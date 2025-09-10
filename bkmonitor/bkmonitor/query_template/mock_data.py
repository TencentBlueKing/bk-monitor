"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db.models import Q

from bkmonitor.data_source import filter_dict_to_conditions, q_to_dict
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel

from . import constants

COMMON_BUILDER: QueryConfigBuilder = (
    QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))
    .data_label("APM")
    .table("APM.__default__")
    .interval(60)
)


def format_query_params(query_params: dict[str, Any]) -> dict[str, Any]:
    return {
        "functions": query_params.get("functions", []),
        "expression": query_params["expression"],
        "query_configs": query_params["query_configs"],
    }


def callee_success_rate_query_params() -> dict[str, Any]:
    query_params: dict[str, Any] = (
        UnifyQuerySet()
        .add_query(
            COMMON_BUILDER.alias("a")
            .group_by("${GROUP_BY}")
            .metric(field="rpc_server_handled_total", method="SUM", alias="a")
            .conditions(filter_dict_to_conditions(q_to_dict(Q(code_type="success")), []))
        )
        .add_query(
            COMMON_BUILDER.alias("b")
            .group_by("${GROUP_BY}")
            .metric(field="rpc_server_handled_total", method="SUM", alias="b")
        )
        .expression("(a or b < bool 0) / (b > ${ALARM_THRESHOLD_VALUE}) * 100")
        .config
    )

    for query_config in query_params["query_configs"]:
        query_config["where"].append("${CONDITIONS}")
        query_config["functions"].append("${FUNCTIONS}")

    query_params.setdefault("functions", [])
    query_params["functions"].append("${EXPRESSION_FUNCTIONS}")

    return format_query_params(query_params)


def callee_p99_query_params() -> dict[str, Any]:
    query_params: dict[str, Any] = (
        UnifyQuerySet()
        .add_query(
            COMMON_BUILDER.alias("a")
            .group_by("le", "${GROUP_BY}")
            .func(_id="histogram_quantile", params=[{"id": "scalar", "value": 0.99}])
            .metric(field="rpc_server_handled_seconds_bucket", method="${METHOD}", alias="a")
        )
        .add_query(
            COMMON_BUILDER.alias("b")
            .group_by("${GROUP_BY}")
            .metric(field="rpc_server_handled_total", method="${METHOD}", alias="b")
            .conditions(filter_dict_to_conditions(q_to_dict(Q(code_type="${CODE_TYPE}")), []))
        )
        .expression("(b > bool ${ALARM_THRESHOLD_VALUE}) * a * 1000")
        .config
    )

    for query_config in query_params["query_configs"]:
        query_config["where"].append("${CONDITIONS}")
        query_config["functions"].append("${FUNCTIONS}")

    return format_query_params(query_params)


CALLEE_SUCCESS_RATE_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": 0,
    "alias": "被调成功率（%）",
    "name": "apm_rpc_callee_success_rate",
    **callee_success_rate_query_params(),
    "variables": [
        {
            "name": "GROUP_BY",
            "alias": "监控维度",
            "type": constants.VariableType.GROUP_BY.value,
            "config": {
                "default": ["service_name", "callee_method"],
                "related_metrics": [
                    {
                        "metric_field": "rpc_server_handled_total",
                        "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                    }
                ],
            },
            "description": "监控维度是指在监控数据中对数据进行分组的依据。",
        },
        {
            "name": "CONDITIONS",
            "alias": "维度过滤",
            "type": constants.VariableType.CONDITIONS.value,
            "config": {
                "options": ["callee_service", "callee_method"],
                "default": [{"key": "rpc_system", "method": "eq", "value": [""]}],
                "related_metrics": [
                    {
                        "metric_field": "rpc_server_handled_total",
                        "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                    },
                ],
            },
            "description": "维度过滤是指在监控数据中对数据进行筛选的条件。",
        },
        {
            "name": "FUNCTIONS",
            "alias": "函数",
            "type": constants.VariableType.FUNCTIONS.value,
            "config": {"default": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}]},
        },
        {
            "name": "ALARM_THRESHOLD_VALUE",
            "alias": "告警起算值",
            "type": constants.VariableType.CONSTANTS.value,
            "config": {"default": "0"},
            "description": "告警起算值是为了避免在请求数较少的情况下，因少量请求的异常导致告警触发，起算值可以根据实际业务情况进行调整。",
        },
        {
            "name": "EXPRESSION_FUNCTIONS",
            "alias": "表达式函数",
            "type": constants.VariableType.EXPRESSION_FUNCTIONS.value,
            "config": {"default": [{"id": "abs", "params": []}]},
        },
    ],
}


CALLEE_SUCCESS_RATE_QUERY_INSTANCE: dict[str, Any] = {
    "bk_biz_id": 0,
    "alias": "被调成功率（%）",
    "name": "apm_rpc_callee_success_rate",
    "description": "",
    "namespace": "default",
    "query_configs": [
        {
            "table": "APM.__default__",
            "data_label": "APM",
            "data_type_label": "time_series",
            "data_source_label": "custom",
            "interval": 60,
            "promql": "",
            "metric_id": "custom.APM.__default__.rpc_server_handled_total",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "a"}],
            "where": [
                {"key": "code_type", "value": ["success"], "method": "eq"},
                {"key": "rpc_system", "method": "eq", "value": [""]},
            ],
            "functions": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
            "group_by": ["service_name", "callee_method"],
        },
        {
            "table": "APM.__default__",
            "data_label": "APM",
            "data_type_label": "time_series",
            "data_source_label": "custom",
            "interval": 60,
            "promql": "",
            "metric_id": "custom.APM.__default__.rpc_server_handled_total",
            "metrics": [{"field": "rpc_server_handled_total", "method": "SUM", "alias": "b"}],
            "where": [{"key": "rpc_system", "method": "eq", "value": [""]}],
            "functions": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}],
            "group_by": ["service_name", "callee_method"],
        },
    ],
    "expression": "(a or b < bool 0) / (b > 0) * 100",
    "space_scope": [],
    "functions": [{"id": "abs", "params": []}],
}


CALLEE_P99_QUERY_TEMPLATE: dict[str, Any] = {
    "bk_biz_id": 0,
    "name": "apm_rpc_callee_p99",
    "alias": "被调 P99 耗时（ms）",
    **callee_p99_query_params(),
    "variables": [
        {
            "name": "GROUP_BY",
            "alias": "监控维度",
            "type": constants.VariableType.GROUP_BY.value,
            "config": {
                "default": ["service_name", "callee_method"],
                "related_metrics": [
                    {
                        "metric_field": "rpc_server_handled_total",
                        "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                    },
                    {
                        "metric_field": "rpc_server_handled_seconds_bucket",
                        "metric_id": "custom.APM.__default__.rpc_server_handled_seconds_bucket",
                    },
                ],
            },
            "description": "监控维度是指在监控数据中对数据进行分组的依据。",
        },
        {
            "name": "CONDITIONS",
            "alias": "维度过滤",
            "type": constants.VariableType.CONDITIONS.value,
            "config": {
                "default": [{"key": "rpc_system", "method": "eq", "value": [""]}],
                "related_metrics": [
                    {
                        "metric_field": "rpc_server_handled_total",
                        "metric_id": "custom.APM.__default__.rpc_client_handled_total",
                    },
                    {
                        "metric_field": "rpc_server_handled_seconds_bucket",
                        "metric_id": "custom.APM.__default__.rpc_server_handled_seconds_bucket",
                    },
                ],
            },
            "description": "维度过滤是指在监控数据中对数据进行筛选的条件。",
        },
        {
            "name": "FUNCTIONS",
            "alias": "函数",
            "type": constants.VariableType.FUNCTIONS.value,
            "config": {"default": [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}]},
        },
        {
            "name": "METHOD",
            "alias": "汇聚",
            "type": constants.VariableType.METHOD.value,
            "config": {"default": "SUM"},
        },
        {
            "name": "CODE_TYPE",
            "alias": "返回码类型",
            "type": constants.VariableType.TAG_VALUES.value,
            "config": {
                "default": ["success"],
                "related_tag": "code_type",
                "related_metrics": [
                    {
                        "metric_field": "rpc_server_handled_total",
                        "metric_id": "custom.APM.__default__.rpc_server_handled_total",
                    }
                ],
            },
            "description": "返回码类型",
        },
        {
            "name": "ALARM_THRESHOLD_VALUE",
            "type": constants.VariableType.CONSTANTS.value,
            "alias": "告警起算值",
            "config": {"default": "0"},
            "description": "告警起算值是为了避免在请求数较少的情况下，因少量请求的异常导致告警触发，起算值可以根据实际业务情况进行调整。",
        },
    ],
}
