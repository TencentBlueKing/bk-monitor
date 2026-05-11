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
import re
import csv
from io import StringIO

from django.conf import settings
from django.utils.translation import gettext as _

from apps.exceptions import ValidationError
from apps.log_clustering.constants import AGGS_FIELD_PREFIX, PatternEnum, StorageTypeEnum
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
    EXPORT_LIMIT = 10000
    INTERVAL_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[mhd])$")

    def __init__(self, index_set_id, params):
        self.index_set_id = int(index_set_id)
        self.params = params
        self.clustering_config = None

    def get_distribution(self) -> dict:
        """返回单个占位符的 TopN 值分布和精确 unique_count。"""

        context = self._prepare_placeholder_analysis()
        raw_regex = context["raw_regex"]
        distribution_rows = self._query_distribution(self._build_distribution_sql(raw_regex))
        unique_count = self._query_count(self._build_unique_count_sql(raw_regex), "unique_count")
        total_count = self._query_count(self._build_total_count_sql(raw_regex), "total_count")

        return self._format_response(
            placeholder=context["placeholder"],
            values=distribution_rows,
            unique_count=unique_count,
            total_count=total_count,
        )

    def get_trend(self) -> dict:
        """返回整体趋势与当前选中值趋势。"""

        context = self._prepare_placeholder_analysis()
        raw_regex = context["raw_regex"]
        selected_value = self._resolve_selected_value()
        interval = self._resolve_interval()
        overall = self._query_trend(self._build_trend_sql(raw_regex, interval=interval))
        if selected_value:
            selected = self._query_trend(
                self._build_trend_sql(raw_regex, interval=interval, selected_value=selected_value)
            )
        else:
            selected = []

        return {
            "placeholder_name": context["placeholder"]["name"],
            "placeholder_index": context["placeholder"]["index"],
            "selected_value": selected_value,
            "interval": interval,
            "overall": overall,
            "selected": selected,
        }

    def get_samples(self) -> dict:
        """返回当前选中值的相关样本。"""

        context = self._prepare_placeholder_analysis()
        selected_value = self._resolve_selected_value(required=True)
        samples_result = self._query_samples(self._build_samples_sql(context["raw_regex"], selected_value))
        return {
            "placeholder_name": context["placeholder"]["name"],
            "placeholder_index": context["placeholder"]["index"],
            "selected_value": selected_value,
            "samples": samples_result["list"],
            "total_records": samples_result["total_records"],
            "result_schema": samples_result["result_schema"],
            "select_fields_order": samples_result["select_fields_order"],
        }

    def export_distribution(self):
        """导出占位符值分布表。"""

        context = self._prepare_placeholder_analysis()
        raw_regex = context["raw_regex"]
        distribution_rows = self._query_distribution(self._build_distribution_sql(raw_regex, limit=self.EXPORT_LIMIT))
        total_count = self._query_count(self._build_total_count_sql(raw_regex), "total_count")
        row_buffer = StringIO()
        csv_writer = csv.writer(row_buffer)
        csv_writer.writerow(["value", "count", "percentage"])
        yield row_buffer.getvalue().encode("utf-8")
        row_buffer.seek(0)
        row_buffer.truncate()

        for item in distribution_rows:
            csv_writer.writerow(
                [
                    item["value"],
                    item["count"],
                    f"{self._calculate_percentage(item['count'], total_count):.2f}%",
                ]
            )
            yield row_buffer.getvalue().encode("utf-8")
            row_buffer.seek(0)
            row_buffer.truncate()

    def _prepare_placeholder_analysis(self) -> dict:
        self._load_clustering_context()
        self._validate_storage_type()

        pattern = self._resolve_pattern()
        placeholders = self._resolve_placeholders(pattern)
        placeholder = self._resolve_target_placeholder(placeholders)
        self._evaluate_pattern_risk(pattern)

        return {
            "pattern": pattern,
            "placeholder": placeholder,
            "raw_regex": self._build_regex(pattern),
        }

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

    def _resolve_selected_value(self, required: bool = False) -> str:
        value = str(self.params.get("value", "") or "")
        if required and not value:
            raise ValidationError(_("value 不能为空"))
        return value

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

    def _build_distribution_sql(self, raw_regex: str, limit: int | None = None) -> str:
        """分布查询只保留 regexp_extract 与聚合逻辑，其他过滤交给 UnifyQuery 注入。"""

        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        signature_field = self._get_signature_field()
        field_name = self.clustering_config.clustering_fields
        extract_sql = f"regexp_extract({field_name}, '{regex}', 1)"
        sql = (
            "SELECT val, COUNT(*) AS cnt "
            f"FROM (SELECT {extract_sql} AS val WHERE {signature_field} = '{signature}') t "
            f"WHERE val != ''{self._build_value_keyword_filter()} "
            "GROUP BY val "
            "ORDER BY cnt DESC, val ASC "
        )
        if limit is None:
            limit = self.params.get("limit", self.DEFAULT_LIMIT)
        if limit:
            sql += f"LIMIT {limit}"
        return sql

    def _build_trend_sql(self, raw_regex: str, interval: str, selected_value: str = "") -> str:
        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        signature_field = self._get_signature_field()
        extract_sql = self._get_extract_sql(regex)
        bucket_sql = self._get_bucket_sql(interval)
        sql = (
            f"SELECT {bucket_sql} AS bucket, COUNT(*) AS cnt "
            f"WHERE {signature_field} = '{signature}' "
            f"AND {extract_sql} != '' "
        )
        if selected_value:
            sql += f"AND {extract_sql} = '{escape_sql_literal(str(selected_value))}' "
        sql += f"GROUP BY {bucket_sql} ORDER BY {bucket_sql} ASC"
        return sql

    def _build_samples_sql(self, raw_regex: str, selected_value: str, with_limit: bool = True) -> str:
        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        signature_field = self._get_signature_field()
        extract_sql = self._get_extract_sql(regex)
        value = escape_sql_literal(selected_value)
        sql = (
            "SELECT * "
            f"WHERE {signature_field} = '{signature}' "
            f"AND {extract_sql} = '{value}' "
            "ORDER BY dtEventTimeStamp DESC "
        )
        if with_limit:
            limit = int(self.params.get("limit", 20))
            sql += f"LIMIT {limit}"
        return sql

    def _build_unique_count_sql(self, raw_regex: str) -> str:
        """unique_count 必须独立 COUNT DISTINCT，不能由 TopN 分布近似推导。"""

        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        signature_field = self._get_signature_field()
        field_name = self.clustering_config.clustering_fields
        extract_sql = f"regexp_extract({field_name}, '{regex}', 1)"
        return (
            "SELECT COUNT(DISTINCT val) AS unique_count "
            f"FROM (SELECT {extract_sql} AS val WHERE {signature_field} = '{signature}') t "
            f"WHERE val != ''{self._build_value_keyword_filter()}"
        )

    def _build_total_count_sql(self, raw_regex: str) -> str:
        regex = escape_sql_literal(raw_regex)
        signature = escape_sql_literal(self.params["signature"])
        signature_field = self._get_signature_field()
        field_name = self.clustering_config.clustering_fields
        extract_sql = f"regexp_extract({field_name}, '{regex}', 1)"
        return (
            "SELECT COUNT(*) AS total_count "
            f"FROM (SELECT {extract_sql} AS val WHERE {signature_field} = '{signature}') t "
            f"WHERE val != ''{self._build_value_keyword_filter()}"
        )

    def _get_signature_field(self) -> str:
        pattern_level = str(self.params.get("pattern_level") or PatternEnum.LEVEL_05.value)
        if pattern_level not in {"01", "03", "05", "07", "09"}:
            raise ValidationError(_("pattern_level 不合法: {level}").format(level=pattern_level))
        return f"{AGGS_FIELD_PREFIX}_{pattern_level}"

    def _get_extract_sql(self, escaped_regex: str) -> str:
        field_name = self.clustering_config.clustering_fields
        return f"regexp_extract({field_name}, '{escaped_regex}', 1)"

    def _build_value_keyword_filter(self) -> str:
        value_keyword = str(self.params.get("value_keyword", "") or "").strip()
        if not value_keyword:
            return ""
        return f" AND INSTR(val, '{escape_sql_literal(value_keyword)}') > 0"

    def _get_bucket_sql(self, interval: str) -> str:
        bucket_ms = self._interval_to_milliseconds(interval)
        return f"CAST(FLOOR(dtEventTimeStamp / {bucket_ms}) * {bucket_ms} AS BIGINT)"

    def _resolve_interval(self) -> str:
        interval = str(self.params.get("interval") or "auto")
        if interval == "auto":
            duration_ms = max(self.params["end_time"] - self.params["start_time"], 0)
            if duration_ms <= 60 * 60 * 1000:
                return "1m"
            if duration_ms <= 6 * 60 * 60 * 1000:
                return "5m"
            if duration_ms <= 3 * 24 * 60 * 60 * 1000:
                return "1h"
            return "1d"

        self._interval_to_milliseconds(interval)
        return interval

    def _interval_to_milliseconds(self, interval: str) -> int:
        match = self.INTERVAL_PATTERN.match(interval)
        if not match:
            raise ValidationError(_("interval 不合法: {interval}").format(interval=interval))
        value = int(match.group("value"))
        unit = match.group("unit")
        unit_to_ms = {
            "m": 60 * 1000,
            "h": 60 * 60 * 1000,
            "d": 24 * 60 * 60 * 1000,
        }
        return value * unit_to_ms[unit]

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
        for field, value in (self.params.get("groups") or {}).items():
            if not field:
                continue
            if field in existing_fields:
                continue
            merged.append({"field": field, "operator": "is", "value": value, "condition": "and"})
        return merged

    def _query_chart_data(self, sql: str) -> dict:
        """统一从 clustered_rt 查询 Doris SQL，避免落到默认 _analysis 表。"""

        return self._build_chart_handler(sql).get_chart_data()

    def _build_chart_handler(self, sql: str) -> ClusteringUnifyQueryChartHandler:
        params = self._build_query_params(sql)
        return ClusteringUnifyQueryChartHandler(params, clustered_rt=self.clustering_config.clustered_rt)

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

    def _query_trend(self, sql: str) -> list[dict]:
        result = self._query_chart_data(sql)
        return [
            {"time": self._to_int(item.get("bucket", 0)), "count": self._to_int(item.get("cnt", 0))}
            for item in result.get("list", [])
        ]

    def _query_samples(self, sql: str) -> dict:
        result = self._query_chart_data(sql)
        return {
            "list": [dict(item) for item in result.get("list", [])],
            "total_records": self._to_int(result.get("total_records", len(result.get("list", [])))),
            "result_schema": result.get("result_schema", []),
            "select_fields_order": result.get("select_fields_order", []),
        }

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
            "total_count": total_count,
            "values": [
                {
                    "value": item["value"],
                    "count": item["count"],
                    "percentage": self._calculate_percentage(item["count"], total_count),
                }
                for item in values
            ],
        }
