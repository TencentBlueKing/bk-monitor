"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy

from django.conf import settings
from django.utils.translation import gettext as _

from apps.exceptions import ValidationError
from apps.log_clustering.constants import StorageTypeEnum
from apps.log_clustering.exceptions import PlaceholderAnalysisNotSupportedException
from apps.log_clustering.models import ClusteringConfig
from apps.log_clustering.utils.pattern import (
    build_doris_regexp,
    escape_sql_literal,
    evaluate_pattern_risk,
    parse_pattern_placeholders,
)
from apps.log_search.handlers.index_set import BaseIndexSetHandler
from apps.log_unifyquery.handler.chart import UnifyQueryChartHandler
from apps.utils.log import logger


class ClusteringUnifyQueryChartHandler(UnifyQueryChartHandler):
    """复用 UnifyQuery SQL 执行能力，但强制走 clustered_rt 路由。"""

    def __init__(self, params, clustered_rt):
        self.clustered_rt = clustered_rt
        super().__init__(params)

    def init_base_dict(self):
        query_list = []
        for index, index_info in enumerate(self.index_info_list):
            query_list.append(
                {
                    "data_source": settings.UNIFY_QUERY_DATA_SOURCE,
                    "reference_name": self.generate_reference_name(index),
                    "conditions": self._transform_additions(index_info),
                    "query_string": self.query_string,
                    "sql": self.sql,
                    "table_id": BaseIndexSetHandler.get_data_label(
                        index_info["index_set_id"], clustered_rt=self.clustered_rt
                    ),
                }
            )

        return {
            "query_list": query_list,
            "metric_merge": " + ".join([query["reference_name"] for query in query_list]),
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "down_sample_range": "",
            "timezone": "UTC",
            "bk_biz_id": self.bk_biz_id,
            "is_merge_db": True,
        }


class PlaceholderAnalysisHandler:
    """占位符值分布分析入口，收口参数校验、SQL 构造和结果格式化。"""

    DEFAULT_LIMIT = 100

    def __init__(self, index_set_id, params):
        self.index_set_id = int(index_set_id)
        self.params = params
        self.clustering_config = None

    def get_distribution(self) -> dict:
        """返回单个占位符的 TopN 值分布和精确 unique_count。"""

        self._load_clustering_context()
        self._validate_storage_type()
        self._validate_groups()

        pattern = self._resolve_pattern()
        placeholders = self._resolve_placeholders(pattern)
        placeholder = self._resolve_target_placeholder(placeholders)

        self._evaluate_pattern_risk(pattern)

        raw_regex = self._build_regex(pattern)
        distribution_rows = self._query_distribution(self._build_distribution_sql(raw_regex))
        unique_count = self._query_count(self._build_unique_count_sql(raw_regex), "unique_count")
        total_count = self._query_count(self._build_total_count_sql(raw_regex), "total_count")

        return self._format_response(
            placeholder=placeholder,
            values=distribution_rows,
            unique_count=unique_count,
            total_count=total_count,
        )

    def _load_clustering_context(self):
        self.clustering_config = ClusteringConfig.get_by_index_set_id(index_set_id=self.index_set_id)

    def _validate_storage_type(self):
        if (
            self.clustering_config.storage_type != StorageTypeEnum.DORIS.value
            or not self.clustering_config.clustered_rt
        ):
            raise PlaceholderAnalysisNotSupportedException(
                PlaceholderAnalysisNotSupportedException.MESSAGE.format(reason=_("当前业务不是 Doris 聚类结果表"))
            )

    def _validate_groups(self):
        """groups 只允许描述当前聚类行上下文，不能和 addition 语义冲突。"""

        groups = self.params.get("groups", {})
        addition = self.params.get("addition", [])
        group_fields = set(self.clustering_config.group_fields or [])

        invalid_fields = sorted(set(groups) - group_fields)
        if invalid_fields:
            raise ValidationError(_("groups 包含非法字段: {fields}").format(fields=", ".join(invalid_fields)))

        for item in addition:
            field = item.get("field")
            if field not in groups:
                continue
            if not self._is_addition_compatible_with_group(item, groups[field]):
                raise ValidationError(_("groups 与 addition 在字段 {field} 上冲突").format(field=field))

    @staticmethod
    def _is_addition_compatible_with_group(addition, group_value):
        operator = addition.get("operator")
        value = addition.get("value")
        if operator == "is":
            return str(value) == str(group_value)
        if operator == "is one of":
            if isinstance(value, list):
                value_list = value
            else:
                value_list = str(value).split(",")
            return str(group_value) in [str(item) for item in value_list]
        return False

    def _resolve_pattern(self) -> str:
        pattern = self.params["pattern"].strip()
        if not pattern:
            raise ValidationError(_("pattern 不能为空"))
        return pattern

    def _resolve_placeholders(self, pattern: str) -> list[dict]:
        placeholders = parse_pattern_placeholders(pattern)
        if not placeholders:
            raise ValidationError(_("pattern 中不存在占位符"))
        return placeholders

    def _resolve_target_placeholder(self, placeholders: list[dict]) -> dict:
        placeholder_index = self.params["placeholder_index"]
        if placeholder_index >= len(placeholders):
            raise ValidationError(_("placeholder_index 超出占位符范围"))
        return placeholders[placeholder_index]

    def _evaluate_pattern_risk(self, pattern: str):
        """风险只做日志观测，不阻断 Sprint 1 查询主链路。"""

        risk = evaluate_pattern_risk(
            pattern=pattern,
            placeholder_index=self.params["placeholder_index"],
            max_log_length=self.clustering_config.max_log_length,
            predefined_varibles=self.clustering_config.predefined_varibles,
        )
        logger.info(
            "placeholder analysis risk: index_set_id=%s signature=%s placeholder_index=%s risk_level=%s reasons=%s",
            self.index_set_id,
            self.params["signature"],
            self.params["placeholder_index"],
            risk["risk_level"],
            ",".join(risk["reasons"]),
        )

    def _build_regex(self, pattern: str) -> str:
        try:
            return build_doris_regexp(
                pattern=pattern,
                placeholder_index=self.params["placeholder_index"],
                predefined_varibles=self.clustering_config.predefined_varibles,
            )
        except ValueError as error:
            raise PlaceholderAnalysisNotSupportedException(
                PlaceholderAnalysisNotSupportedException.MESSAGE.format(reason=str(error))
            ) from error

    def _build_distribution_sql(self, raw_regex: str) -> str:
        """分布查询只保留 regexp_extract 与聚合逻辑，其他过滤交给 UnifyQuery 注入。"""

        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        field_name = self.clustering_config.clustering_fields
        limit = self.params.get("limit", self.DEFAULT_LIMIT)
        extract_sql = f"regexp_extract({field_name}, '{regex}', 1)"
        return (
            f"SELECT {extract_sql} AS val, COUNT(*) AS cnt "
            f"WHERE __dist_05 = '{signature}' "
            f"AND {extract_sql} != '' "
            f"GROUP BY {extract_sql} "
            "ORDER BY cnt DESC "
            f"LIMIT {limit}"
        )

    def _build_unique_count_sql(self, raw_regex: str) -> str:
        """unique_count 必须独立 COUNT DISTINCT，不能由 TopN 分布近似推导。"""

        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        field_name = self.clustering_config.clustering_fields
        extract_sql = f"regexp_extract({field_name}, '{regex}', 1)"
        return (
            f"SELECT COUNT(DISTINCT {extract_sql}) AS unique_count "
            f"WHERE __dist_05 = '{signature}' "
            f"AND {extract_sql} != ''"
        )

    def _build_total_count_sql(self, raw_regex: str) -> str:
        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        field_name = self.clustering_config.clustering_fields
        extract_sql = f"regexp_extract({field_name}, '{regex}', 1)"
        return (
            "SELECT COUNT(*) AS total_count "
            f"WHERE __dist_05 = '{signature}' "
            f"AND {extract_sql} != ''"
        )

    def _build_query_params(self, sql: str) -> dict:
        """把聚类分析上下文转换成 UnifyQueryChartHandler 可消费的参数。"""

        return {
            "sql": sql,
            "bk_biz_id": self.params.get("bk_biz_id") or self.clustering_config.bk_biz_id,
            "index_set_ids": [self.index_set_id],
            "start_time": self.params["start_time"],
            "end_time": self.params["end_time"],
            "keyword": self.params.get("keyword", ""),
            "addition": self._merge_groups_into_addition(),
            "host_scopes": self.params.get("host_scopes", {}),
            "ip_chooser": self.params.get("ip_chooser", {}),
        }

    def _merge_groups_into_addition(self) -> list:
        # groups 表示当前聚类行的 group_by 上下文，统一收敛为等值 addition。
        merged = copy.deepcopy(self.params.get("addition", []))
        existing_fields = {item.get("field") for item in merged}
        for field, value in self.params.get("groups", {}).items():
            if field in existing_fields:
                continue
            merged.append({"field": field, "operator": "is", "value": value, "condition": "and"})
        return merged

    def _query_chart_data(self, sql: str) -> dict:
        """统一从 clustered_rt 查询 Doris SQL，避免落到默认 _analysis 表。"""

        params = self._build_query_params(sql)
        return ClusteringUnifyQueryChartHandler(
            params, clustered_rt=self.clustering_config.clustered_rt
        ).get_chart_data()

    def _query_distribution(self, sql: str) -> list[dict]:
        result = self._query_chart_data(sql)
        values = []
        for item in result.get("list", []):
            values.append(
                {
                    "value": item.get("val", ""),
                    "count": self._to_int(item.get("cnt", 0)),
                }
            )
        return values

    def _query_count(self, sql: str, field_name: str) -> int:
        """读取单行聚合结果中的数值字段。"""

        result = self._query_chart_data(sql)
        if not result.get("list"):
            return 0
        return self._to_int(result["list"][0].get(field_name, 0))

    @staticmethod
    def _to_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(float(value or 0))

    @staticmethod
    def _calculate_percentage(count: int, total_count: int) -> float:
        """percentage 的分母是本次 regexp_extract 命中的非空总行数。"""

        if total_count <= 0:
            return 0
        return round(count * 100 / total_count, 2)

    def _format_response(self, placeholder: dict, values: list[dict], unique_count: int, total_count: int) -> dict:
        return {
            "placeholder_name": placeholder["name"],
            "placeholder_index": placeholder["index"],
            "unique_count": unique_count,
            "values": [
                {
                    "value": item["value"],
                    "count": item["count"],
                    "percentage": self._calculate_percentage(item["count"], total_count),
                }
                for item in values
            ],
        }
