"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
from typing import Any

from core.drf_resource import api
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.utils.base import get_bar_interval_number
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.data_source.utils import types
from constants.otel_query import FieldTypeEnum


class BaseQuery:
    USING: tuple[str, str]
    DEFAULT_TIME_FIELD = "time"
    DEFAULT_SORT = ["time"]
    DEFAULT_RETENTION = 7

    # 枚举查询上限
    QUERY_MAX_LIMIT = 10000

    # 时间字段精度，用于时间字段查询时做乘法（秒 -> 毫秒）
    TIME_FIELD_ACCURACY = 1000

    # 时间填充，单位 s：未指定 end_time 时向前填充，避免查询最新数据时因延迟查不到
    TIME_PADDING = 5

    # 查询字段映射
    KEY_REPLACE_FIELDS: dict[str, str] = {}

    # 字段别名映射，[{field_name: alias}]
    FIELD_ALIAS_MAP_LIST: list[dict[str, str]] = []
    # 字段操作符映射，{field_type: operations}
    FIELD_OPERATIONS: dict[str, list[dict[str, Any]]] = {}
    # 字段单位映射，｛field_name: unit｝
    FIELD_UNITS: dict[str, str] = {}
    # 枚举字段选项值映射，{field_name: [{"value": "", "alias": ""}]}
    ENUM_FIELD_OPTION_VALUES: dict[str, list[dict[str, Any]]] = {}

    def _get_q(self, time_field: str | None = None) -> QueryConfigBuilder:
        """构建基础查询配置，指定数据源类型和时间字段。

        :param time_field: 时间字段名，默认使用 DEFAULT_TIME_FIELD
        :return: QueryConfigBuilder 实例
        """
        return QueryConfigBuilder(self.USING).time_field(time_field or self.DEFAULT_TIME_FIELD)

    def get_qs(self, start_time: int, end_time: int) -> UnifyQuerySet:
        """构建基础查询集，设置时间范围并关闭时间对齐。

        :param start_time: 开始时间（秒级或毫秒级时间戳）
        :param end_time: 结束时间（秒级或毫秒级时间戳）
        :return: UnifyQuerySet 实例
        """
        start_time, end_time = self._get_time_range(start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(False)

    @classmethod
    def get_q_from_query_config(cls, query_config: dict[str, Any]) -> QueryConfigBuilder:
        """从查询配置字典构建 QueryConfigBuilder。

        :param query_config: 查询配置字典，包含 data_type_label、data_source_label、table、
                             group_by、where、filter_dict、query_string 等字段
        :return: QueryConfigBuilder 实例
        """
        return (
            QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
            .table(query_config["table"])
            .time_field(query_config.get("time_field") or cls.DEFAULT_TIME_FIELD)
            .group_by(*query_config.get("group_by", []))
            .conditions(query_config.get("where", []))
            .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
            .query_string(query_config.get("query_string") or "")
        )

    @classmethod
    def _translate_field(cls, field: str) -> str:
        """将字段名按 KEY_REPLACE_FIELDS 映射转换，无映射则返回原字段名。

        :param field: 原始字段名
        :return: 转换后的字段名
        """
        return cls.KEY_REPLACE_FIELDS.get(field) or field

    @classmethod
    def process_sort_fields(cls, fields):
        """
        预处理排序字段列表，调整字段排序格式

        :param fields: 原始排序字段列表，如 ["-time", "name"]
        :return: 处理后的排序字段列表，如 ["time desc", "name"]
        """
        processed_fields = []
        for field in fields:
            # 提取字段名（去掉可能的 "-" 前缀）
            is_descending = field.startswith("-")
            field = field[1:] if is_descending else field

            # 保留原始排序方向
            if is_descending:
                processed_fields.append(f"{field} desc")
            else:
                processed_fields.append(field)
        return processed_fields

    @classmethod
    def _add_query(cls, qs: UnifyQuerySet, q_list: list[QueryConfigBuilder]) -> UnifyQuerySet:
        """将多个查询配置依次添加到查询集中。

        :param qs: 基础查询集
        :param q_list: 待添加的 QueryConfigBuilder 列表
        :return: 添加所有查询后的 UnifyQuerySet
        """
        for q in q_list:
            qs = qs.add_query(q)
        return qs

    def _get_time_range(self, start_time: int | None = None, end_time: int | None = None) -> tuple[int, int]:
        return self.get_retention_time_range(self.retention, start_time, end_time)

    @property
    def retention(self) -> int:
        """数据保留天数（天），表示不自动补齐时间窗口。

        子类（如 APM / RUM Query）应基于 TraceDatasourceTarget 提供具体实现。
        """
        return self.DEFAULT_RETENTION

    @classmethod
    def get_retention_time_range(
        cls, retention: int, start_time: int | None = None, end_time: int | None = None
    ) -> tuple[int, int]:
        """基于数据保留天数构造查询时间窗口（毫秒级）。

        覆盖全部不传、只传一端、两端均传三种情况；显式时间范围保持原有行为，
        仅将 end_time 限制在当前时间之前、将 start_time 限制保留期下界之内。

        :param retention: 数据保留天数
        :param start_time: 开始时间戳（秒级），缺省时取保留期下界
        :param end_time: 结束时间戳（秒级），缺省时取当前时间（含 TIME_PADDING 填充）
        :return: (毫秒级开始时间, 毫秒级结束时间)
        """
        now: int = int(datetime.datetime.now().timestamp())

        retention_seconds: int = int(datetime.timedelta(days=retention).total_seconds())
        # 最早可查询时间（秒）
        earliest_start_time: int = now - retention_seconds

        if not end_time:
            # 不传 end_time 代表查询最新数据，请求时间距离实际存储查询时间可能存在延迟，
            # 因此增加一个时间填充，避免查询不到数据。
            end_time = now + cls.TIME_PADDING
        else:
            # 已指定查询时间范围，限制 end_time 不超过当前时间，避免查询到未来数据。
            end_time = min(now, end_time)

        start_time = start_time or earliest_start_time
        if end_time < earliest_start_time:
            # 查询窗口不在有效保留期内：-<start_time>-----<end_time>-----<earliest_start_time>----<now>--
            start_time = max(end_time - retention_seconds, start_time)
        else:
            # 查询窗口部分或全部落在有效期内：-<start_time>---<earliest_start_time>---<end_time>----<now>--
            start_time = max(earliest_start_time, start_time)

        return start_time * cls.TIME_FIELD_ACCURACY, end_time * cls.TIME_FIELD_ACCURACY

    def _query_list(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """分页查询原始记录列表。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param offset: 分页偏移量，默认 0
        :param limit: 每页返回条数，默认 20
        :return: 记录列表
        """
        qs = self.get_qs(start_time, end_time).offset(offset).limit(limit)
        return list(self._add_query(qs, queries))

    def _query_total(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
    ) -> int:
        """查询记录总数（COUNT）。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :return: 记录总数
        """
        return int(self._query_field_aggregated_value(queries, start_time, end_time, "_index", "count"))

    def _query_field_topk(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        need_empty: bool = False,
    ) -> list[dict[str, Any]]:
        """查询指定字段出现次数最多的 Top-K 值。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param field: 目标字段名
        :param limit: 返回 Top-K 数量，默认 5
        :param need_empty: 为 True 时统计含空值的记录数（使用 _index 计数），默认 False
        :return: 按出现次数降序排列的记录列表，每条记录包含字段值和计数
        """
        alias: str = "a"
        query_limit = limit * 2 + 10
        queries = [
            q.alias(alias)
            .metric(field="_index" if need_empty else field, method="COUNT", alias=alias)
            .group_by(field)
            .order_by("_value desc")
            for q in queries
        ]
        qs = (
            self.get_qs(start_time, end_time)
            .expression(alias)
            .time_agg(False)
            .instant()
            .limit(min(query_limit, self.QUERY_MAX_LIMIT))
        )
        records = list(self._add_query(qs, queries))
        return sorted(records, key=lambda item: item["_result_"], reverse=True)[:limit]

    def _query_option_values(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int = 20,
    ) -> dict[str, list[str]]:
        """并发查询多个字段的可选枚举值。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param fields: 需要枚举可选值的字段列表
        :param limit: 每个字段最多返回的枚举值数量，默认 20
        :return: 字段名到枚举值列表的映射字典
        """
        query_limit = limit * 2 + 10
        qs = (
            self.get_qs(start_time, end_time)
            .expression("a")
            .time_agg(False)
            .instant()
            .limit(min(query_limit, self.QUERY_MAX_LIMIT))
        )
        option_values: dict[str, list[str]] = {
            field: [d["value"] for d in self.ENUM_FIELD_OPTION_VALUES.get(field, [])] for field in fields
        }
        ThreadPool().map_ignore_exception(
            self._collect_option_values,
            [
                (queries, qs, field_name, option_values)
                for field_name, value_list in option_values.items()
                if not value_list
            ],
        )
        return {field: values[:limit] for field, values in option_values.items()}

    @classmethod
    def _collect_option_values(
        cls, queries: list[QueryConfigBuilder], queryset: UnifyQuerySet, field: str, option_values: dict[str, list[str]]
    ):
        """收集单个字段的枚举值，过滤掉计数为 0 的桶，结果写入 option_values。

        :param queries: 查询配置列表
        :param queryset: 基础查询集（已设置时间范围和分页）
        :param field: 目标字段名
        :param option_values: 结果收集字典，key 为字段名，value 为枚举值列表（原地修改）
        """
        alias = "a"
        queries = [
            q.alias(alias).metric(field=field, method="COUNT", alias=alias).group_by(field).order_by("_value desc")
            for q in queries
        ]
        records = sorted(
            cls._add_query(queryset, queries),
            key=lambda item: item["_result_"],
            reverse=True,
        )
        for bucket in records:
            if bucket["_result_"] == 0:
                continue
            option_values[field].append(bucket[field])

    def _query_graph_config(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 20,
        enable_topk=False,
    ):
        """构建图表配置，按字段分组统计时序数据。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param field: 分组统计的目标字段名
        :param limit: 最多展示的分组数量，默认 20
        :param enable_topk: 为 True 时使用 topk 表达式过滤，默认 False
        :return: 图表查询配置对象
        """
        alias = "a"
        queries = [
            q.alias(alias)
            .interval(get_bar_interval_number(start_time, end_time))
            .metric(field=field, method="COUNT", alias=alias)
            .group_by(field)
            for q in queries
        ]
        return self._add_query(
            self.get_qs(start_time, end_time)
            .expression(f"topk({limit}, {alias})" if enable_topk else alias)
            .time_agg(False)
            .instant(),
            queries,
        ).config

    def _query_field_aggregated_value(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        method: str,
    ) -> int | float:
        """
        查询字段聚合值。

        - 所有 RT 的 reference 和 metric alias 统一设为 "a"
        - expression 规则：max/min 使用 max(a)/min(a)，其余使用 "a"
        - distinct 保留多 RT 枚举合并去重方式，不直接合并各 RT 的 distinct 标量
        """
        method = method.lower()
        if method == "distinct":
            return self._query_field_distinct_value(queries, start_time, end_time, field)

        alias = "a"
        queries = [q.alias(alias).metric(field=field, method=method, alias=alias) for q in queries]
        qs = (
            self.get_qs(start_time, end_time)
            .expression(f"{method}(a)" if method in {"max", "min"} else "a")
            .time_agg(False)
            .instant()
            .limit(1)
        )
        return list(self._add_query(qs, queries))[0]["_result_"]

    def _query_field_distinct_value(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
    ) -> int:
        """
        查询字段去重数量。

        通过枚举所有值后合并去重计算，而非直接合并各 RT 的 distinct 标量，
        避免多 RT 场景下重叠值被重复计数。
        """
        alias = "a"
        # 单 RT 直接使用存储侧 distinct
        base_qs = self.get_qs(start_time, end_time).expression(alias).time_agg(False).instant()
        if len(queries) == 1:
            queries = [q.alias(alias).metric(field=field, method="distinct", alias=alias) for q in queries]
            return list(self._add_query(base_qs, queries).limit(1))[0]["_result_"]

        # 多 RT 需要枚举后合并去重
        queries = [
            q.alias(alias).metric(field=field, method="COUNT", alias=alias).group_by(field).order_by("_value desc")
            for q in queries
        ]
        distinct_values: set[Any] = set()
        for record in self._add_query(base_qs.limit(self.QUERY_MAX_LIMIT), queries):
            if record.get("_result_", 0) == 0:
                continue
            distinct_values.add(record.get(field))
        return len(distinct_values)

    @classmethod
    def merge_field_metadata(cls, current: dict[str, Any], field_dict: dict[str, Any]) -> dict[str, Any]:
        return {
            **current,
            "is_agg": bool(current["is_agg"] or field_dict["is_agg"]),
            "is_analyzed": bool(current["is_analyzed"] or field_dict["is_analyzed"]),
            "is_case_sensitive": bool(current["is_case_sensitive"] and field_dict["is_case_sensitive"]),
        }

    @classmethod
    def _resolve_field_alias(cls, field_name: str) -> str:
        for mapping in reversed(cls.FIELD_ALIAS_MAP_LIST):
            if field_name in mapping:
                return mapping[field_name]
        return field_name

    def _query_fields(
        self, targets: list[tuple[types.TableId, types.SpaceUid]], start_time: int | None, end_time: int | None
    ) -> dict[str, dict[str, Any]]:
        """并发查询多个结果表的字段信息，合并为字段名到字段详情的映射。

        :param targets: 结果表 ID 与空间 UID 的元组列表
        :param start_time: 开始时间戳（秒级，缺省时按 retention 自动补齐后统一转为毫秒级）
        :param end_time: 结束时间戳（秒级，缺省时按 retention 自动补齐后统一转为毫秒级）
        :return: field_name 到字段详情字典的映射，每项包含以下键：
            - field_name: 实际字段名，用于查询、过滤、聚合
            - field_alias: 字段别名，无别名时与 field_name 相同
            - field_type: ES 字段类型，如 keyword、text、long 等；多表类型冲突时为 "conflict"
            - field_unit: 字段单位（可选，仅在 FIELD_UNITS 中有配置时存在）
            - origin_field: 原始顶层字段名，嵌套字段时为顶层字段（如 attributes.http.url 对应 attributes）
            - is_searchable: 是否可搜索（object/nested 类型为 False）
            - is_agg: 是否支持聚合、分组、排序
            - is_list: 是否可展示在列表表头中（object/nested 类型为 False）
            - is_analyzed: 是否经过文本分析器分词（查询层私有键，接口层应忽略）
            - is_case_sensitive: 是否区分大小写（查询层私有键，接口层应忽略）
            - wildcard_case_insensitive(bool): 通配符查询是否忽略大小写（查询层私有键，接口层应忽略）
            - tokenize_on_chars (list): 自定义分词字符列表（查询层私有键，接口层应忽略）
            - supported_operations: 该字段类型支持的操作符列表
            - option_values: 字段可选值列表[{"value": "", "alias": ""}]（可选）

        """
        start_time, end_time = self._get_time_range(start_time, end_time)
        param_list: list[tuple[types.TableId, types.SpaceUid, int, int]] = [
            (table_id, space_uid, start_time, end_time) for table_id, space_uid in targets
        ]
        field_map: dict[str, dict[str, Any]] = {}
        for field_list in ThreadPool().map_ignore_exception(self._query_info_fields, param_list):
            for field_dict in field_list:
                field_name = field_dict.get("field_name", "")
                field_dict.pop("alias_name", None)
                field_dict["field_alias"] = self._resolve_field_alias(field_name)

                current = field_map.get(field_name)
                if current is None:
                    field_map[field_name] = field_dict
                elif current["field_type"] != field_dict["field_type"]:
                    field_map[field_name] = self.merge_field_metadata(
                        {**current, "field_type": FieldTypeEnum.CONFLICT.value},
                        {**field_dict, "field_type": FieldTypeEnum.CONFLICT.value},
                    )
                else:
                    field_map[field_name] = self.merge_field_metadata(current, field_dict)

                _field_dict = field_map[field_name]

                _field_dict["supported_operations"] = self.FIELD_OPERATIONS.get(
                    _field_dict["field_type"],
                    [],
                )
                _field_dict["is_list"] = _field_dict["is_searchable"] = _field_dict["field_type"] not in {
                    "object",
                    "nested",
                }
                if field_name in self.FIELD_UNITS:
                    _field_dict["field_unit"] = self.FIELD_UNITS[field_name]
                if field_name in self.ENUM_FIELD_OPTION_VALUES:
                    _field_dict["option_values"] = self.ENUM_FIELD_OPTION_VALUES[field_name]
        return field_map

    @classmethod
    def _query_info_fields(cls, table_id: str, space_uid: str, start_time: int, end_time: int) -> list[dict[str, Any]]:
        """查询单个结果表的字段信息列表。

        调用 unify_query.query_info_field_map 接口获取指定结果表在给定时间范围内的字段元数据。

        :param table_id: 结果表 ID
        :param space_uid: 空间 UID
        :param start_time: 开始时间戳（毫秒级，已按 retention 补齐窗口）
        :param end_time: 结束时间戳（毫秒级，已按 retention 补齐窗口）
        :return: 字段信息列表，每项为包含以下键的字典：
            - alias_name (str): 字段别名
            - field_name (str): 字段名称
            - field_type (str): 字段类型，如 keyword、integer、float 等
            - origin_field (str): 原始字段名
            - is_agg (bool): 是否支持聚合
            - is_analyzed (bool): 是否已分词（全文检索）
            - is_case_sensitive (bool): 是否大小写敏感
            - wildcard_case_insensitive (bool): 通配符查询是否忽略大小写
            - tokenize_on_chars (list): 自定义分词字符列表
        """
        return api.unify_query.query_info_field_map(
            {
                "data_source": "bkapm",
                "table_id": table_id,
                "space_uid": space_uid,
                "start_time": start_time,
                "end_time": end_time,
            }
        ).get("data", [])
