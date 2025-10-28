"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property
from typing import Any

from django.db.models import Q

from bkmonitor.data_source import filter_dict_to_conditions, q_to_dict, q_to_conditions
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.apm import DEFAULT_DATA_LABEL, RPCMetricTag, CachedEnum
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.query_template import GLOBAL_BIZ_ID


from django.utils.translation import gettext_lazy as _

from .. import constants
from . import utils
from .base import QueryTemplateSet


class APMQueryTemplateName(CachedEnum):
    RPC_CALLEE_SUCCESS_RATE = "apm_rpc_callee_success_rate"
    RPC_CALLEE_AVG_TIME = "apm_rpc_callee_avg_time"
    RPC_CALLEE_P99 = "apm_rpc_callee_p99"
    RPC_CALLEE_REQ_TOTAL = "apm_rpc_callee_req_total"
    RPC_CALLEE_ERROR_CODE = "apm_rpc_callee_error_code"
    RPC_CALLER_SUCCESS_RATE = "apm_rpc_caller_success_rate"
    RPC_CALLER_AVG_TIME = "apm_rpc_caller_avg_time"
    RPC_CALLER_P99 = "apm_rpc_caller_p99"
    RPC_CALLER_REQ_TOTAL = "apm_rpc_caller_req_total"
    RPC_CALLER_ERROR_CODE = "apm_rpc_caller_error_code"
    CUSTOM_METRIC_PANIC = "apm_custom_metric_panic"
    SPAN_TOTAL = "apm_span_total"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.RPC_CALLEE_SUCCESS_RATE: _("[调用分析] 被调成功率（%）"),
                self.RPC_CALLEE_AVG_TIME: _("[调用分析] 被调平均耗时 (ms）"),
                self.RPC_CALLEE_P99: _("[调用分析] 被调 P99 耗时 (ms）"),
                self.RPC_CALLEE_REQ_TOTAL: _("[调用分析] 被调请求总数"),
                self.RPC_CALLEE_ERROR_CODE: _("[调用分析] 被调错误数"),
                self.RPC_CALLER_SUCCESS_RATE: _("[调用分析] 主调成功率（%）"),
                self.RPC_CALLER_AVG_TIME: _("[调用分析] 主调平均耗时 (ms）"),
                self.RPC_CALLER_P99: _("[调用分析] 主调 P99 耗时 (ms）"),
                self.RPC_CALLER_REQ_TOTAL: _("[调用分析] 主调请求总数"),
                self.RPC_CALLER_ERROR_CODE: _("[调用分析] 主调错误数"),
                self.CUSTOM_METRIC_PANIC: _("[自定义指标] 服务 Panic 次数"),
                self.SPAN_TOTAL: _("[调用链] Span 总数"),
            }.get(self, self.value)
        )


def _get_common_variables(
    group_by: list[str],
    related_metric_fields: list[str],
    is_need_functions: bool = True,
    is_need_threshold_value: bool = True,
) -> list[dict[str, Any]]:
    related_metrics: list[dict[str, str]] = [
        {"metric_field": metric_field, "metric_id": f"custom.{_TABLE}.{metric_field}"}
        for metric_field in related_metric_fields
    ]

    variables: list[dict[str, Any]] = [
        {
            "name": "GROUP_BY",
            "alias": "监控维度",
            "type": constants.VariableType.GROUP_BY.value,
            "config": {"default": group_by, "related_metrics": related_metrics},
            "description": "监控维度是指在监控数据中对数据进行分组的依据。",
        },
        {
            "name": "CONDITIONS",
            "alias": "维度过滤",
            "type": constants.VariableType.CONDITIONS.value,
            "config": {"related_metrics": related_metrics},
            "description": "维度过滤是指在监控数据中对数据进行筛选的条件。",
        },
    ]
    if is_need_functions:
        variables.append(
            {
                "name": "FUNCTIONS",
                "alias": "函数",
                "type": constants.VariableType.FUNCTIONS.value,
                "config": {"default": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}]},
                "description": "Oteam SDK 指标类型为 Counter，需要使用 increase 计算周期间差值，其他 SDK 请根据实际情况选择函数。",
            }
        )
    if is_need_threshold_value:
        variables.append(
            {
                "name": "ALARM_THRESHOLD_VALUE",
                "alias": "[整数] 告警起算值",
                "type": constants.VariableType.CONSTANTS.value,
                "config": {"default": "0"},
                "description": "当前请求量大于「告警起算值」时才进行检测，可用于避免在请求量较小的情况下触发告警。",
            }
        )

    return variables


def _qs_to_query_params(qs: UnifyQuerySet) -> dict[str, Any]:
    query_params: dict[str, Any] = qs.config
    for query_config in query_params["query_configs"]:
        query_config["where"].append("${CONDITIONS}")
        query_config["functions"].append("${FUNCTIONS}")
    return utils.format_query_params(query_params)


_TABLE: str = f"{DEFAULT_DATA_LABEL}.__default__"

_COMMON_BUILDER: QueryConfigBuilder = (
    QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))
    .data_label(DEFAULT_DATA_LABEL)
    .table(_TABLE)
    .interval(60)
    .group_by("${GROUP_BY}")
)

RPC_CALLEE_SUCCESS_RATE_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLEE_SUCCESS_RATE.value,
    "alias": APMQueryTemplateName.RPC_CALLEE_SUCCESS_RATE.label,
    "description": "被调成功率是指当前服务作为「服务提供方」，被其他服务调用时，请求成功数占总请求数的比例。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .metric(field="rpc_server_handled_total", method="SUM", alias="a")
            .conditions(q_to_conditions(Q(code_type="success")))
        )
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_server_handled_total", method="SUM", alias="b"))
        .expression("(a or b < bool 0) / (b > ${ALARM_THRESHOLD_VALUE}) * 100")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CALLER_SERVICE.value, RPCMetricTag.CALLEE_METHOD.value],
        related_metric_fields=["rpc_server_handled_total"],
    ),
    "unit": "percent",
}

RPC_CALLEE_AVG_TIME_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLEE_AVG_TIME.value,
    "alias": APMQueryTemplateName.RPC_CALLEE_AVG_TIME.label,
    "description": "被调平均耗时是指当前服务作为「服务提供方」，被其他服务调用时，从收到请求到返回结果的平均响应时间，单位为毫秒（ms）。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(_COMMON_BUILDER.alias("a").metric(field="rpc_server_handled_seconds_sum", method="SUM", alias="a"))
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_server_handled_seconds_count", method="SUM", alias="b"))
        .expression("b == 0 or (a / (b > ${ALARM_THRESHOLD_VALUE})) * 1000")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CALLER_SERVICE.value, RPCMetricTag.CALLEE_METHOD.value],
        related_metric_fields=["rpc_server_handled_seconds_count"],
    ),
    "unit": "ms",
}


RPC_CALLEE_P99_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLEE_P99.value,
    "alias": APMQueryTemplateName.RPC_CALLEE_P99.label,
    "description": "被调 P99 耗时是指当前服务作为「服务提供方」，被其他服务调用时，99% 的请求响应时间小于指标输出值，单位为毫秒（ms）。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .group_by("le")
            .func(_id="histogram_quantile", params=[{"id": "scalar", "value": 0.99}])
            .metric(field="rpc_server_handled_seconds_bucket", method="SUM", alias="a")
        )
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_server_handled_total", method="SUM", alias="b"))
        .expression("(b > bool ${ALARM_THRESHOLD_VALUE}) * a * 1000")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CALLER_SERVICE.value, RPCMetricTag.CALLEE_METHOD.value],
        related_metric_fields=["rpc_server_handled_total"],
    ),
    "unit": "ms",
}

RPC_CALLEE_REQ_TOTAL_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLEE_REQ_TOTAL.value,
    "alias": APMQueryTemplateName.RPC_CALLEE_REQ_TOTAL.label,
    "description": "被调请求总数是指当前服务作为「服务提供方」，被其他服务调用的请求总数量。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(_COMMON_BUILDER.alias("a").metric(field="rpc_server_handled_total", method="SUM", alias="a"))
        .expression("(a > bool ${ALARM_THRESHOLD_VALUE}) * a")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value], related_metric_fields=["rpc_server_handled_total"]
    ),
    "unit": "",
}

RPC_CALLEE_ERROR_CODE_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLEE_ERROR_CODE.value,
    "alias": APMQueryTemplateName.RPC_CALLEE_ERROR_CODE.label,
    "description": "被调错误数是指当前服务作为「服务提供方」，被其他服务调用时，请求出现错误的数量，默认按返回码（code）聚合。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .metric(field="rpc_server_handled_total", method="SUM", alias="a")
            .conditions(filter_dict_to_conditions(q_to_dict(Q(code_type__neq="success")), []))
        )
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_server_handled_total", method="SUM", alias="b"))
        .expression("(b > bool ${ALARM_THRESHOLD_VALUE}) * a")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CODE.value],
        related_metric_fields=["rpc_server_handled_total"],
    ),
    "unit": "",
}

RPC_CALLER_SUCCESS_RATE_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLER_SUCCESS_RATE.value,
    "alias": APMQueryTemplateName.RPC_CALLER_SUCCESS_RATE.label,
    "description": "主调成功率是指当前服务作为「调用方」，调用其他服务时，请求成功数占总请求数的比例。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .metric(field="rpc_client_handled_total", method="SUM", alias="a")
            .conditions(filter_dict_to_conditions(q_to_dict(Q(code_type="success")), []))
        )
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_client_handled_total", method="SUM", alias="b"))
        .expression("(a or b < bool 0) / (b > ${ALARM_THRESHOLD_VALUE}) * 100")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CALLEE_SERVICE.value, RPCMetricTag.CALLEE_METHOD.value],
        related_metric_fields=["rpc_client_handled_total"],
    ),
    "unit": "percent",
}

RPC_CALLER_AVG_TIME_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLER_AVG_TIME.value,
    "alias": APMQueryTemplateName.RPC_CALLER_AVG_TIME.label,
    "description": "主调平均耗时是指当前服务作为「调用方」，调用其他服务时，从发起请求到接收结果的平均响应时间，单位为毫秒（ms）。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(_COMMON_BUILDER.alias("a").metric(field="rpc_client_handled_seconds_sum", method="SUM", alias="a"))
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_client_handled_seconds_count", method="SUM", alias="b"))
        .expression("b == 0 or (a / (b > ${ALARM_THRESHOLD_VALUE})) * 1000")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CALLEE_SERVICE.value, RPCMetricTag.CALLEE_METHOD.value],
        related_metric_fields=["rpc_client_handled_seconds_count"],
    ),
    "unit": "ms",
}

RPC_CALLER_P99_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLER_P99.value,
    "alias": APMQueryTemplateName.RPC_CALLER_P99.label,
    "description": "主调 P99 耗时是指当前服务作为「调用方」，调用其他服务时，99% 的请求响应时间小于指标输出值，单位为毫秒（ms）。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .group_by("le")
            .func(_id="histogram_quantile", params=[{"id": "scalar", "value": 0.99}])
            .metric(field="rpc_client_handled_seconds_bucket", method="SUM", alias="a")
        )
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_client_handled_total", method="SUM", alias="b"))
        .expression("(b > bool ${ALARM_THRESHOLD_VALUE}) * a * 1000")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CALLEE_SERVICE.value, RPCMetricTag.CALLEE_METHOD.value],
        related_metric_fields=["rpc_client_handled_total"],
    ),
    "unit": "ms",
}

RPC_CALLER_REQ_TOTAL_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLER_REQ_TOTAL.value,
    "alias": APMQueryTemplateName.RPC_CALLER_REQ_TOTAL.label,
    "description": "主调请求总数是指当前服务作为「调用方」，调用其他服务的请求总数量。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(_COMMON_BUILDER.alias("a").metric(field="rpc_client_handled_total", method="SUM", alias="a"))
        .expression("(a > bool ${ALARM_THRESHOLD_VALUE}) * a")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value], related_metric_fields=["rpc_client_handled_total"]
    ),
    "unit": "",
}

RPC_CALLER_ERROR_CODE_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.RPC_CALLER_ERROR_CODE.value,
    "alias": APMQueryTemplateName.RPC_CALLER_ERROR_CODE.label,
    "description": "主调错误数是指当前服务作为「调用方」，调用其他服务时，请求出现错误的数量，默认按返回码（code）聚合。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .metric(field="rpc_client_handled_total", method="SUM", alias="a")
            .conditions(filter_dict_to_conditions(q_to_dict(Q(code_type__neq="success")), []))
        )
        .add_query(_COMMON_BUILDER.alias("b").metric(field="rpc_client_handled_total", method="SUM", alias="b"))
        .expression("(b > bool ${ALARM_THRESHOLD_VALUE}) * a")
    ),
    "variables": _get_common_variables(
        group_by=[RPCMetricTag.SERVICE_NAME.value, RPCMetricTag.CODE.value],
        related_metric_fields=["rpc_client_handled_total"],
    ),
    "unit": "",
}

CUSTOM_METRIC_PANIC_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.CUSTOM_METRIC_PANIC.value,
    "alias": APMQueryTemplateName.CUSTOM_METRIC_PANIC.label,
    "description": "服务 Panic 次数是指当前服务在运行过程中发生的 Panic 错误次数。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(_COMMON_BUILDER.alias("a").metric(field="trpc_PanicNum", method="SUM", alias="a"))
        .expression("a")
    ),
    "variables": _get_common_variables(
        group_by=[
            RPCMetricTag.SERVICE_NAME.value,
            RPCMetricTag.ENV_NAME.value,
            RPCMetricTag.NAMESPACE.value,
            RPCMetricTag.INSTANCE.value,
        ],
        related_metric_fields=["trpc_PanicNum"],
        is_need_threshold_value=False,
    ),
    "unit": "",
}

TRACE_SPAN_TOTAL_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": APMQueryTemplateName.SPAN_TOTAL.value,
    "alias": APMQueryTemplateName.SPAN_TOTAL.label,
    "description": "调用链 Span 数是指在指定时间范围内所上报的 Span 总数。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(_COMMON_BUILDER.alias("a").metric(field="bk_apm_count", method="SUM", alias="a"))
        .expression("a")
    ),
    "variables": _get_common_variables(
        group_by=["service_name"],
        related_metric_fields=["bk_apm_count"],
        is_need_functions=False,
        is_need_threshold_value=False,
    ),
    "unit": "",
}


class APMQueryTemplateSet(QueryTemplateSet):
    """APM 内置查询模板集"""

    NAMESPACE: str = constants.Namespace.APM.value

    QUERY_TEMPLATES: list[dict[str, Any]] = [
        RPC_CALLEE_SUCCESS_RATE_QUERY_TEMPLATE,
        RPC_CALLEE_AVG_TIME_QUERY_TEMPLATE,
        RPC_CALLEE_P99_QUERY_TEMPLATE,
        RPC_CALLEE_REQ_TOTAL_TEMPLATE,
        RPC_CALLEE_ERROR_CODE_QUERY_TEMPLATE,
        RPC_CALLER_SUCCESS_RATE_QUERY_TEMPLATE,
        RPC_CALLER_AVG_TIME_QUERY_TEMPLATE,
        RPC_CALLER_P99_QUERY_TEMPLATE,
        RPC_CALLER_REQ_TOTAL_TEMPLATE,
        RPC_CALLER_ERROR_CODE_QUERY_TEMPLATE,
        CUSTOM_METRIC_PANIC_QUERY_TEMPLATE,
        TRACE_SPAN_TOTAL_QUERY_TEMPLATE,
    ]
