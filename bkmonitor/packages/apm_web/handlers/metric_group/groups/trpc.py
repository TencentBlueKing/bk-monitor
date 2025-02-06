# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import functools
from typing import Any, Callable, Dict, List, Optional, Set

from django.db.models import Q
from django.utils.functional import cached_property

from apm_web.metric.constants import SeriesAliasType
from bkmonitor.data_source import filter_dict_to_conditions, q_to_dict
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.apm import MetricTemporality, TRPCMetricTag

from .. import base, define

SUCCESS_CODES: List[str] = ["0", "ret_0"]


class TRPCMetricField:
    # 主调
    # 请求数
    RPC_CLIENT_HANDLED_TOTAL: str = "rpc_client_handled_total"
    # 请求时间
    RPC_CLIENT_HANDLED_SECONDS_SUM: str = "rpc_client_handled_seconds_sum"
    # 请求数
    RPC_CLIENT_HANDLED_SECONDS_COUNT: str = "rpc_client_handled_seconds_count"
    # 分桶
    RPC_CLIENT_HANDLED_SECONDS_BUCKET: str = "rpc_client_handled_seconds_bucket"

    # 被调
    # 请求数
    RPC_SERVER_HANDLED_TOTAL: str = "rpc_server_handled_total"
    # 请求时间
    RPC_SERVER_HANDLED_SECONDS_SUM: str = "rpc_server_handled_seconds_sum"
    # 请求数
    RPC_SERVER_HANDLED_SECONDS_COUNT: str = "rpc_server_handled_seconds_count"
    # 分桶
    RPC_SERVER_HANDLED_SECONDS_BUCKET: str = "rpc_server_handled_seconds_bucket"


class CodeType:
    SUCCESS: str = "success"
    TIMEOUT: str = "timeout"
    EXCEPTION: str = "exception"


class TrpcMetricGroup(base.BaseMetricGroup):
    # tRPC-Go Recovery 插件写入指标，通用框架指标，和上报 SDK 无关。
    PANIC_METRIC_FIELD: str = "trpc_PanicNum"

    METRIC_FIELDS: Dict[str, Dict[str, str]] = {
        SeriesAliasType.CALLER.value: {
            "rpc_handled_total": TRPCMetricField.RPC_CLIENT_HANDLED_TOTAL,
            "rpc_handled_seconds_sum": TRPCMetricField.RPC_CLIENT_HANDLED_SECONDS_SUM,
            "rpc_handled_seconds_count": TRPCMetricField.RPC_CLIENT_HANDLED_SECONDS_COUNT,
            "rpc_handled_seconds_bucket": TRPCMetricField.RPC_CLIENT_HANDLED_SECONDS_BUCKET,
        },
        SeriesAliasType.CALLEE.value: {
            "rpc_handled_total": TRPCMetricField.RPC_SERVER_HANDLED_TOTAL,
            "rpc_handled_seconds_sum": TRPCMetricField.RPC_SERVER_HANDLED_SECONDS_SUM,
            "rpc_handled_seconds_count": TRPCMetricField.RPC_SERVER_HANDLED_SECONDS_COUNT,
            "rpc_handled_seconds_bucket": TRPCMetricField.RPC_SERVER_HANDLED_SECONDS_BUCKET,
        },
    }

    DEFAULT_INTERVAL = 60

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        group_by: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, group_by, filter_dict, **kwargs)
        self.kind: str = kwargs.get("kind") or SeriesAliasType.CALLER.value
        self.temporality: str = kwargs.get("temporality") or MetricTemporality.CUMULATIVE
        self.ret_code_as_exception: bool = kwargs.get("ret_code_as_exception") or False
        self.time_shift: Optional[str] = kwargs.get("time_shift")
        # 预留 interval 可配置入口
        self.interval = self.DEFAULT_INTERVAL

        self.instant: bool = True
        if self.metric_helper.TIME_FIELD in self.group_by:
            self.group_by.remove(self.metric_helper.TIME_FIELD)
            self.instant: bool = False

    def handle(self, calculation_type: str, **kwargs) -> List[Dict[str, Any]]:
        return self.get_calculation_method(calculation_type)(**kwargs)

    def query_config(self, calculation_type: str, **kwargs) -> Dict[str, Any]:
        return self._get_qs(calculation_type).query_config

    class Meta:
        name = define.GroupEnum.TRPC

    def get_calculation_method(self, calculation_type: str) -> Callable[..., List[Dict[str, Any]]]:
        support_calculation_methods: Dict[str, Callable[..., List[Dict[str, Any]]]] = {
            define.CalculationType.REQUEST_TOTAL: self._request_total,
            define.CalculationType.SUCCESS_RATE: functools.partial(self._request_code_rate, CodeType.SUCCESS),
            define.CalculationType.TIMEOUT_RATE: functools.partial(self._request_code_rate, CodeType.TIMEOUT),
            define.CalculationType.EXCEPTION_RATE: functools.partial(self._request_code_rate, CodeType.EXCEPTION),
            define.CalculationType.AVG_DURATION: self._avg_duration,
            define.CalculationType.P50_DURATION: functools.partial(self._histogram_quantile_duration, 0.50),
            define.CalculationType.P95_DURATION: functools.partial(self._histogram_quantile_duration, 0.95),
            define.CalculationType.P99_DURATION: functools.partial(self._histogram_quantile_duration, 0.99),
            define.CalculationType.TOP_N: self._top_n,
            define.CalculationType.BOTTOM_N: self._bottom_n,
        }
        if calculation_type not in support_calculation_methods:
            raise ValueError(f"Unsupported calculation type -> {calculation_type}")
        return support_calculation_methods[calculation_type]

    def _is_cumulative_metric(self) -> bool:
        """指标类型为「累加」时返回 True"""
        return self.temporality == MetricTemporality.CUMULATIVE

    @cached_property
    def _used_labels(self) -> List[str]:
        """返回使用到的指标维度字段"""
        used_labels: Set[str] = set(self.group_by)
        for cond in filter_dict_to_conditions(self.filter_dict, []):
            used_labels.add(cond.get("key") or "")
        return list(used_labels)

    def _add_metric(
        self, q: QueryConfigBuilder, metric: str, method: str, alias: Optional[str] = ""
    ) -> QueryConfigBuilder:
        """添加一个指标到查询表达式
        处理流程：
          1）[可选] 路由到相应的预计算指标。
          2）累加（Cumulative）类型指标统一增加 increase 处理。
        """
        result: Dict[str, Any] = {"table_id": self.metric_helper.table_id, "metric": metric, "is_hit": False}
        if self.pre_calculate_helper:
            result: Dict[str, str] = self.pre_calculate_helper.router(
                self.metric_helper.table_id, metric, used_labels=self._used_labels
            )

        q = q.table(result["table_id"]).metric(result["metric"], method, alias).alias(alias)
        if self._is_cumulative_metric() and not result["is_hit"]:
            q = q.func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])

        return q

    def q(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> QueryConfigBuilder:
        # 如果是求瞬时量，那么整个时间范围是作为一个区间
        q: QueryConfigBuilder = (
            self.metric_helper.q.group_by(*self.group_by).interval(self.interval).filter(self._filter_dict_to_q())
        )

        if self.time_shift:
            q = q.func(_id="time_shift", params=[{"id": "n", "value": self.time_shift}])

        if self.instant:
            interval: int = self.metric_helper.get_interval(start_time, end_time)
            # 背景：统计一段时间内的黄金指标（瞬时量）
            # sum_over_time(sum(increase(xxx[1m]))[window:step]) 可以解决数据刚上报、重启场景的差值计算不准确问题。
            q = q.func(
                _id="sum_over_time",
                # window: sum_over_time 区间左闭右闭，左侧减去 1s 变成左闭右开，确保一个 interval 只有一个点。
                # step：精度，由于是求 window 内所有点之和，step 须和内层 interval 对齐。
                # 必须显式传入 step：不指定 step 会参考 interval 自动取值，这意味着不同查询引擎可能默认行为不一致。
                # refer：https://prometheus.io/blog/2019/01/28/subquery-support/
                params=[{"id": "window", "value": f"{interval - 1}s"}, {"id": "step", "value": f"{self.interval}s"}],
            )

        return q

    def qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None):
        qs: UnifyQuerySet = self.metric_helper.time_range_qs(start_time, end_time)
        if self.instant:
            return qs.instant(align_interval=self.interval * self.metric_helper.TIME_FIELD_ACCURACY)
        return qs.limit(self.metric_helper.MAX_DATA_LIMIT)

    def _panic_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None):
        q: QueryConfigBuilder = (
            self.q(start_time, end_time).alias("a").metric(field=self.PANIC_METRIC_FIELD, method="SUM", alias="a")
        )
        return self.qs(start_time, end_time).add_query(q).expression("a")

    def _request_total_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        q: QueryConfigBuilder = self._add_metric(
            self.q(start_time, end_time), self.METRIC_FIELDS[self.kind]["rpc_handled_total"], "SUM", "a"
        )
        # a != 0：非时序计算反应的是一段时间内的统计值，不需要展示请求量为 0 的数据。
        return self.qs(start_time, end_time).add_query(q).expression("a != 0")

    def _request_total(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        return list(self._request_total_qs(start_time, end_time))

    def _avg_duration_qs(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        sum_q: QueryConfigBuilder = self._add_metric(
            self.q(start_time, end_time), self.METRIC_FIELDS[self.kind]["rpc_handled_seconds_sum"], "SUM", "a"
        )
        count_q: QueryConfigBuilder = self._add_metric(
            self.q(start_time, end_time), self.METRIC_FIELDS[self.kind]["rpc_handled_seconds_count"], "SUM", "b"
        )
        # b == 0：分母为 0 需短路返回
        return self.qs(start_time, end_time).add_query(sum_q).add_query(count_q).expression("b == 0 or (a / b) * 1000")

    def _avg_duration(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[Dict[str, Any]]:
        return list(self._avg_duration_qs(start_time, end_time))

    def _histogram_quantile_duration_qs(
        self, scalar: float, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> UnifyQuerySet:
        q: QueryConfigBuilder = (
            self.q(start_time, end_time)
            .group_by("le")
            .func(_id="histogram_quantile", params=[{"id": "scalar", "value": scalar}])
        )
        q = self._add_metric(q, self.METRIC_FIELDS[self.kind]["rpc_handled_seconds_bucket"], "SUM", "a")
        return self.qs(start_time, end_time).add_query(q).expression("a * 1000")

    def _histogram_quantile_duration(
        self, scalar: float, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return list(self._histogram_quantile_duration_qs(scalar, start_time, end_time))

    def _code_redefined(self, code_type: str, q: QueryConfigBuilder) -> QueryConfigBuilder:
        if not self.ret_code_as_exception:
            return q.filter(code_type__eq=code_type)

        if code_type == CodeType.EXCEPTION:
            return q.filter(code__neq=SUCCESS_CODES, code_type__neq=CodeType.TIMEOUT)
        elif code_type == CodeType.SUCCESS:
            return q.filter(code__eq=SUCCESS_CODES)

        return q.filter(code_type__eq=code_type)

    def _request_code_rate_qs(
        self, code_type: str, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> UnifyQuerySet:
        code_q: QueryConfigBuilder = self._add_metric(
            self.q(start_time, end_time), self.METRIC_FIELDS[self.kind]["rpc_handled_total"], "SUM", "a"
        )
        code_q: QueryConfigBuilder = self._code_redefined(code_type, code_q)

        total_q: QueryConfigBuilder = self._add_metric(
            self.q(start_time, end_time), self.METRIC_FIELDS[self.kind]["rpc_handled_total"], "SUM", "b"
        )
        return (
            self.qs(start_time, end_time)
            .add_query(code_q)
            .add_query(total_q)
            # 单个错误码的占比为 100% or 0% 时，对时间序列来说，是某段时间内不出现这条线，即无数据。
            # 上述情况会导致比率计算缺少这部分数据点，即使通过 1-a / b 的模式，也只能做到 0% 或 100% 有数据，无法两边都满足。
            # 这会导致 group by 场景下，计算不出错误率为 0% 、错误率 100% 的线。
            # 可以借助 b 一定存在的情况，将 b 的维度对齐到 a，确保按字段聚合时，能 group by 出所有错误率 100% 或 0% 的数据。
            .expression("(a or b < bool 0) /  b * 100")
        )

    def _request_code_rate(
        self, code_type: str, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return list(self._request_code_rate_qs(code_type, start_time, end_time))

    def _get_qs(self, qs_type: str, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        return {
            define.CalculationType.REQUEST_TOTAL: self._request_total_qs,
            define.CalculationType.SUCCESS_RATE: functools.partial(self._request_code_rate_qs, CodeType.SUCCESS),
            define.CalculationType.TIMEOUT_RATE: functools.partial(self._request_code_rate_qs, CodeType.TIMEOUT),
            define.CalculationType.EXCEPTION_RATE: functools.partial(self._request_code_rate_qs, CodeType.EXCEPTION),
            define.CalculationType.AVG_DURATION: self._avg_duration_qs,
            define.CalculationType.P99_DURATION: functools.partial(self._histogram_quantile_duration_qs, 0.99),
            define.CalculationType.PANIC: self._panic_qs,
        }[qs_type](start_time, end_time)

    def _top_n(
        self, qs_type: str, limit: int, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        qs: UnifyQuerySet = self._get_qs(qs_type, start_time, end_time)
        if self.instant:
            return list(qs.func(_id="topk", params=[{"value": limit}]))

        # 时间聚合场景，需要排序找 TopN
        records: List[Dict[str, Any]] = []
        for record in qs:
            if record.get("_result_") is None:
                continue
            records.append(record)

        return sorted(records, key=lambda r: -r["_result_"])[:limit]

    def _bottom_n(
        self, qs_type: str, limit: int, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return list(self._get_qs(qs_type, start_time, end_time).func(_id="bottomk", params=[{"value": limit}]))

    def fetch_server_list(
        self,
        filter_dict: Optional[Dict[str, Any]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[str]:
        return self.metric_helper.get_field_option_values_by_groups(
            params_list=[
                {
                    "metric_field": TRPCMetricField.RPC_CLIENT_HANDLED_TOTAL,
                    "field": TRPCMetricTag.CALLER_SERVER,
                    "filter_dict": filter_dict,
                },
                {
                    "metric_field": TRPCMetricField.RPC_SERVER_HANDLED_TOTAL,
                    "field": TRPCMetricTag.CALLEE_SERVER,
                    "filter_dict": filter_dict,
                },
                {
                    "metric_field": TRPCMetricField.RPC_SERVER_HANDLED_TOTAL,
                    "field": TRPCMetricTag.SERVICE_NAME,
                    "filter_dict": filter_dict,
                },
                {
                    "metric_field": TRPCMetricField.RPC_CLIENT_HANDLED_TOTAL,
                    "field": TRPCMetricTag.SERVICE_NAME,
                    "filter_dict": filter_dict,
                },
            ],
            start_time=start_time,
            end_time=end_time,
        )

    def get_server_config(
        self, server: str, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> Dict[str, Any]:
        # 根据特殊维度探测上报方式，不同上报方式需要采用不同的指标计算/筛选方式
        apps: List[str] = self.metric_helper.get_field_option_values_by_groups(
            params_list=[
                {
                    "metric_field": TRPCMetricField.RPC_CLIENT_HANDLED_TOTAL,
                    "field": TRPCMetricTag.APP,
                    "filter_dict": q_to_dict(
                        Q(**{f"{TRPCMetricTag.CALLER_SERVER}__eq": server})
                        | Q(**{f"{TRPCMetricTag.SERVICE_NAME}__eq": server})
                    ),
                },
                {
                    "metric_field": TRPCMetricField.RPC_SERVER_HANDLED_TOTAL,
                    "field": TRPCMetricTag.APP,
                    "filter_dict": q_to_dict(
                        Q(**{f"{TRPCMetricTag.CALLEE_SERVER}__eq": server})
                        | Q(**{f"{TRPCMetricTag.SERVICE_NAME}__eq": server})
                    ),
                },
            ],
            start_time=start_time,
            end_time=end_time,
        )

        temporality: str = MetricTemporality.CUMULATIVE if apps else MetricTemporality.DELTA
        return MetricTemporality.get_metric_config(temporality=temporality)
