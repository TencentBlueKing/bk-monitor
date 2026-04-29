"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.filter_calls = []
        self.slice_value = None

    def filter(self, **kwargs):
        self.filter_calls.append(kwargs)
        return self

    def __getitem__(self, value):
        self.slice_value = value
        return self.rows[value]


class FakeManager:
    def __init__(self, queryset):
        self.queryset = queryset

    def filter(self, **kwargs):
        self.queryset.filter_calls.append(kwargs)
        return self.queryset


def test_inspect_bcs_metadata_registered_as_bkm_cli_op():
    op = BkmCliOpRegistry.resolve("inspect-bcs-metadata")
    function_detail = KernelRPCRegistry.get_function_detail("bkm_cli.inspect_bcs_metadata")

    assert op.func_name == "bkm_cli.inspect_bcs_metadata"
    assert op.capability_level == "inspect"
    assert op.risk_level == "low"
    assert function_detail is not None


def test_inspect_bcs_metadata_reads_db_models_only(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    cluster_info_qs = FakeQuerySet(
        [
            SimpleNamespace(
                cluster_id="BCS-K8S-00001",
                bcs_api_cluster_id="BCS-K8S-00001",
                bk_biz_id=1001,
                project_id="project-a",
                status="running",
                K8sMetricDataID=10001,
                K8sEventDataID=10002,
                bk_tenant_id="system",
            )
        ]
    )
    space_qs = FakeQuerySet(
        [
            SimpleNamespace(
                space_type_id="bkcc",
                space_id="1001",
                space_uid="bkcc__1001",
                space_name="biz-demo",
                is_bcs_valid=True,
                bk_tenant_id="system",
            )
        ]
    )
    space_resource_qs = FakeQuerySet(
        [
            SimpleNamespace(
                space_type_id="bkcc",
                space_id="1001",
                resource_type="bcs",
                resource_id="BCS-K8S-00001",
                dimension_values=[{"cluster_id": "BCS-K8S-00001"}],
                bk_tenant_id="system",
            )
        ]
    )
    bcs_cluster_qs = FakeQuerySet(
        [
            SimpleNamespace(
                bk_biz_id=1001,
                bcs_cluster_id="BCS-K8S-00001",
                name="cluster-demo",
                environment="prod",
                space_uid="bkcc__1001",
                bk_tenant_id="system",
            )
        ]
    )
    metric_cache_qs = FakeQuerySet(
        [
            SimpleNamespace(
                bk_biz_id=1001,
                result_table_id="1001_bkmonitor_event",
                metric_field="event_count",
                metric_field_name="event count",
                data_label="k8s_event",
                bk_tenant_id="system",
            )
        ]
    )

    monkeypatch.setattr(bcs_metadata.BCSClusterInfo, "objects", FakeManager(cluster_info_qs))
    monkeypatch.setattr(bcs_metadata.Space, "objects", FakeManager(space_qs))
    monkeypatch.setattr(bcs_metadata.SpaceResource, "objects", FakeManager(space_resource_qs))
    monkeypatch.setattr(bcs_metadata.BCSCluster, "objects", FakeManager(bcs_cluster_qs))
    monkeypatch.setattr(bcs_metadata.MetricListCache, "objects", FakeManager(metric_cache_qs))

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {
                "cluster_id": "BCS-K8S-00001",
                "bk_biz_id": "1001",
                "space_uid": "bkcc__1001",
                "bk_tenant_id": "system",
                "include_metric_cache": True,
            },
        }
    )

    assert result["result"]["cluster_id"] == "BCS-K8S-00001"
    assert result["result"]["bk_biz_id"] == 1001
    assert result["result"]["space_uid"] == "bkcc__1001"
    assert result["result"]["bcs_cluster_info"][0]["status"] == "running"
    assert result["result"]["spaces"][0]["space_uid"] == "bkcc__1001"
    assert result["result"]["space_resources"][0]["resource_id"] == "BCS-K8S-00001"
    assert result["result"]["bcs_clusters"][0]["space_uid"] == "bkcc__1001"
    assert result["result"]["metric_list_cache"][0]["data_label"] == "k8s_event"
    assert cluster_info_qs.filter_calls == [{"cluster_id": "BCS-K8S-00001"}, {"bk_biz_id": 1001}]
    assert bcs_cluster_qs.filter_calls == [
        {"bcs_cluster_id": "BCS-K8S-00001"},
        {"bk_biz_id": 1001},
        {"space_uid": "bkcc__1001"},
    ]


def test_inspect_bcs_metadata_can_skip_metric_cache(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    monkeypatch.setattr(bcs_metadata.BCSClusterInfo, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(bcs_metadata.Space, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(bcs_metadata.SpaceResource, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(bcs_metadata.BCSCluster, "objects", FakeManager(FakeQuerySet([])))
    metric_cache_qs = FakeQuerySet([])
    monkeypatch.setattr(bcs_metadata.MetricListCache, "objects", FakeManager(metric_cache_qs))

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {
                "cluster_id": "BCS-K8S-00001",
                "bk_tenant_id": "system",
                "include_metric_cache": False,
            },
        }
    )

    assert result["result"]["metric_list_cache"] == []
    assert metric_cache_qs.filter_calls == []


def test_inspect_bcs_metadata_rejects_missing_cluster_id():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "inspect-bcs-metadata",
                "params": {},
            }
        )

    assert "cluster_id" in str(exc.value)
