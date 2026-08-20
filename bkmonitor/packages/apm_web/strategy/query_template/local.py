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

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.query_template.builtin import QueryTemplateSet, utils
from bkmonitor.query_template.constants import Namespace, VariableType
from constants.apm import CachedEnum, K8SMetricTag
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.query_template import GLOBAL_BIZ_ID

from django.utils.translation import gettext_lazy as _


def _qs_to_query_params(qs: UnifyQuerySet) -> dict[str, Any]:
    return utils.format_query_params(qs.config)


class LocalQueryTemplateName(CachedEnum):
    RPC_PANIC_LOG = "apm_rpc_panic_log"
    TRACE_SPAN_TOTAL = "apm_trace_span_total"
    LOG_TOTAL = "apm_log_total"
    K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO = "k8s_memory_limit_usage_container_ratio"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.RPC_PANIC_LOG: _("服务 Panic 日志数"),
                self.TRACE_SPAN_TOTAL: _("调用链 Span 数"),
                self.LOG_TOTAL: _("日志数"),
                self.K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO: _("[容器] 内存高负载 Pod 占比（%）"),
            }.get(self, self.value)
        )


RPC_PANIC_LOG_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.RPC_PANIC_LOG.value,
    "alias": LocalQueryTemplateName.RPC_PANIC_LOG.label,
    "description": str(_("服务 Panic 日志是指当前服务在运行过程中发生的 Panic 所记录的堆栈日志。")),
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_LOG_SEARCH))
            .table("${INDEX_SET_ID}")
            .index_set_id("${INDEX_SET_ID}")
            .interval(60)
            .group_by("resource.server", "resource.env", "resource.instance")
            .metric(field="_index", method="COUNT", alias="a")
            .conditions([{"key": "resource.server", "method": "eq", "value": ["${SERVICE_NAME}"], "condition": "and"}])
            .query_string("${QUERY_STRING}")
        )
        .expression("a")
    ),
    "variables": [
        {
            "name": "INDEX_SET_ID",
            "alias": str(_("日志索引集 ID")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("日志索引集 ID")),
        },
        {
            "name": "SERVICE_NAME",
            "alias": str(_("服务名称")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("服务名")),
        },
        {
            "name": "QUERY_STRING",
            "alias": str(_("日志关键字")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "\\\\[PANIC\\\\]"},
            "description": str(_("用于检索 Panic 的日志关键字。")),
        },
    ],
}

TRACE_SPAN_TOTAL_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.TRACE_SPAN_TOTAL.value,
    "alias": LocalQueryTemplateName.TRACE_SPAN_TOTAL.label,
    "description": str(_("调用链 Span 数是指在指定时间范围内所上报的 Span 总数。")),
    "table": "",
    "query_configs": [
        {
            "table": "",
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": "a",
            "interval": 60,
            "promql": "sum(count_over_time(bklog:bklog_index_set_${INDEX_SET_ID}:"
            '_index{resource__bk_46__service__bk_46__name="${SERVICE_NAME}"}[1m])) or vector(0)',
        }
    ],
    "variables": [
        {
            "name": "INDEX_SET_ID",
            "alias": str(_("日志索引集 ID")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("日志索引集 ID")),
        },
        {
            "name": "SERVICE_NAME",
            "alias": str(_("服务名称")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("服务名")),
        },
    ],
}

LOG_TOTAL_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.LOG_TOTAL.value,
    "alias": LocalQueryTemplateName.LOG_TOTAL.label,
    "description": str(_("日志数是指在指定时间范围内所上报的日志总数。")),
    "query_configs": [
        {
            "table": "",
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": "a",
            "interval": 60,
            # 为什么用 PromQL？
            # 目前日志数据源不支持 or vector(0) 的补 0 写法，暂时通过 PromQL 直接复用 UnifyQuery 的能力。
            # 等后续 SaaS 数据源统一切换到 UnifyQuery 时，改回结构体。
            "promql": "sum(count_over_time(bklog:bklog_index_set_${INDEX_SET_ID}:"
            '_index{resource__bk_46__service__bk_46__name="${SERVICE_NAME}"}[1m])) or vector(0)',
        }
    ],
    "variables": [
        {
            "name": "INDEX_SET_ID",
            "alias": str(_("日志索引集 ID")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("日志索引集 ID")),
        },
        {
            "name": "SERVICE_NAME",
            "alias": str(_("服务名称")),
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "<无需填写，下发时自动补充>"},
            "description": str(_("服务名")),
        },
    ],
}

_MEMORY_USAGE_METRIC: str = "container_memory_working_set_bytes"
_MEMORY_LIMIT_METRIC: str = "kube_pod_container_resource_limits_memory_bytes"
_POD_DIMENSIONS: str = ", ".join(
    [
        K8SMetricTag.BCS_CLUSTER_ID.value,
        K8SMetricTag.NAMESPACE.value,
        K8SMetricTag.POD_NAME.value,
    ]
)
_CONTAINER_SELECTOR: str = 'container_name!="POD",${CONDITIONS}'
_POD_MEMORY_USAGE_PROMQL: str = f"sum by ({_POD_DIMENSIONS}) ({_MEMORY_USAGE_METRIC}{{{_CONTAINER_SELECTOR}}})"
_POD_MEMORY_LIMIT_PROMQL: str = f"sum by ({_POD_DIMENSIONS}) ({_MEMORY_LIMIT_METRIC}{{{_CONTAINER_SELECTOR}}})"
_POD_MEMORY_USAGE_RATIO_PROMQL: str = f"({_POD_MEMORY_USAGE_PROMQL} / {_POD_MEMORY_LIMIT_PROMQL}) * 100"
_MEMORY_HIGH_LOAD_POD_RATIO_PROMQL: str = (
    f"sum by (${{GROUP_BY}}) (({_POD_MEMORY_USAGE_RATIO_PROMQL}) > bool ${{MEMORY_USAGE_THRESHOLD}}) "
    f"/ count by (${{GROUP_BY}}) ({_POD_MEMORY_LIMIT_PROMQL}) * 100"
)
_MEMORY_RELATED_METRICS: list[dict[str, str]] = [
    {"metric_field": metric, "metric_id": f"{DataSourceLabel.BK_MONITOR_COLLECTOR}..{metric}"}
    for metric in [_MEMORY_USAGE_METRIC, _MEMORY_LIMIT_METRIC]
]

K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": LocalQueryTemplateName.K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO.value,
    "alias": LocalQueryTemplateName.K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO.label,
    "description": str(
        _(
            "内存高负载 Pod 占比表示 memory limit 使用率超过「内存使用率阈值」的 Pod 数，"
            "占已配置 memory limit 的 Pod 总数的百分比。"
        )
    ),
    "expression": "a",
    "query_configs": [
        {
            "table": "",
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "interval": 60,
            "promql": _MEMORY_HIGH_LOAD_POD_RATIO_PROMQL,
            "group_by": ["${GROUP_BY}"],
        }
    ],
    "variables": [
        {
            "name": "GROUP_BY",
            "alias": "监控维度",
            "type": VariableType.GROUP_BY.value,
            "config": {
                "default": [K8SMetricTag.BCS_CLUSTER_ID.value, K8SMetricTag.NAMESPACE.value],
                "options": [K8SMetricTag.BCS_CLUSTER_ID.value, K8SMetricTag.NAMESPACE.value],
                "related_metrics": _MEMORY_RELATED_METRICS,
            },
            "description": "统计高负载 Pod 占比时使用的聚合维度。",
        },
        {
            "name": "CONDITIONS",
            "alias": "维度过滤",
            "type": VariableType.CONDITIONS.value,
            "config": {
                "default": [],
                "options": [
                    K8SMetricTag.BCS_CLUSTER_ID.value,
                    K8SMetricTag.NAMESPACE.value,
                    K8SMetricTag.POD_NAME.value,
                    K8SMetricTag.CONTAINER_NAME.value,
                ],
                "related_metrics": _MEMORY_RELATED_METRICS,
            },
            "description": "限定参与高负载 Pod 占比计算的容器范围。",
        },
        {
            "name": "MEMORY_USAGE_THRESHOLD",
            "alias": "[整数] 内存使用率阈值（%）",
            "type": VariableType.CONSTANTS.value,
            "config": {"default": "90"},
            "description": "Pod 内存 limit 使用率超过该值时计为高负载。",
        },
    ],
    "unit": "percent",
}


class LocalQueryTemplateSet(QueryTemplateSet):
    NAMESPACE: str = Namespace.DEFAULT

    QUERY_TEMPLATES = [
        RPC_PANIC_LOG_QUERY_TEMPLATE,
        TRACE_SPAN_TOTAL_QUERY_TEMPLATE,
        LOG_TOTAL_QUERY_TEMPLATE,
        K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO_QUERY_TEMPLATE,
    ]
