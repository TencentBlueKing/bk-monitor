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

import pytest

from apm_web.strategy.query_template.local import LocalQueryTemplateName, LocalQueryTemplateSet

from .. import mock_data, serializers
from ..builtin.apm import APMQueryTemplateName, APMQueryTemplateSet
from ..builtin.k8s import K8SQueryTemplateSet
from ..core import QueryTemplateWrapper


class TestSerializers:
    @pytest.mark.parametrize(
        "template", [mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE, mock_data.CALLEE_P99_QUERY_TEMPLATE]
    )
    def test_query_template_serializers(self, template: dict[str, Any]):
        serializer = serializers.QueryTemplateSerializer(data=template)
        serializer.is_valid(raise_exception=True)

    @pytest.mark.parametrize(
        "template",
        APMQueryTemplateSet.QUERY_TEMPLATES
        + K8SQueryTemplateSet.QUERY_TEMPLATES
        + LocalQueryTemplateSet.QUERY_TEMPLATES,
        ids=lambda template: template["name"],
    )
    def test_builtin_query_templates_valid(self, template: dict[str, Any]):
        serializer = serializers.QueryTemplateSerializer(data=template)
        serializer.is_valid(raise_exception=True)


def _histogram_quantile_value(query_configs: list[dict[str, Any]]) -> Any:
    for query_config in query_configs:
        for function in query_config.get("functions") or []:
            if not isinstance(function, dict) or function.get("id") != "histogram_quantile":
                continue
            for param in function.get("params") or []:
                if param.get("id") == "scalar":
                    return param.get("value")
    raise AssertionError("histogram_quantile scalar not found")


class TestBuiltinTemplateRender:
    @pytest.mark.parametrize(
        "template_name",
        [APMQueryTemplateName.RPC_CALLEE_QUANTILE, APMQueryTemplateName.RPC_CALLER_QUANTILE],
    )
    def test_rpc_quantile_uses_custom_quantile(self, template_name: APMQueryTemplateName):
        template: dict[str, Any] = next(
            item for item in APMQueryTemplateSet.QUERY_TEMPLATES if item["name"] == template_name.value
        )
        rendered: dict[str, Any] = QueryTemplateWrapper.from_dict(template).render(
            {
                "QUANTILE": "0.995",
                "ALARM_THRESHOLD_VALUE": 20,
                "GROUP_BY": ["service_name"],
                "CONDITIONS": [],
                "FUNCTIONS": [],
            }
        )
        assert rendered["expression"] == "(b > bool 20) * a * 1000"
        assert _histogram_quantile_value(rendered["query_configs"]) == "0.995"
        assert all(not query_config.get("promql") for query_config in rendered["query_configs"])

    def test_memory_high_load_pod_ratio_uses_local_promql(self):
        template: dict[str, Any] = next(
            item
            for item in LocalQueryTemplateSet.QUERY_TEMPLATES
            if item["name"] == LocalQueryTemplateName.K8S_MEMORY_LIMIT_USAGE_CONTAINER_RATIO.value
        )
        wrapper: QueryTemplateWrapper = QueryTemplateWrapper.from_dict(template)
        rendered: dict[str, Any] = wrapper.render(
            {
                "MEMORY_USAGE_THRESHOLD": "90",
                "GROUP_BY": ["bcs_cluster_id", "namespace"],
                "CONDITIONS": [
                    {"key": "bcs_cluster_id", "value": ["BCS-K8S-00000"], "method": "eq"},
                    {"key": "namespace", "value": ["trpc-micros-stag"], "method": "eq", "condition": "and"},
                    {
                        "key": "pod_name",
                        "value": ["^bkm-web(-[a-z0-9]{5,10}){1,2}$"],
                        "method": "req",
                        "condition": "and",
                    },
                ],
            }
        )
        assert rendered["expression"] == "a"
        assert len(rendered["query_configs"]) == 1
        query_config: dict[str, Any] = rendered["query_configs"][0]
        assert query_config["data_source_label"] == "prometheus"
        promql: str = query_config["promql"]
        assert "count without" not in rendered["expression"]
        assert "sum by (bcs_cluster_id, namespace)" in promql
        assert "count by (bcs_cluster_id, namespace)" in promql
        assert "> bool 90" in promql
        assert "container_memory_working_set_bytes" in promql
        assert "kube_pod_container_resource_limits_memory_bytes" in promql
        assert "bcs_cluster_id, namespace, pod_name" in promql
        assert 'bcs_cluster_id="BCS-K8S-00000"' in promql
        assert 'namespace="trpc-micros-stag"' in promql
        assert 'pod_name=~"^bkm-web(-[a-z0-9]{5,10}){1,2}$"' in promql
        assert "workload_name" not in query_config["group_by"]
        assert "workload_kind" not in query_config["group_by"]

        strategy_item: dict[str, Any] = wrapper.render_to_strategy_item(
            {
                "MEMORY_USAGE_THRESHOLD": "90",
                "GROUP_BY": ["bcs_cluster_id", "namespace"],
                "CONDITIONS": [],
            }
        )
        assert strategy_item["expression"] == "a"
        assert len(strategy_item["query_configs"]) == 1
        assert strategy_item["query_configs"][0]["promql"]
        assert strategy_item["query_configs"][0]["alias"] == "a"
