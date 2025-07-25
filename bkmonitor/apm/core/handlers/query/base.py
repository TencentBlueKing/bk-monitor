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
from collections.abc import Callable
from typing import Any

from django.db.models import Q
from django.utils.functional import cached_property, classproperty
from django.utils.translation import gettext_lazy as _

from apm import types
from apm.constants import AggregatedMethod
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import ApmDataSourceConfigBase, MetricDataSource, TraceDataSource
from apm.utils.base import get_bar_interval_number
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OperatorGroupRelation
from constants.data_source import DataSourceLabel, DataTypeLabel

logger = logging.getLogger("apm")


class FilterOperator:
    # 走ES查询可以使用的操作符
    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"
    NOT_LIKE = "not_like"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"

    UNIFY_QUERY_OPERATOR_MAPPING = {
        EXISTS: "exists",
        NOT_EXISTS: "nexists",
        EQUAL: "eq",
        NOT_EQUAL: "neq",
        LIKE: "include",
        NOT_LIKE: "exclude",
        GT: "gt",
        LT: "lt",
        GTE: "gte",
        LTE: "lte",
    }

    UNIFY_QUERY_WILDCARD_OPERATOR_MAPPING = {
        LIKE: "wildcard",
        NOT_LIKE: "nwildcard",
    }

    @classproperty
    def operator_handler_mapping(cls) -> dict[str, Callable[[QueryConfigBuilder, str, types.FilterValue], Q]]:
        return {
            cls.BETWEEN: cls._between_operator_handler,
            cls.EXISTS: cls._existence_operator_handler,
            cls.NOT_EXISTS: cls._existence_operator_handler,
        }

    @classmethod
    def _between_operator_handler(
        cls, q: Q, operator: str, field: str, value: types.FilterValue, options: dict[str, Any]
    ) -> Q:
        return q & Q(**{f"{field}__gte": value[0], f"{field}__lt": value[1]})

    @classmethod
    def _default_operator_handler(
        cls, q: Q, operator: str, field: str, value: types.FilterValue, options: dict[str, Any]
    ) -> Q:
        # 字段不等于 "" 的情况下，需要过滤出字段存在的情况
        if operator == FilterOperator.NOT_EQUAL and "" in value:
            q &= Q(**{f"{field}__{FilterOperator.EXISTS}": [""]})

        # 操作符映射，如果是通配符查询的话需要映射到特定操作符
        if operator in cls.UNIFY_QUERY_WILDCARD_OPERATOR_MAPPING and options.get("is_wildcard"):
            operator = cls.UNIFY_QUERY_WILDCARD_OPERATOR_MAPPING[operator]
        else:
            operator = cls.UNIFY_QUERY_OPERATOR_MAPPING[operator]

        # 处理组间关系查询
        if options.get("group_relation") == OperatorGroupRelation.AND:
            result_q = Q()
            for v in value:
                result_q &= Q(**{f"{field}__{operator}": v})
        else:
            result_q = Q(**{f"{field}__{operator}": value})

        return q & result_q

    @classmethod
    def _existence_operator_handler(
        cls, q: Q, operator: str, field: str, value: types.FilterValue, options: dict[str, Any]
    ) -> Q:
        """
        处理存在性相关操作符 (exists/not exists)
        """
        operator = cls.UNIFY_QUERY_OPERATOR_MAPPING[operator]
        return q & Q(**{f"{field}__{operator}": [""]})

    @classmethod
    def get_handler(cls, operator: str) -> Q:
        if operator in cls.UNIFY_QUERY_OPERATOR_MAPPING or operator in cls.operator_handler_mapping:
            return cls.operator_handler_mapping.get(operator, cls._default_operator_handler)
        raise ValueError(_(f"不支持的查询操作符: {operator}"))


class LogicSupportOperator:
    # 走特殊逻辑可以使用的操作符
    LOGIC = "logic"


class BaseQuery:
    USING_LOG: tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_APM)

    USING_METRIC: tuple[str, str] = (DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM)

    DEFAULT_DATASOURCE_CONFIGS: dict[str, dict[str, Any]] = {
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

    # 查询字段映射
    KEY_REPLACE_FIELDS: dict[str, str] = {}

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        retention: int,
        overwrite_datasource_configs: dict[str, dict[str, Any]] | None = None,
    ):
        self.bk_biz_id: int = bk_biz_id
        self.app_name: str = app_name
        self.retention: int = retention
        self.overwrite_datasource_configs: dict[str, dict[str, Any]] = overwrite_datasource_configs or {}

    @cached_property
    def _datasource_configs(self) -> dict[str, dict[str, Any]]:
        datasource_configs: dict[str, dict[str, Any]] = copy.deepcopy(self.DEFAULT_DATASOURCE_CONFIGS)
        for datasource_type, conf in self.overwrite_datasource_configs.items():
            datasource_configs.setdefault(datasource_type, {}).update(conf)
        return datasource_configs

    def _get_table_id(self, datasource_type: str) -> str:
        get_table_id_func: Callable[[int, str], str] = self._datasource_configs[datasource_type]["get_table_id_func"]
        return get_table_id_func(self.bk_biz_id, self.app_name)

    def _get_q(self, datasource_type: str):
        datasource_config: dict[str, Any] = self._datasource_configs[datasource_type]
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

    def time_range_queryset(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        using_scope: bool = True,
    ) -> UnifyQuerySet:
        start_time, end_time = self._get_time_range(self.retention, start_time, end_time)
        queryset: UnifyQuerySet = UnifyQuerySet().start_time(start_time).end_time(end_time)
        if using_scope:
            # 默认仅查询本业务下的数据
            return queryset.scope(self.bk_biz_id)
        return queryset

    def _query_option_values(
        self,
        start_time: int,
        end_time: int,
        fields: list[str],
        q: QueryConfigBuilder,
        limit: int,
    ) -> dict[str, list[str]]:
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time).limit(limit)

        # 为什么这里使用多线程，而不是构造多个 aggs？
        # 在性能差距不大的情况下，尽可能构造通用查询，便于后续屏蔽存储差异
        # 默认构建字段的空列表，字段无候选项时候返回空列表
        option_values: dict[str, list[str]] = {field: [] for field in fields}
        ThreadPool().map_ignore_exception(
            self._collect_option_values, [(q, queryset, field, option_values) for field in fields]
        )
        return option_values

    @classmethod
    def _collect_option_values(
        cls, q: QueryConfigBuilder, queryset: UnifyQuerySet, field: str, option_values: dict[str, list[str]]
    ):
        if q.using == cls.USING_LOG:
            q = q.metric(field=field, method="count", alias="a").group_by(field)
            queryset = queryset.time_agg(False).instant()
        else:
            q = q.metric(field="bk_apm_count", method="count").tag_values(field).time_field("time")

        for bucket in queryset.add_query(q):
            # 指标来源没有 _result_，需要先判断。
            if "_result_" in bucket and bucket["_result_"] == 0:
                continue
            option_values[field].append(bucket[field])

    @classmethod
    def _get_data_page(
        cls,
        q: QueryConfigBuilder,
        queryset: UnifyQuerySet,
        select_fields: list[str],
        count_field: str,
        offset: int,
        limit: int,
    ) -> types.Page:
        def _fill_data():
            _q: QueryConfigBuilder = q.values(*select_fields)
            page_data["data"] = list(queryset.add_query(_q).offset(offset).limit(limit))

        page_data: dict[str, int | list[dict[str, Any]]] = {"total": 0}

        _fill_data()

        return page_data

    @classmethod
    def _translate_field(cls, field: str) -> str:
        return cls.KEY_REPLACE_FIELDS.get(field) or field

    @classmethod
    def _build_filters(cls, filters: list[types.Filter] | None) -> Q:
        if not filters:
            return Q()

        q: Q = Q()
        for f in filters:
            operator = f["operator"]
            key = cls._translate_field(f["key"])
            # 更新 q，叠加查询条件
            if operator == LogicSupportOperator.LOGIC:
                q = cls._add_logic_filter(q, key, f["value"])
            else:
                q = FilterOperator.get_handler(operator)(q, operator, key, f["value"], f.get("options", {}))
        return q

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        return q

    @classmethod
    def _get_time_range(
        cls, retention: int, start_time: int | None = None, end_time: int | None = None
    ) -> tuple[int, int]:
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

    def build_query_q(self, filters: list[types.Filter], query_string: str) -> QueryConfigBuilder:
        return self.q.filter(self._build_filters(filters)).query_string(query_string)

    def _query_field_topk(
        self, q: QueryConfigBuilder, start_time: int, end_time: int, field: str, limit: int
    ) -> list[dict[str, Any]]:
        q: QueryConfigBuilder = q.metric(field=field, method="COUNT", alias="a").group_by(field).order_by("_value desc")
        queryset = self.time_range_queryset(start_time, end_time).add_query(q).time_agg(False).instant().limit(limit)
        try:
            field_topk_values = list(queryset)
        except Exception as e:
            logger.warning("failed to query field %s topk, error: %s", field, e)
            raise ValueError(_(f"字段 {field} topk值查询出错"))
        # 去除0值和兜底排序
        return sorted(
            [topk_item for topk_item in field_topk_values if topk_item["_result_"] > 0],
            key=lambda item: item["_result_"],
            reverse=True,
        )

    def _query_total(self, q: QueryConfigBuilder, start_time: int, end_time: int) -> int:
        q: QueryConfigBuilder = q.metric(field="_index", method="COUNT", alias="a")
        queryset = self.time_range_queryset(start_time, end_time).add_query(q).time_agg(False).instant().limit(1)
        try:
            return list(queryset)[0]["_result_"]
        except (IndexError, KeyError) as exc:
            logger.warning("failed to query total, err -> %s", exc)
            raise ValueError(_("总记录数查询出错"))

    def _query_field_aggregated_value(
        self, q: QueryConfigBuilder, start_time: int, end_time: int, field: str, method: str
    ) -> int | float:
        """
        查询字段聚合值
        """
        queryset = (
            self.time_range_queryset(start_time, end_time)
            .add_query(q.metric(field=field, method=method, alias="a"))
            .time_agg(False)
            .instant()
            .limit(1)
        )
        try:
            return list(queryset)[0]["_result_"]
        except (IndexError, KeyError) as exc:
            logger.warning("failed to query field %s with method %s, error: %s", field, method, exc)
            raise ValueError(_(f"字段 {field} 使用 {method} 方法聚合值查询出错"))

    def query_graph_config(self, start_time, end_time, field, filters: list[types.Filter], query_string: str):
        """
        获取查询配置
        """
        q: QueryConfigBuilder = (
            self.build_query_q(filters, query_string)
            .interval(get_bar_interval_number(start_time, end_time))
            .metric(field=field, method=AggregatedMethod.COUNT.value, alias="a")
            .group_by(field)
        )
        return self.time_range_queryset(start_time, end_time).add_query(q).instant().time_agg(False).config


class FakeQuery:
    def list(self, *args, **kwargs):
        return [], 0

    def __getattr__(self, item):
        return lambda *args, **kwargs: None
