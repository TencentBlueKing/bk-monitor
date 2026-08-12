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
        self.filter_args_calls = []
        self.order_by_fields = None
        self.slice_value = None

    def filter(self, *args, **kwargs):
        if args:
            self.filter_args_calls.append(args)
        self.filter_calls.append(kwargs)
        if kwargs:
            self.rows = [
                row
                for row in self.rows
                if all(getattr(row, field_name, None) == expected for field_name, expected in kwargs.items())
            ]
        return self

    def order_by(self, *fields):
        self.order_by_fields = fields
        return self

    def count(self):
        return len(self.rows)

    def __getitem__(self, value):
        self.slice_value = value
        return self.rows[value]


class FakeManager:
    def __init__(self, queryset):
        self.queryset = queryset

    def filter(self, *args, **kwargs):
        return self.queryset.filter(*args, **kwargs)


def _patch_bcs_models(
    monkeypatch,
    bcs_metadata,
    cluster_info_rows,
    federal_rows,
    *,
    space_resource_rows=None,
    bcs_cluster_rows=None,
):
    federal_qs = FakeQuerySet(federal_rows)
    monkeypatch.setattr(bcs_metadata.BCSClusterInfo, "objects", FakeManager(FakeQuerySet(cluster_info_rows)))
    monkeypatch.setattr(bcs_metadata.Space, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(
        bcs_metadata.SpaceResource,
        "objects",
        FakeManager(FakeQuerySet(space_resource_rows or [])),
    )
    monkeypatch.setattr(
        bcs_metadata.BCSCluster,
        "objects",
        FakeManager(FakeQuerySet(bcs_cluster_rows or [])),
    )
    monkeypatch.setattr(bcs_metadata.MetricListCache, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(
        bcs_metadata,
        "BcsFederalClusterInfo",
        SimpleNamespace(objects=FakeManager(federal_qs)),
        raising=False,
    )
    return federal_qs


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
                CustomMetricDataID=10003,
                CustomEventDataID=10004,
                bk_env="bkop",
                bk_env_label="bkop",
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
                resource_id="1001",
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
    federal_qs = FakeQuerySet(
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=["namespace-a", "namespace-b"],
                fed_builtin_metric_table_id="1001_bkmonitor_time_series_10001.__default__",
                fed_builtin_event_table_id="1001_bkmonitor_event_10002",
            ),
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00004",
                is_deleted=True,
                fed_namespaces=[],
                fed_builtin_metric_table_id=None,
                fed_builtin_event_table_id=None,
            ),
        ]
    )

    monkeypatch.setattr(bcs_metadata.BCSClusterInfo, "objects", FakeManager(cluster_info_qs))
    monkeypatch.setattr(bcs_metadata.Space, "objects", FakeManager(space_qs))
    monkeypatch.setattr(bcs_metadata.SpaceResource, "objects", FakeManager(space_resource_qs))
    monkeypatch.setattr(bcs_metadata.BCSCluster, "objects", FakeManager(bcs_cluster_qs))
    monkeypatch.setattr(bcs_metadata.MetricListCache, "objects", FakeManager(metric_cache_qs))
    monkeypatch.setattr(
        bcs_metadata,
        "BcsFederalClusterInfo",
        SimpleNamespace(objects=FakeManager(federal_qs)),
        raising=False,
    )

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
    cluster_info = result["result"]["bcs_cluster_info"][0]
    assert cluster_info["status"] == "running"
    assert cluster_info["bk_env"] == "bkop"
    assert cluster_info["bk_env_label"] == "bkop"
    assert result["result"]["spaces"][0]["space_uid"] == "bkcc__1001"
    assert result["result"]["space_resources"][0]["resource_id"] == "1001"
    assert result["result"]["bcs_clusters"][0]["space_uid"] == "bkcc__1001"
    assert result["result"]["metric_list_cache"][0]["data_label"] == "k8s_event"
    assert result["result"]["federal_cluster_info"] == {
        "status": "found",
        "total_count": 2,
        "returned_count": 2,
        "truncated": False,
        "items": [
            {
                "fed_cluster_id": "BCS-K8S-00001",
                "host_cluster_id": "BCS-K8S-00002",
                "sub_cluster_id": "BCS-K8S-00003",
                "is_deleted": False,
                "fed_namespaces": ["namespace-a", "namespace-b"],
                "fed_namespaces_total_count": 2,
                "fed_namespaces_returned_count": 2,
                "fed_namespaces_truncated": False,
                "fed_builtin_metric_table_id": "1001_bkmonitor_time_series_10001.__default__",
                "fed_builtin_event_table_id": "1001_bkmonitor_event_10002",
            },
            {
                "fed_cluster_id": "BCS-K8S-00001",
                "host_cluster_id": "BCS-K8S-00002",
                "sub_cluster_id": "BCS-K8S-00004",
                "is_deleted": True,
                "fed_namespaces": [],
                "fed_namespaces_total_count": 0,
                "fed_namespaces_returned_count": 0,
                "fed_namespaces_truncated": False,
                "fed_builtin_metric_table_id": None,
                "fed_builtin_event_table_id": None,
            },
        ],
    }
    assert cluster_info_qs.filter_calls == [
        {"cluster_id": "BCS-K8S-00001"},
        {"bk_biz_id": 1001},
        {"bk_tenant_id": "system"},
    ]
    assert bcs_cluster_qs.filter_calls == [
        {"bcs_cluster_id": "BCS-K8S-00001"},
        {"bk_biz_id": 1001},
        {"space_uid": "bkcc__1001"},
        {"bk_tenant_id": "system"},
    ]
    assert space_qs.filter_calls == [{"bk_tenant_id": "system", "space_type_id": "bkcc", "space_id": "1001"}]
    assert space_resource_qs.filter_calls == [
        {"resource_type": "bcs", "resource_id": "1001"},
        {"bk_tenant_id": "system", "space_type_id": "bkcc", "space_id": "1001"},
    ]
    assert metric_cache_qs.filter_calls == [{"bk_biz_id": 1001}, {"bk_tenant_id": "system"}]
    federal_filter = federal_qs.filter_args_calls[0][0]
    assert federal_filter.connector == "OR"
    assert federal_filter.children == [
        ("fed_cluster_id", "BCS-K8S-00001"),
        ("host_cluster_id", "BCS-K8S-00001"),
        ("sub_cluster_id", "BCS-K8S-00001"),
    ]
    assert federal_qs.order_by_fields == ("fed_cluster_id", "host_cluster_id", "sub_cluster_id", "is_deleted")


def test_inspect_bcs_metadata_can_skip_metric_cache(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    monkeypatch.setattr(bcs_metadata.BCSClusterInfo, "objects", FakeManager(FakeQuerySet([])))
    space_qs = FakeQuerySet([])
    monkeypatch.setattr(bcs_metadata.Space, "objects", FakeManager(space_qs))
    monkeypatch.setattr(bcs_metadata.SpaceResource, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(bcs_metadata.BCSCluster, "objects", FakeManager(FakeQuerySet([])))
    monkeypatch.setattr(
        bcs_metadata,
        "BcsFederalClusterInfo",
        SimpleNamespace(objects=FakeManager(FakeQuerySet([]))),
        raising=False,
    )
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
    assert result["result"]["spaces"] == []
    assert space_qs.filter_calls == []


def test_inspect_bcs_metadata_reports_non_federal_cluster(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [],
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {"cluster_id": "BCS-K8S-00001", "bk_biz_id": 1001, "bk_tenant_id": "system"},
        }
    )

    assert result["result"]["federal_cluster_info"] == {
        "status": "not_federal",
        "total_count": 0,
        "returned_count": 0,
        "truncated": False,
        "items": [],
    }


def test_inspect_bcs_metadata_hides_federal_rows_outside_requested_scope(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=["private-namespace"],
                fed_builtin_metric_table_id="private.metric",
                fed_builtin_event_table_id="private.event",
            )
        ],
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {"cluster_id": "BCS-K8S-00001", "bk_biz_id": 2002, "bk_tenant_id": "other"},
        }
    )

    assert result["result"]["federal_cluster_info"] == {
        "status": "not_found_in_scope",
        "total_count": 0,
        "returned_count": 0,
        "truncated": False,
        "items": [],
    }
    assert federal_qs.filter_calls == []


def test_inspect_bcs_metadata_reports_missing_cluster_in_requested_scope(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(monkeypatch, bcs_metadata, [], [])

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {"cluster_id": "BCS-K8S-99999", "bk_biz_id": 1001, "bk_tenant_id": "system"},
        }
    )

    assert result["result"]["federal_cluster_info"]["status"] == "not_found_in_scope"
    assert federal_qs.filter_calls == []


def test_inspect_bcs_metadata_hides_federal_rows_without_tenant_scope(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=["private-namespace"],
            )
        ],
    )

    result = BkmCliOpCallResource().perform_request(
        {"op_id": "inspect-bcs-metadata", "params": {"cluster_id": "BCS-K8S-00001"}}
    )

    assert result["result"]["federal_cluster_info"]["status"] == "not_found_in_scope"
    assert federal_qs.filter_calls == []


def test_inspect_bcs_metadata_hides_federal_rows_when_space_does_not_own_cluster(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=["private-namespace"],
            )
        ],
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {
                "cluster_id": "BCS-K8S-00001",
                "space_uid": "bkcc__2002",
                "bk_tenant_id": "system",
            },
        }
    )

    assert result["result"]["federal_cluster_info"]["status"] == "not_found_in_scope"
    assert federal_qs.filter_calls == []


def test_inspect_bcs_metadata_accepts_real_bcs_space_resource_shape(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=[],
            )
        ],
        space_resource_rows=[
            SimpleNamespace(
                space_type_id="bkci",
                space_id="project-a",
                bk_tenant_id="system",
                resource_type="bcs",
                resource_id="project-a",
                dimension_values=[
                    {"cluster_id": "BCS-K8S-OTHER", "namespace": None, "cluster_type": "single"},
                    {"cluster_id": "BCS-K8S-00001", "namespace": ["namespace-a"], "cluster_type": "shared"},
                ],
            )
        ],
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {
                "cluster_id": "BCS-K8S-00001",
                "space_uid": "bkci__project-a",
                "bk_tenant_id": "system",
            },
        }
    )

    assert result["result"]["federal_cluster_info"]["status"] == "found"
    assert result["result"]["space_resources"][0]["resource_id"] == "project-a"
    assert federal_qs.filter_args_calls


def test_inspect_bcs_metadata_accepts_bkcc_space_owned_by_cluster_info(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=[],
            )
        ],
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {
                "cluster_id": "BCS-K8S-00001",
                "bk_biz_id": 1001,
                "space_uid": "bkcc__1001",
                "bk_tenant_id": "system",
            },
        }
    )

    assert result["result"]["space_resources"] == []
    assert result["result"]["bcs_clusters"] == []
    assert result["result"]["federal_cluster_info"]["status"] == "found"
    assert federal_qs.filter_args_calls


def test_inspect_bcs_metadata_rejects_non_bcs_space_resource_collision(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_qs = _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        [
            SimpleNamespace(
                fed_cluster_id="BCS-K8S-00001",
                host_cluster_id="BCS-K8S-00002",
                sub_cluster_id="BCS-K8S-00003",
                is_deleted=False,
                fed_namespaces=["private-namespace"],
            )
        ],
        space_resource_rows=[
            SimpleNamespace(
                space_type_id="bkci",
                space_id="project-a",
                bk_tenant_id="system",
                resource_type="other",
                resource_id="project-a",
                dimension_values=[{"cluster_id": "BCS-K8S-00001"}],
            )
        ],
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {
                "cluster_id": "BCS-K8S-00001",
                "space_uid": "bkci__project-a",
                "bk_tenant_id": "system",
            },
        }
    )

    assert result["result"]["space_resources"] == []
    assert result["result"]["federal_cluster_info"]["status"] == "not_found_in_scope"
    assert federal_qs.filter_calls == []


def test_inspect_bcs_metadata_truncates_federal_rows_and_namespaces(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import bcs_metadata

    federal_rows = [
        SimpleNamespace(
            fed_cluster_id="BCS-K8S-00001",
            host_cluster_id="BCS-K8S-00002",
            sub_cluster_id=f"BCS-K8S-{index:05d}",
            is_deleted=False,
            fed_namespaces=[f"namespace-{namespace_index}" for namespace_index in range(201)] if index == 0 else [],
            fed_builtin_metric_table_id="metric.table",
            fed_builtin_event_table_id="event.table",
        )
        for index in range(51)
    ]
    _patch_bcs_models(
        monkeypatch,
        bcs_metadata,
        [SimpleNamespace(cluster_id="BCS-K8S-00001", bk_biz_id=1001, bk_tenant_id="system")],
        federal_rows,
    )

    result = BkmCliOpCallResource().perform_request(
        {
            "op_id": "inspect-bcs-metadata",
            "params": {"cluster_id": "BCS-K8S-00001", "bk_biz_id": 1001, "bk_tenant_id": "system"},
        }
    )

    federal_info = result["result"]["federal_cluster_info"]
    assert federal_info["status"] == "found"
    assert federal_info["total_count"] == 51
    assert federal_info["returned_count"] == 50
    assert federal_info["truncated"] is True
    assert len(federal_info["items"]) == 50
    first_item = federal_info["items"][0]
    assert first_item["fed_namespaces_total_count"] == 201
    assert first_item["fed_namespaces_returned_count"] == 200
    assert first_item["fed_namespaces_truncated"] is True
    assert len(first_item["fed_namespaces"]) == 200


def test_inspect_bcs_metadata_rejects_missing_cluster_id():
    with pytest.raises(CustomException) as exc:
        BkmCliOpCallResource().perform_request(
            {
                "op_id": "inspect-bcs-metadata",
                "params": {},
            }
        )

    assert "cluster_id" in str(exc.value)
