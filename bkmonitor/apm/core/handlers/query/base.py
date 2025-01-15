# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import copy
import datetime
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.db.models import Q
from django.utils.functional import cached_property, classproperty
from django.utils.translation import gettext_lazy as _

from apm import types
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import ApmDataSourceConfigBase, MetricDataSource, TraceDataSource
from bkmonitor.data_source import dict_to_q
from bkmonitor.utils.thread_backend import ThreadPool
from constants.data_source import DataSourceLabel, DataTypeLabel

logger = logging.getLogger("apm")


def dsl_to_filter_dict(query: Dict[str, Any], depth=1, width=1) -> Dict[str, Any]:
    filter_dict: Dict[str, Any] = {}

    if "nested" in query:
        nested_query = query["nested"]
        if "query" in nested_query:
            return dsl_to_filter_dict(nested_query["query"], depth + 1, width)
    elif "bool" in query:
        bool_query = query["bool"]
        for clause in ["must", "should"]:
            if clause not in bool_query:
                continue

            sub_filters = [
                dsl_to_filter_dict(sub_query, depth + 1, idx) for idx, sub_query in enumerate(bool_query[clause])
            ]
            is_all_query_string: bool = all(
                [len(sub_filter.keys()) == 1 and "__" in list(sub_filter.keys())[0] for sub_filter in sub_filters]
            )
            for sub_filter in sub_filters:
                if clause == "must":
                    for field, values in sub_filter.items():
                        if is_all_query_string and (field.startswith("wildcard")):
                            filter_dict.setdefault(field, []).extend(values)
                        else:
                            filter_dict[field] = values
                elif clause == "should":
                    filter_dict.setdefault("or", []).append(sub_filter)
    else:
        op: str = ""
        lookup: str = ""
        child_query: Dict[str, Any] = {}
        for op, lookup in {"query_string": "qs", "term": "eq", "wildcard": "include"}.items():
            if op in query:
                child_query = query[op]
                break

        if not op:
            return filter_dict

        if op == "query_string":
            field: str = child_query["default_field"]
            if field == "*":
                filter_dict[f"{field}__*__{lookup}__nested"] = [child_query["query"]]
            else:
                if "." not in field:
                    path = "*"
                else:
                    path, __ = field.split(".", 1)
                filter_dict[f"{field}__{path}__{lookup}__nested"] = [child_query["query"]]
        else:
            for field, value in child_query.items():
                path, __ = field.split(".", 1)
                filter_dict[f"{field}__{path}__{lookup}__nested"] = [value["value"]]
    return filter_dict


class FilterOperator:
    # 走ES查询可以使用的操作符
    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"


class LogicSupportOperator:
    # 走特殊逻辑可以使用的操作符
    LOGIC = "logic"


class BaseQuery:
    USING_LOG: Tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_APM)

    USING_METRIC: Tuple[str, str] = (DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM)

    DEFAULT_DATASOURCE_CONFIGS: Dict[str, Dict[str, Any]] = {
        ApmDataSourceConfigBase.METRIC_DATASOURCE: {
            "using": USING_METRIC,
            "get_table_id_func": MetricDataSource.get_table_id,
        },
        ApmDataSourceConfigBase.TRACE_DATASOURCE: {
            "using": USING_LOG,
            "get_table_id_func": TraceDataSource.get_table_id,
        },
    }

    # 时间填充，单位 s
    TIME_PADDING = 5

    # 时间字段精度，用于时间字段查询时做乘法
    TIME_FIELD_ACCURACY = 1000

    # 默认时间字段
    DEFAULT_TIME_FIELD = "end_time"

    # 字段候选值最多获取500个
    OPTION_VALUES_MAX_SIZE = 500

    # 查询字段映射
    KEY_REPLACE_FIELDS: Dict[str, str] = {}

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        retention: int,
        overwrite_datasource_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.bk_biz_id: int = bk_biz_id
        self.app_name: str = app_name
        self.retention: int = retention
        self.overwrite_datasource_configs: Dict[str, Dict[str, Any]] = overwrite_datasource_configs or {}

    @classproperty
    def operator_mapping(self) -> Dict[str, Callable[[QueryConfigBuilder, str, types.FilterValue], Q]]:
        return {
            FilterOperator.EXISTS: lambda q, field, value: q & Q(**{f"{field}__exists": value}),
            FilterOperator.NOT_EXISTS: lambda q, field, value: q & Q(**{f"{field}__nexists": value}),
            FilterOperator.EQUAL: lambda q, field, value: q & q & Q(**{f"{field}__eq": value}),
            FilterOperator.NOT_EQUAL: lambda q, field, value: q & Q(**{f"{field}__neq": value}),
            FilterOperator.BETWEEN: lambda q, field, value: q
            & Q(**{f"{field}__gte": value[0], f"{field}__lte": value[1]}),
            FilterOperator.LIKE: lambda q, field, value: q & Q(**{f"{field}__include": value[0]}),
            LogicSupportOperator.LOGIC: lambda q, field, value: self._add_logic_filter(q, field, value),
        }

    @cached_property
    def _datasource_configs(self) -> Dict[str, Dict[str, Any]]:
        datasource_configs: Dict[str, Dict[str, Any]] = copy.deepcopy(self.DEFAULT_DATASOURCE_CONFIGS)
        for datasource_type, conf in self.overwrite_datasource_configs.items():
            datasource_configs.setdefault(datasource_type, {}).update(conf)
        return datasource_configs

    def _get_table_id(self, datasource_type: str) -> str:
        get_table_id_func: Callable[[int, str], str] = self._datasource_configs[datasource_type]["get_table_id_func"]
        return get_table_id_func(self.bk_biz_id, self.app_name)

    def _get_q(self, datasource_type: str):
        datasource_config: Dict[str, Any] = self._datasource_configs[datasource_type]
        return QueryConfigBuilder(datasource_config["using"]).table(self._get_table_id(datasource_type))

    @property
    def q(self) -> QueryConfigBuilder:
        return self.log_q

    @property
    def log_q(self) -> QueryConfigBuilder:
        return self._get_q(ApmDataSourceConfigBase.TRACE_DATASOURCE).time_field(self.DEFAULT_TIME_FIELD)

    @property
    def metric_q(self) -> QueryConfigBuilder:
        return self._get_q(ApmDataSourceConfigBase.METRIC_DATASOURCE)

    def time_range_queryset(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        start_time, end_time = self._get_time_range(self.retention, start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time)

    def _query_option_values(
        self, q: QueryConfigBuilder, fields: List[str], start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> Dict[str, List[str]]:
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time).limit(self.OPTION_VALUES_MAX_SIZE)

        # 为什么这里使用多线程，而不是构造多个 aggs？
        # 在性能差距不大的情况下，尽可能构造通用查询，便于后续屏蔽存储差异
        option_values: Dict[str, List[str]] = {}
        ThreadPool().map_ignore_exception(
            self._collect_option_values, [(q, queryset, field, option_values) for field in fields]
        )

        # UnifyQuery tag_values 目前还不支持 limit，此处进行截断，避免返回量大导致前端组件卡死的问题
        # 后续会支持 limit，并且请求速度会进一步加快，可以考虑放开一个更大的 limit
        return {field: values[: self.OPTION_VALUES_MAX_SIZE] for field, values in option_values.items()}

    @classmethod
    def _collect_option_values(
        cls, q: QueryConfigBuilder, queryset: UnifyQuerySet, field: str, option_values: Dict[str, List[str]]
    ):
        if q.using == cls.USING_LOG:
            q = q.metric(field=field, method="count").group_by(field)
        else:
            q = q.metric(field="bk_apm_count", method="count").tag_values(field).time_field("time")

        for bucket in queryset.add_query(q):
            option_values.setdefault(field, []).append(bucket[field])

    @classmethod
    def _get_data_page(
        cls,
        q: QueryConfigBuilder,
        queryset: UnifyQuerySet,
        select_fields: List[str],
        count_field: str,
        offset: int,
        limit: int,
    ) -> types.Page:
        def _fill_data():
            _q: QueryConfigBuilder = q.values(*select_fields)
            page_data["data"] = list(queryset.add_query(_q).offset(offset).limit(limit))

        page_data: Dict[str, Union[int, List[Dict[str, Any]]]] = {"total": 0}

        _fill_data()

        return page_data

    @classmethod
    def _translate_field(cls, field: str) -> str:
        return cls.KEY_REPLACE_FIELDS.get(field) or field

    @classmethod
    def _build_filters(cls, filters: Optional[List[types.Filter]]) -> Q:
        if not filters:
            return Q()

        q: Q = Q()
        for f in filters:
            if f["operator"] not in cls.operator_mapping:
                raise ValueError(_("不支持的查询操作符: %s") % (f['operator']))

            key = cls._translate_field(f["key"])
            # 更新 q，叠加查询条件
            q = cls.operator_mapping[f["operator"]](q, key, f["value"])

        return q

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        return q

    @classmethod
    def _get_time_range(
        cls, retention: int, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> Tuple[int, int]:
        now: int = int(datetime.datetime.now().timestamp())
        # 最早可查询时间
        earliest_start_time: int = now - int(datetime.timedelta(days=retention).total_seconds())

        # 开始时间不能小于 earliest_start_time
        start_time = max(earliest_start_time, start_time or earliest_start_time)
        # 结束时间不能大于 now
        end_time = min(now, end_time or now)

        # 通常我们会在页面拿到 TraceID 后便进行查询，「查询请求时间」可能 Trace 还未完成，前后补一个填充时间
        start_time = (start_time - cls.TIME_PADDING) * cls.TIME_FIELD_ACCURACY
        end_time = (end_time + cls.TIME_PADDING) * cls.TIME_FIELD_ACCURACY

        return start_time, end_time

    @classmethod
    def _add_filters_from_dsl(cls, q: QueryConfigBuilder, dsl: Dict[str, Any]) -> QueryConfigBuilder:
        logger.info("[add_query_string] dsl -> %s", dsl)
        try:
            filter_dict: Dict[str, Any] = dsl_to_filter_dict(dsl["query"])
            logger.info("[add_query_string] filter_dict -> %s", filter_dict)
            if filter_dict:
                return q.filter(dict_to_q(filter_dict))
        except Exception:  # pylint: disable=broad-except
            # 可忽略异常，仅打印 warn 日志
            logger.warning("[add_query_string] failed to parse dsl but skipped -> %s", dsl)

        query_string, nested_paths = cls._parse_query_string_from_dsl(dsl)
        logger.info("[add_query_string] query_string -> %s, nested_paths -> %s", query_string, nested_paths)
        return q.query_string(query_string, nested_paths)

    @classmethod
    def _parse_query_string_from_dsl(cls, dsl: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
        """
        【待废弃】在 dsl 中提取检索关键字，保留该逻辑主要是兼容前端的 lucene 查询，后续兼容不同 DB，该逻辑大概率会下掉
        :param dsl:
        :return:
        """
        try:
            return dsl["query"]["query_string"]["query"], {}
        except KeyError:
            pass

        try:
            should_list: List[Dict[str, Any]] = dsl["query"]["bool"]["should"]
        except KeyError:
            return "*", {}

        query_string: str = "*"
        nested_paths: Dict[str, str] = {}
        for should in should_list:
            try:
                nested_paths[should["nested"]["path"]] = should["nested"]["query"]["query_string"]["query"]
            except KeyError:
                try:
                    # handle case: {'should': [{'query_string': {'query': 'ListTrace'}}]}
                    query_string = should["query_string"]["query"]
                except KeyError:
                    continue

        return query_string, nested_paths

    @classmethod
    def _parse_ordering_from_dsl(cls, dsl: Dict[str, Any]) -> List[str]:
        """
        【待废弃】在 dsl 中提取字段排序信息
        :param dsl:
        :return:
        """

        ordering: List[str] = []
        try:
            for sort_item in dsl["sort"]:
                if isinstance(sort_item, str):
                    # handle case: 'start_time'
                    ordering.append(sort_item)

                elif isinstance(sort_item, dict):
                    for field, option in sort_item.items():
                        if isinstance(option, str):
                            # handle case: {'end_time': 'desc'}
                            ordering.append(f"{field} {option}")
                        elif isinstance(option, dict):
                            # handle case: {'hierarchy_count': {'order': 'desc'}}
                            ordering.append(f"{field} {option['order']}")
        except (KeyError, TypeError, IndexError):
            pass

        return ordering


class FakeQuery:
    def list(self, *args, **kwargs):
        return [], 0

    def __getattr__(self, item):
        return lambda *args, **kwargs: None
