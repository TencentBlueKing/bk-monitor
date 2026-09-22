"""VM Query 独立镜像的同步及 Admin 读取测试。"""

import copy

import pytest
from django.db import IntegrityError, transaction

from core.drf_resource import api
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin.datalink import get_component_config, get_component_detail, list_components
from metadata import config, models
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import COMPONENT_CLASS_MAP, ClusterConfig
from metadata.models.data_link.vm_query_cluster import VmQueryClusterConfig
from metadata.task.bkbase import sync_all_bkbase_cluster_info, sync_bkbase_vm_query_clusters
from metadata.task.tenant import _init_bkbase_cluster

pytestmark = pytest.mark.django_db(databases="__all__")


def remote_cluster(name="query-a", tenant="tenant-a", namespace="bkmonitor"):
    return {
        "kind": "VmQueryCluster",
        "metadata": {"tenant": tenant, "namespace": namespace, "name": name, "labels": {}, "annotations": {}},
        "spec": {
            "clusterName": f"logical-{name}",
            "clusterDomain": f"{name}.example.com",
            "monitorStorageClusters": ["monitor-0", "monitor-4"],
            "numReplicas": 3,
            "k8sCluster": "BCS-K8S-10000",
            "version": "1.115.0-2.0.0",
            "k8sNamespace": "vm-query",
        },
        "status": {"phase": "Ok", "message": "", "version": 1790051345649},
    }


@pytest.fixture(autouse=True)
def external_apis(mocker, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    list_api = mocker.patch.object(api.bkdata, "list_data_link", return_value=[])
    get_api = mocker.patch.object(api.bkdata, "get_data_link")
    apply_api = mocker.patch.object(api.bkdata, "apply_data_link")
    delete_api = mocker.patch.object(api.bkdata, "delete_data_link")
    yield list_api, get_api
    apply_api.assert_not_called()
    delete_api.assert_not_called()


def test_sync_lifecycle_preserves_snapshot_and_independent_storage(external_apis, settings):
    settings.SYNC_BKBASE_CLUSTER_INFO_UPDATE = False
    list_api, _ = external_apis
    first, second = remote_cluster(), remote_cluster("query-b")
    list_api.return_value = [first, second]
    original_cluster_count = models.ClusterInfo.objects.count()
    original_config_count = ClusterConfig.objects.count()

    assert sync_bkbase_vm_query_clusters("tenant-a")
    list_api.assert_called_once_with(bk_tenant_id="tenant-a", namespace="bkmonitor", kind="vmqueryclusters")
    record = VmQueryClusterConfig.objects.get(name="query-a")
    assert record.cluster_name == "logical-query-a"
    assert record.origin_config == first
    assert record.status == "Ok"
    assert record.last_synced_at is not None
    original_id = record.pk
    original_synced_at = record.last_synced_at

    changed = copy.deepcopy(first)
    changed["spec"].update(clusterDomain="new.example.com", monitorStorageClusters=["monitor-new"])
    changed["metadata"]["annotations"] = {"extension": "preserved"}
    list_api.return_value = [changed]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    record.refresh_from_db()
    assert record.pk == original_id
    assert record.last_synced_at > original_synced_at
    assert record.cluster_domain == "new.example.com"
    assert record.monitor_storage_clusters == ["monitor-new"]
    assert record.origin_config == changed
    disappeared = VmQueryClusterConfig.objects.get(name="query-b")
    assert disappeared.status == "Terminated"
    assert disappeared.origin_config == second

    list_api.return_value = []
    assert sync_bkbase_vm_query_clusters("tenant-a")
    assert set(VmQueryClusterConfig.objects.values_list("status", flat=True)) == {"Terminated"}
    list_api.return_value = [second]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    disappeared.refresh_from_db()
    assert disappeared.status == "Ok"
    assert VmQueryClusterConfig.objects.count() == 2
    assert models.ClusterInfo.objects.count() == original_cluster_count
    assert ClusterConfig.objects.count() == original_config_count
    assert VmQueryClusterConfig.kind not in COMPONENT_CLASS_MAP
    assert not hasattr(record, "compose_config")
    assert not hasattr(record, "delete_config")


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("kind",), "VmStorage"),
        (("metadata",), []),
        (("metadata", "name"), ""),
        (("metadata", "namespace"), "other"),
        (("metadata", "tenant"), "other"),
        (("spec",), None),
        (("spec", "clusterDomain"), ""),
        (("spec", "clusterName"), "x" * 256),
        (("spec", "version"), None),
        (("spec", "numReplicas"), True),
        (("spec", "numReplicas"), 0),
        (("spec", "numReplicas"), "3"),
        (("spec", "monitorStorageClusters"), "monitor-0"),
        (("spec", "monitorStorageClusters"), [None]),
        (("status",), "Ok"),
        (("status", "phase"), None),
    ],
)
def test_invalid_item_rejects_entire_batch(external_apis, path, value):
    list_api, _ = external_apis
    list_api.return_value = [remote_cluster()]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    before = list(VmQueryClusterConfig.objects.values())
    invalid = remote_cluster("invalid")
    target = invalid
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    list_api.return_value = [remote_cluster("new"), invalid]
    assert not sync_bkbase_vm_query_clusters("tenant-a")
    assert list(VmQueryClusterConfig.objects.values()) == before


@pytest.mark.parametrize("response", [None, {}, "", [None], [remote_cluster(), remote_cluster()]])
def test_invalid_list_does_not_invalidate_existing_records(external_apis, response):
    list_api, _ = external_apis
    list_api.return_value = [remote_cluster()]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    before = list(VmQueryClusterConfig.objects.values())
    list_api.return_value = response
    assert not sync_bkbase_vm_query_clusters("tenant-a")
    assert list(VmQueryClusterConfig.objects.values()) == before


def test_request_failure_and_database_failure_preserve_batch(external_apis, mocker):
    list_api, _ = external_apis
    list_api.return_value = [remote_cluster()]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    before = list(VmQueryClusterConfig.objects.values())
    list_api.side_effect = RuntimeError("BKBase unavailable")
    assert not sync_bkbase_vm_query_clusters("tenant-a")
    assert list(VmQueryClusterConfig.objects.values()) == before

    list_api.side_effect = None
    list_api.return_value = [remote_cluster("new-a"), remote_cluster("new-b")]
    update_or_create = VmQueryClusterConfig.objects.update_or_create

    def fail_second_write(**kwargs):
        if kwargs["name"] == "new-b":
            raise IntegrityError("simulated database failure")
        return update_or_create(**kwargs)

    mocker.patch.object(VmQueryClusterConfig.objects, "update_or_create", side_effect=fail_second_write)
    assert not sync_bkbase_vm_query_clusters("tenant-a")
    assert list(VmQueryClusterConfig.objects.values()) == before


def test_sync_scope_isolation(external_apis):
    list_api, _ = external_apis
    for tenant, namespace in [("tenant-a", "bkmonitor"), ("tenant-b", "bkmonitor"), ("tenant-a", "other")]:
        list_api.return_value = [remote_cluster(tenant=tenant, namespace=namespace)]
        assert sync_bkbase_vm_query_clusters(tenant, namespace)

    other_scopes = VmQueryClusterConfig.objects.exclude(bk_tenant_id="tenant-a", namespace="bkmonitor").order_by("id")
    before = list(other_scopes.values())
    assert len(before) == 2
    list_api.return_value = []
    assert sync_bkbase_vm_query_clusters("tenant-a")
    assert VmQueryClusterConfig.objects.get(bk_tenant_id="tenant-a", namespace="bkmonitor").status == "Terminated"
    assert list(other_scopes.values()) == before


def test_identity_unique_constraint(external_apis):
    external_apis[0].return_value = [remote_cluster()]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    values = VmQueryClusterConfig.objects.values().get()
    values.pop("id")
    with pytest.raises(IntegrityError), transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        VmQueryClusterConfig.objects.create(**values)


def test_single_tenant_remote_identity_and_unreconciled_resource(external_apis, settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    resource = remote_cluster(tenant="default")
    resource.pop("kind")
    resource["status"] = None
    external_apis[0].return_value = [resource]
    assert sync_bkbase_vm_query_clusters("system")
    record = VmQueryClusterConfig.objects.get()
    assert record.bk_tenant_id == "system"
    assert record.origin_config["metadata"]["tenant"] == "default"
    assert record.status == ""


def test_admin_reads_independent_model_and_live_config(external_apis):
    list_api, get_api = external_apis
    resource = remote_cluster()
    list_api.return_value = [resource, remote_cluster("query-b")]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    list_api.return_value = [resource]
    assert sync_bkbase_vm_query_clusters("tenant-a")
    params = {"bk_tenant_id": "tenant-a", "namespace": "bkmonitor", "kind": "VmQueryCluster"}

    response = list_components({**params, "page_size": 1})["data"]
    assert response["total"] == 2
    assert len(response["items"]) == 1
    terminated = list_components({**params, "statuses": ["Terminated"]})["data"]["items"]
    assert [item["name"] for item in terminated] == ["query-b"]
    assert list_components({**params, "bk_tenant_id": "other"})["data"]["total"] == 0
    assert list_components({**params, "namespace": "other"})["data"]["total"] == 0

    detail = get_component_detail({**params, "name": "query-a"})["data"]
    assert detail["cluster_name"] == "logical-query-a"
    assert detail["monitor_storage_clusters"] == ["monitor-0", "monitor-4"]
    assert detail["origin_config"] == resource
    assert detail["last_synced_at"]
    assert "data_link_name" not in detail
    assert "bk_biz_id" not in detail
    get_api.assert_not_called()
    get_api.return_value = resource
    live = get_component_config({**params, "name": "query-a"})["data"]
    assert live["component_config"] == resource
    get_api.assert_called_once_with(
        bk_tenant_id="tenant-a", namespace="bkmonitor", kind="vmqueryclusters", name="query-a"
    )
    detail = get_component_detail({**params, "name": "query-a", "include": ["component_config"]})["data"]
    assert detail["component_config"] == resource
    with pytest.raises(CustomException):
        get_component_detail({**params, "bk_tenant_id": "other", "name": "query-a"})


def test_periodic_sync_continues_after_failed_vm_query_batch(external_apis, mocker):
    mocker.patch.object(api.bk_login, "list_tenant", return_value=[{"id": "tenant-a"}, {"id": "tenant-b"}])

    def list_resources(**kwargs):
        if kwargs["kind"] == "vmqueryclusters":
            if kwargs["bk_tenant_id"] == "tenant-a":
                raise RuntimeError("temporarily unavailable")
            return [remote_cluster(tenant="tenant-b")]
        return []

    external_apis[0].side_effect = list_resources
    sync_all_bkbase_cluster_info.__wrapped__()
    assert VmQueryClusterConfig.objects.get().bk_tenant_id == "tenant-b"
    assert any(call.kwargs["kind"] == "vmstorages" for call in external_apis[0].call_args_list)


def test_tenant_initialization_syncs_vm_query(external_apis, mocker):
    mocker.patch("metadata.task.tenant.BKBASE_V4_KIND_STORAGE_CONFIGS", [])
    vm_clusters = mocker.Mock()
    vm_clusters.__bool__ = mocker.Mock(return_value=True)
    vm_clusters.__iter__ = mocker.Mock(return_value=iter([mocker.Mock(is_default_cluster=True)]))
    mocker.patch.object(models.ClusterInfo.objects, "filter", return_value=vm_clusters)
    external_apis[0].return_value = [remote_cluster()]
    _init_bkbase_cluster("tenant-a")
    assert VmQueryClusterConfig.objects.get().name == "query-a"


def test_vm_query_kind_mapping():
    assert DataLinkKind.get_choice_value(DataLinkKind.VMQUERYCLUSTER.value) == "vmqueryclusters"
