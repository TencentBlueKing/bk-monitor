"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from typing import Any
from constants.data_source import DataTypeLabel, DataSourceLabel
from constants.apm import DEFAULT_DATA_LABEL
from constants.query_template import GLOBAL_BIZ_ID

from . import utils
from .base import QueryTemplateSet
from .. import constants


def _get_related_metrics(related_metric_fields: list[str]) -> list[dict[str, str]]:
    return [
        {"metric_field": metric_field, "metric_id": f"{DataSourceLabel.BK_MONITOR_COLLECTOR}.{_TABLE}.{metric_field}"}
        for metric_field in related_metric_fields
    ]


def _get_group_by_variable(
    related_metrics: list[dict[str, str]],
    default: list[str] = None,
    options: list[str] = None,
) -> dict[str, Any]:
    return {
        "name": "GROUP_BY",
        "alias": "监控维度",
        "type": constants.VariableType.GROUP_BY.value,
        "config": {"default": default or [], "options": options or [], "related_metrics": related_metrics},
        "description": "监控维度是指在监控数据中对数据进行分组的依据。",
    }


def _get_conditions_variable(
    related_metrics: list[dict[str, str]],
    default: list[dict[str, Any]] = None,
    options: list[str] = None,
) -> dict[str, Any]:
    return {
        "name": "CONDITIONS",
        "alias": "维度过滤",
        "type": constants.VariableType.CONDITIONS.value,
        "config": {"default": default or [], "options": options or [], "related_metrics": related_metrics},
        "description": "维度过滤是指在监控数据中对数据进行筛选的条件。",
    }


def _get_common_variables(
    related_metric_fields: list[str],
    method_default: str = None,
    group_by_default: list[str] = None,
    group_by_options: list[str] = None,
    conditions_default: list[str] = None,
    conditions_options: list[str] = None,
) -> list[dict[str, Any]]:
    related_metrics: list[dict[str, str]] = _get_related_metrics(related_metric_fields)
    variables: list[dict[str, Any]] = [
        {
            "name": "METHOD",
            "alias": "汇聚",
            "type": constants.VariableType.METHOD.value,
            "config": {"default": method_default or "sum_without_time"},
            "description": "汇聚是指在单个聚合周期内，对监控数据采取的聚合方式，例如 SUM（求和）、MAX（单个聚合周期内的最大值）等。",
        },
        _get_group_by_variable(related_metrics, default=group_by_default, options=group_by_options),
        _get_conditions_variable(
            related_metrics,
            # 数据量太大，给个明确的默认过滤范围，同时也作为过滤条件样例。
            default=conditions_default or [{"key": "namespace", "value": ["kube-system"], "method": "eq"}],
            options=conditions_options,
        ),
    ]

    return variables


def _qs_to_query_params(qs: UnifyQuerySet) -> dict[str, Any]:
    query_params: dict[str, Any] = qs.config
    for query_config in query_params["query_configs"]:
        query_config["where"].append("${CONDITIONS}")
    return utils.format_query_params(query_params)


_TABLE: str = ""

_COMMON_BUILDER: QueryConfigBuilder = (
    QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.BK_MONITOR_COLLECTOR))
    .data_label(DEFAULT_DATA_LABEL)
    .table(_TABLE)
    .interval(60)
    .group_by("${GROUP_BY}")
)


def _cpu_usage_templ(usage_type: str) -> dict[str, Any]:
    return {
        "bk_biz_id": GLOBAL_BIZ_ID,
        "name": f"k8s_cpu_{usage_type}_usage",
        "alias": f"[容器] CPU {usage_type} 使用率（%）",
        "description": f"CPU {usage_type} 使用率表示容器实际使用的 CPU 与分配的 CPU 资源（{usage_type}）的比值。"
        f"如果无数据，则表示容器未设置 CPU {usage_type}。",
        **_qs_to_query_params(
            UnifyQuerySet()
            .add_query(
                _COMMON_BUILDER.alias("a")
                .func(_id="rate", params=[{"id": "window", "value": "1m"}])
                .metric(field="container_cpu_usage_seconds_total", method="${METHOD}", alias="a")
            )
            .add_query(
                _COMMON_BUILDER.alias("b").metric(
                    field=f"kube_pod_container_resource_{usage_type}s_cpu_cores", method="${METHOD}", alias="b"
                )
            )
            .expression("(a / b) * 100")
        ),
        "variables": _get_common_variables(
            ["container_cpu_usage_seconds_total"],
            group_by_default=["bcs_cluster_id", "namespace", "pod_name"],
            group_by_options=["bcs_cluster_id", "namespace", "pod_name", "container_name"],
            conditions_options=["bcs_cluster_id", "namespace", "pod_name", "container_name"],
        ),
    }


def _memory_usage_templ(usage_type: str) -> dict[str, Any]:
    return {
        "bk_biz_id": GLOBAL_BIZ_ID,
        "name": f"k8s_memory_{usage_type}_usage",
        "alias": f"[容器] 内存 {usage_type} 使用率（%）",
        "description": f"内存 {usage_type} 使用率表示容器实际内存占用与分配的内存资源（{usage_type}）的比值。如果无数据，则表示容器未设置内存 {usage_type}。",
        **_qs_to_query_params(
            UnifyQuerySet()
            .add_query(
                _COMMON_BUILDER.alias("a")
                .func(_id="rate", params=[{"id": "window", "value": "1m"}])
                .metric(field="container_memory_working_set_bytes", method="${METHOD}", alias="a")
            )
            .add_query(
                _COMMON_BUILDER.alias("b").metric(
                    field=f"kube_pod_container_resource_{usage_type}s_memory_bytes", method="${METHOD}", alias="b"
                )
            )
            .expression("(a / b) * 100")
        ),
        "variables": _get_common_variables(
            ["container_memory_working_set_bytes"],
            group_by_default=["bcs_cluster_id", "namespace", "pod_name"],
            group_by_options=["bcs_cluster_id", "namespace", "pod_name", "container_name"],
            conditions_options=["bcs_cluster_id", "namespace", "pod_name", "container_name"],
        ),
    }


CPU_LIMIT_USAGE: dict[str, Any] = _cpu_usage_templ("limit")

CPU_REQUEST_USAGE: dict[str, Any] = _cpu_usage_templ("request")

MEMORY_LIMIT_USAGE: dict[str, Any] = _memory_usage_templ("limit")

MEMORY_REQUEST_USAGE: dict[str, Any] = _memory_usage_templ("request")

CPU_USAGE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": "k8s_cpu_usage",
    "alias": "[容器] CPU 使用量",
    "description": "CPU 使用量表示容器实际使用的 CPU 资源，单位为核。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .func(_id="rate", params=[{"id": "window", "value": "1m"}])
            .metric(field="container_cpu_usage_seconds_total", method="${METHOD}", alias="a")
        )
        .expression("a")
    ),
    "variables": _get_common_variables(
        ["container_cpu_usage_seconds_total"],
        method_default="SUM",
        group_by_default=["bcs_cluster_id", "namespace", "workload_kind", "workload_name"],
        group_by_options=[
            "bcs_cluster_id",
            "namespace",
            "workload_kind",
            "workload_name",
            "pod_name",
            "container_name",
        ],
        conditions_options=[
            "bcs_cluster_id",
            "namespace",
            "workload_kind",
            "workload_name",
            "pod_name",
            "container_name",
        ],
    ),
}

MEMORY_USAGE: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "name": "k8s_memory_usage",
    "alias": "[容器] 内存使用量",
    "description": "内存使用量表示容器实际使用的内存资源，单位为字节。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .func(_id="rate", params=[{"id": "window", "value": "1m"}])
            .metric(field="container_memory_working_set_bytes", method="${METHOD}", alias="a")
        )
        .expression("a")
    ),
    "variables": _get_common_variables(
        ["container_memory_working_set_bytes"],
        method_default="SUM",
        group_by_default=["bcs_cluster_id", "namespace", "workload_kind", "workload_name"],
        group_by_options=[
            "bcs_cluster_id",
            "namespace",
            "workload_kind",
            "workload_name",
            "pod_name",
            "container_name",
        ],
        conditions_options=[
            "bcs_cluster_id",
            "namespace",
            "workload_kind",
            "workload_name",
            "pod_name",
            "container_name",
        ],
    ),
}

TERMINATE_REASON: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "alias": "[容器] 异常终止数",
    "name": "k8s_terminate_reason",
    "description": "异常终止数表示容器因异常原因（如 OOMKilled）终止的次数。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .func(_id="increase", params=[{"id": "window", "value": "1m"}])
            .metric(field="kube_pod_container_status_terminated_reason", method="SUM", alias="a")
        )
        .expression("a")
    ),
    "variables": [
        _get_group_by_variable(
            _get_related_metrics(["kube_pod_container_status_terminated_reason"]),
            default=["bcs_cluster_id", "namespace", "reason"],
            options=["bcs_cluster_id", "namespace", "pod_name", "container_name", "reason"],
        ),
        _get_conditions_variable(
            _get_related_metrics(["kube_pod_container_status_terminated_reason"]),
            options=["bcs_cluster_id", "namespace", "pod_name", "container_name", "reason"],
        ),
    ],
}

ABNORMAL_RESTART: dict[str, Any] = {
    "bk_biz_id": GLOBAL_BIZ_ID,
    "alias": "[容器] 异常重启数",
    "name": "k8s_abnormal_restart",
    "description": "异常重启数表示容器在非正常状态下的重启次数。",
    **_qs_to_query_params(
        UnifyQuerySet()
        .add_query(
            _COMMON_BUILDER.alias("a")
            .func(_id="increase", params=[{"id": "window", "value": "1m"}])
            .metric(field="kube_pod_container_status_restarts_total", method="SUM", alias="a")
        )
        .expression("a")
    ),
    "variables": [
        _get_group_by_variable(
            _get_related_metrics(["kube_pod_container_status_restarts_total"]),
            default=["bcs_cluster_id", "namespace"],
            options=["bcs_cluster_id", "namespace", "pod_name", "container_name"],
        ),
        _get_conditions_variable(
            _get_related_metrics(["kube_pod_container_status_restarts_total"]),
            options=["bcs_cluster_id", "namespace", "pod_name", "container_name"],
        ),
    ],
}


class K8SQueryTemplateSet(QueryTemplateSet):
    """容器场景内置查询模板集"""

    NAMESPACE: str = constants.Namespace.K8S.value

    QUERY_TEMPLATES: list[dict[str, Any]] = [
        CPU_LIMIT_USAGE,
        CPU_REQUEST_USAGE,
        MEMORY_LIMIT_USAGE,
        MEMORY_REQUEST_USAGE,
        CPU_USAGE,
        MEMORY_USAGE,
        TERMINATE_REASON,
        ABNORMAL_RESTART,
    ]
