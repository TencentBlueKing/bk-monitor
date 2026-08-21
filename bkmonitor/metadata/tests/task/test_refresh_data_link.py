"""DataLink 组件状态批量刷新测试。"""

from unittest.mock import call

import pytest

from metadata import models
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import COMPONENT_CLASS_MAP
from metadata.task.refresh_data_link import refresh_data_link_status
from metadata.task.bkbase import (
    _check_storage_binding_reference,
    _reconcile_data_link_components,
    _refresh_bkbase_result_table_statuses,
    batch_check_storage_binding_references,
)


def _remote_component(name: str, status: str) -> dict:
    return {
        "metadata": {"name": name, "labels": {"bk_biz_id": "2"}, "annotations": {}},
        "spec": {"bizId": 2, "dataType": "metric"},
        "status": {"phase": status},
    }


def _remote_databus_component(name: str, status: str) -> dict:
    return {
        "metadata": {"name": name, "labels": {"bk_biz_id": "2"}, "annotations": {}},
        "spec": {
            "sources": [{"kind": DataLinkKind.DATAID.value, "name": f"{name}_data_id"}],
            "sinks": [{"kind": DataLinkKind.RESULTTABLE.value, "name": f"{name}_rt"}],
        },
        "status": {"phase": status},
    }


def _remote_component_for_kind(kind: str, name: str) -> dict:
    if kind == DataLinkKind.RESULTTABLE.value:
        return _remote_component(name, DataLinkResourceStatus.OK.value)
    if kind == DataLinkKind.DATABUS.value:
        return _remote_databus_component(name, DataLinkResourceStatus.OK.value)

    metadata = {"name": name, "labels": {"bk_biz_id": "2"}, "annotations": {}}
    spec = {}
    if kind == DataLinkKind.DATAID.value:
        metadata["annotations"] = {"dataId": "60010"}
    elif kind == DataLinkKind.CHANNELBINDING.value:
        spec = {
            "data": {"kind": DataLinkKind.RESULTTABLE.value, "name": "discovered_result_table"},
            "channel": {"kind": DataLinkKind.KAFKACHANNEL.value, "name": "kafka_inner"},
        }
    elif kind in {
        DataLinkKind.VMSTORAGEBINDING.value,
        DataLinkKind.ESSTORAGEBINDING.value,
        DataLinkKind.DORISBINDING.value,
        DataLinkKind.SURREALDBBINDING.value,
    }:
        spec = {"storage": {"name": f"{name}_storage"}, "data": {"name": "discovered_result_table"}}
        if kind == DataLinkKind.SURREALDBBINDING.value:
            spec.update({"table_type": "normal", "vertices": [], "relations": []})
    elif kind == DataLinkKind.BASEREPORTSINK.value:
        spec = {
            "mappings": [{"sinks": [{"kind": DataLinkKind.VMSTORAGEBINDING.value, "name": "discovered_vm_binding"}]}]
        }
    return {"metadata": metadata, "spec": spec, "status": {"phase": DataLinkResourceStatus.OK.value}}


def _remote_storage_binding(
    *,
    binding_kind: str,
    storage_kind: str,
    name: str = "binding_name",
    namespace: str = "bklog",
    tenant: str | None = "default",
    storage_name: str = "storage_name",
    include_related_res_asset: bool = True,
    related_res_asset: str | None = None,
    include_index1: bool = True,
    index1: str | None = None,
    status: str = DataLinkResourceStatus.OK.value,
) -> dict:
    reference_parts = [storage_kind]
    if tenant and tenant != "default":
        reference_parts.append(tenant)
    reference_parts.extend([namespace, storage_name])
    expected_reference = "/".join(reference_parts)

    labels = {"bk_biz_id": "2"}
    if include_related_res_asset:
        labels["related_res_asset"] = expected_reference if related_res_asset is None else related_res_asset
    annotations = {}
    if include_index1:
        annotations["index1"] = expected_reference if index1 is None else index1

    metadata = {"name": name, "namespace": namespace, "labels": labels, "annotations": annotations}
    storage = {"kind": storage_kind, "namespace": namespace, "name": storage_name}
    if tenant is not None:
        metadata["tenant"] = tenant
        storage["tenant"] = tenant

    return {
        "kind": binding_kind,
        "metadata": metadata,
        "spec": {"storage": storage, "data": {"name": f"{name}_rt"}},
        "status": {"phase": status},
    }


def _create_bkbase_result_table(data_link_name: str, *, tenant: str = "system", status: str = "Creating"):
    return models.BkBaseResultTable.objects.create(
        bk_tenant_id=tenant,
        data_link_name=data_link_name,
        monitor_table_id=f"{data_link_name}.__default__",
        status=status,
    )


def _create_result_table_component(
    name: str,
    data_link_name: str,
    *,
    tenant: str = "system",
    namespace: str = "bkmonitor",
    status: str = "Creating",
):
    return models.ResultTableConfig.objects.create(
        bk_tenant_id=tenant,
        namespace=namespace,
        name=name,
        data_link_name=data_link_name,
        bk_biz_id=2,
        status=status,
        bkbase_table_id=f"2_{name}",
        data_type="metric",
    )


def _create_databus_component(name: str, data_link_name: str, *, status: str = "Creating"):
    return models.DataBusConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name=name,
        data_link_name=data_link_name,
        data_id_name=f"{name}_data_id",
        bk_biz_id=2,
        status=status,
    )


def _create_cluster_info(
    *,
    cluster_name: str,
    cluster_type: str,
    domain_name: str,
    tenant: str = "system",
):
    return models.ClusterInfo.objects.create(
        bk_tenant_id=tenant,
        cluster_name=cluster_name,
        cluster_type=cluster_type,
        domain_name=domain_name,
        port=0,
        description="",
        is_default_cluster=False,
    )


def _mock_storage_binding_lists(mocker, configs_by_batch):
    def list_side_effect(**kwargs):
        return configs_by_batch.get((kwargs["namespace"], kwargs["kind"]), [])

    return mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=list_side_effect)


def _refresh_and_aggregate():
    statuses_by_link, untrusted_links, biz_id_by_link, refresh_stats = _reconcile_data_link_components()
    changed_bkbase_count = _refresh_bkbase_result_table_statuses(
        statuses_by_link=statuses_by_link,
        untrusted_links=untrusted_links,
        biz_id_by_link=biz_id_by_link,
    )
    return refresh_stats.updated_count + refresh_stats.terminated_count, changed_bkbase_count


@pytest.fixture(autouse=True)
def mock_status_metrics(mocker):
    mocker.patch("metadata.task.bkbase.report_metadata_data_link_status_info")
    mocker.patch("metadata.task.bkbase.api.bk_login.list_tenant", return_value=[])


def test_refresh_data_link_status_dispatches_task_without_records(mocker):
    delay = mocker.patch("metadata.task.refresh_data_link.bulk_refresh_data_link_status.delay")

    refresh_data_link_status()

    delay.assert_called_once_with()


@pytest.mark.parametrize(
    ("binding_kind", "storage_kind", "tenant", "namespace"),
    [
        (DataLinkKind.ESSTORAGEBINDING.value, DataLinkKind.ELASTICSEARCH.value, "tencent", "bklog"),
        (DataLinkKind.DORISBINDING.value, DataLinkKind.DORIS.value, "default", "bklog"),
        (DataLinkKind.VMSTORAGEBINDING.value, DataLinkKind.VMSTORAGE.value, "default", "bkmonitor"),
    ],
)
def test_check_storage_binding_reference_accepts_valid_config(binding_kind, storage_kind, tenant, namespace):
    config = _remote_storage_binding(
        binding_kind=binding_kind,
        storage_kind=storage_kind,
        tenant=tenant,
        namespace=namespace,
    )

    issue = _check_storage_binding_reference(
        config,
        bk_tenant_id=tenant,
        namespace=namespace,
        binding_kind=binding_kind,
    )

    assert issue is None


def test_check_storage_binding_reference_allows_missing_related_res_asset_and_tenant():
    config = _remote_storage_binding(
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
        storage_kind=DataLinkKind.VMSTORAGE.value,
        namespace="bkmonitor",
        tenant=None,
        include_related_res_asset=False,
    )

    issue = _check_storage_binding_reference(
        config,
        bk_tenant_id="system",
        namespace="bkmonitor",
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
    )

    assert issue is None


def test_check_storage_binding_reference_compares_only_cluster_name():
    config = _remote_storage_binding(
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
        storage_kind=DataLinkKind.VMSTORAGE.value,
        namespace="bkmonitor",
        tenant="system",
        related_res_asset="VmStorage/bkmonitor/storage_name",
        index1="VmStorage/bkmonitor/storage_name",
    )

    issue = _check_storage_binding_reference(
        config,
        bk_tenant_id="system",
        namespace="bkmonitor",
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
    )

    assert issue is None


def test_check_storage_binding_reference_allows_empty_references():
    config = _remote_storage_binding(
        binding_kind=DataLinkKind.DORISBINDING.value,
        storage_kind=DataLinkKind.DORIS.value,
        related_res_asset="",
        index1="",
    )

    issue = _check_storage_binding_reference(
        config,
        bk_tenant_id="default",
        namespace="bklog",
        binding_kind=DataLinkKind.DORISBINDING.value,
    )

    assert issue is None


def test_check_storage_binding_reference_reports_cluster_name_mismatches():
    config = _remote_storage_binding(
        binding_kind=DataLinkKind.DORISBINDING.value,
        storage_kind=DataLinkKind.DORIS.value,
        related_res_asset="Doris/bklog/old_storage",
        index1="Doris/default/bklog/old_storage",
    )

    issue = _check_storage_binding_reference(
        config,
        bk_tenant_id="default",
        namespace="bklog",
        binding_kind=DataLinkKind.DORISBINDING.value,
    )

    assert issue["problems"] == ["index1_mismatch", "related_res_asset_mismatch"]


def test_check_storage_binding_reference_reports_invalid_config():
    issue = _check_storage_binding_reference(
        {},
        bk_tenant_id="tencent",
        namespace="bklog",
        binding_kind=DataLinkKind.ESSTORAGEBINDING.value,
    )

    assert issue["problems"] == ["invalid_config", "storage_name_missing"]


@pytest.mark.django_db(databases="__all__")
def test_batch_check_storage_binding_references_checks_two_namespaces_and_three_kinds(mocker):
    invalid_config = _remote_storage_binding(
        binding_kind=DataLinkKind.DORISBINDING.value,
        storage_kind=DataLinkKind.DORIS.value,
        namespace="bklog",
        index1="Doris/bklog/old_storage",
    )
    list_data_link = mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link")

    def list_side_effect(**kwargs):
        if kwargs["namespace"] == "bklog" and kwargs["kind"] == "dorisbindings":
            return [invalid_config]
        return []

    list_data_link.side_effect = list_side_effect

    issues = batch_check_storage_binding_references("default")

    assert len(issues) == 1
    assert issues[0]["binding_kind"] == DataLinkKind.DORISBINDING.value
    assert issues[0]["problems"] == ["index1_mismatch"]
    assert list_data_link.call_args_list == [
        call(bk_tenant_id="default", namespace="bkmonitor", kind="elasticsearchbindings"),
        call(bk_tenant_id="default", namespace="bkmonitor", kind="dorisbindings"),
        call(bk_tenant_id="default", namespace="bkmonitor", kind="vmstoragebindings"),
        call(bk_tenant_id="default", namespace="bklog", kind="elasticsearchbindings"),
        call(bk_tenant_id="default", namespace="bklog", kind="dorisbindings"),
        call(bk_tenant_id="default", namespace="bklog", kind="vmstoragebindings"),
    ]


@pytest.mark.django_db(databases="__all__")
def test_batch_check_local_es_aliases_with_same_domain_are_consistent(mocker, django_assert_num_queries):
    local_cluster = _create_cluster_info(
        cluster_name="local_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name=" ES.EXAMPLE.COM ",
    )
    _create_cluster_info(
        cluster_name="remote_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.example.com",
    )
    remote_configs = []
    for index in range(2):
        table_id = f"table_{index}.__default__"
        binding_name = f"es_binding_{index}"
        models.ESStorageBindingConfig.objects.create(
            bk_tenant_id="system",
            namespace="bklog",
            name=binding_name,
            data_link_name=binding_name,
            bk_biz_id=2,
            status=DataLinkResourceStatus.OK.value,
            table_id=table_id,
            es_cluster_name="remote_es",
        )
        models.ESStorage.objects.create(
            bk_tenant_id="system",
            table_id=table_id,
            storage_cluster_id=local_cluster.cluster_id,
        )
        remote_configs.append(
            _remote_storage_binding(
                binding_kind=DataLinkKind.ESSTORAGEBINDING.value,
                storage_kind=DataLinkKind.ELASTICSEARCH.value,
                name=binding_name,
                namespace="bklog",
                tenant="system",
                storage_name="remote_es",
            )
        )

    _mock_storage_binding_lists(mocker, {("bklog", "elasticsearchbindings"): remote_configs})

    with django_assert_num_queries(3):
        issues = batch_check_storage_binding_references("system")

    assert issues == []


@pytest.mark.django_db(databases="__all__")
def test_batch_check_local_es_reports_cluster_and_domain_mismatch(mocker):
    local_cluster = _create_cluster_info(
        cluster_name="local_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="local-es.example.com",
    )
    remote_cluster = _create_cluster_info(
        cluster_name="remote_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="remote-es.example.com",
    )
    models.ESStorageBindingConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="es_binding",
        data_link_name="es_binding",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        table_id="es_table.__default__",
        es_cluster_name="remote_es",
    )
    models.ESStorage.objects.create(
        bk_tenant_id="system",
        table_id="es_table.__default__",
        storage_cluster_id=local_cluster.cluster_id,
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.ESSTORAGEBINDING.value,
        storage_kind=DataLinkKind.ELASTICSEARCH.value,
        name="es_binding",
        namespace="bklog",
        tenant="system",
        storage_name="remote_es",
    )
    _mock_storage_binding_lists(mocker, {("bklog", "elasticsearchbindings"): [remote_config]})

    issues = batch_check_storage_binding_references("system")

    assert len(issues) == 1
    assert issues[0]["problems"] == ["local_storage_cluster_mismatch"]
    assert issues[0]["local_cluster_id"] == local_cluster.cluster_id
    assert issues[0]["local_cluster_name"] == "local_es"
    assert issues[0]["local_domain_name"] == "local-es.example.com"
    assert issues[0]["remote_cluster_id"] == remote_cluster.cluster_id
    assert issues[0]["remote_cluster_name"] == "remote_es"
    assert issues[0]["remote_domain_name"] == "remote-es.example.com"


@pytest.mark.django_db(databases="__all__")
def test_batch_check_local_es_reports_missing_remote_cluster_info(mocker):
    local_cluster = _create_cluster_info(
        cluster_name="local_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="local-es.example.com",
    )
    models.ESStorageBindingConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="es_binding",
        data_link_name="es_binding",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        table_id="es_table.__default__",
        es_cluster_name="missing_remote_es",
    )
    models.ESStorage.objects.create(
        bk_tenant_id="system",
        table_id="es_table.__default__",
        storage_cluster_id=local_cluster.cluster_id,
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.ESSTORAGEBINDING.value,
        storage_kind=DataLinkKind.ELASTICSEARCH.value,
        name="es_binding",
        namespace="bklog",
        tenant="system",
        storage_name="missing_remote_es",
    )
    _mock_storage_binding_lists(mocker, {("bklog", "elasticsearchbindings"): [remote_config]})

    issues = batch_check_storage_binding_references("system")

    assert len(issues) == 1
    assert issues[0]["problems"] == ["remote_cluster_info_missing"]
    assert issues[0]["local_cluster_id"] == local_cluster.cluster_id
    assert issues[0]["remote_cluster_id"] is None
    assert issues[0]["remote_cluster_name"] == "missing_remote_es"


@pytest.mark.django_db(databases="__all__")
def test_batch_check_vm_uses_storage_cluster_id_fallback(mocker):
    vm_cluster = _create_cluster_info(
        cluster_name="vm_default",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.example.com",
    )
    models.VMStorageBindingConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="vm_binding",
        data_link_name="vm_binding",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        table_id="vm_table.__default__",
        vm_cluster_name="vm_default",
    )
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id="vm_table.__default__",
        vm_cluster_id=None,
        storage_cluster_id=vm_cluster.cluster_id,
        bk_base_data_id=1001,
        vm_result_table_id="2_vm_table",
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
        storage_kind=DataLinkKind.VMSTORAGE.value,
        name="vm_binding",
        namespace="bkmonitor",
        tenant="system",
        storage_name="vm_default",
    )
    _mock_storage_binding_lists(mocker, {("bkmonitor", "vmstoragebindings"): [remote_config]})

    assert batch_check_storage_binding_references("system") == []


@pytest.mark.parametrize(
    ("binding_name", "table_id"),
    [
        ("base_18879_sys_mem_cmdb", "tencent_18879_sys.mem_cmdb"),
        ("base_10_system_proc_perf_cmdb", "tencent_10_system_proc.perf_cmdb"),
        ("base_10_system_proc_port_cmdb", "tencent_10_system_proc.port_cmdb"),
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_batch_check_vm_ignores_cmdb_without_access_vm_record(mocker, binding_name, table_id):
    models.VMStorageBindingConfig.objects.create(
        bk_tenant_id="tencent",
        namespace="bkmonitor",
        name=binding_name,
        data_link_name=binding_name,
        bk_biz_id=10,
        status=DataLinkResourceStatus.OK.value,
        table_id=table_id,
        vm_cluster_name="monitor-bk2system",
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
        storage_kind=DataLinkKind.VMSTORAGE.value,
        name=binding_name,
        namespace="bkmonitor",
        tenant="tencent",
        storage_name="monitor-bk2system",
    )
    _mock_storage_binding_lists(mocker, {("bkmonitor", "vmstoragebindings"): [remote_config]})

    assert batch_check_storage_binding_references("tencent") == []


@pytest.mark.django_db(databases="__all__")
def test_batch_check_vm_does_not_ignore_non_cmdb_process_port(mocker):
    binding_name = "base_10_system_proc_port"
    models.VMStorageBindingConfig.objects.create(
        bk_tenant_id="tencent",
        namespace="bkmonitor",
        name=binding_name,
        data_link_name=binding_name,
        bk_biz_id=10,
        status=DataLinkResourceStatus.OK.value,
        table_id="tencent_10_system_proc.port",
        vm_cluster_name="monitor-bk2system",
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
        storage_kind=DataLinkKind.VMSTORAGE.value,
        name=binding_name,
        namespace="bkmonitor",
        tenant="tencent",
        storage_name="monitor-bk2system",
    )
    _mock_storage_binding_lists(mocker, {("bkmonitor", "vmstoragebindings"): [remote_config]})

    issues = batch_check_storage_binding_references("tencent")

    assert len(issues) == 1
    assert issues[0]["problems"] == ["local_storage_record_missing"]


@pytest.mark.django_db(databases="__all__")
def test_batch_check_doris_uses_origin_storage(mocker):
    doris_cluster = _create_cluster_info(
        cluster_name="doris_default",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="doris.example.com",
    )
    models.DorisStorageBindingConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="doris_binding",
        data_link_name="doris_binding",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        table_id="virtual_doris.__default__",
        doris_cluster_name="doris_default",
    )
    models.DorisStorage.objects.create(
        bk_tenant_id="system",
        table_id="real_doris.__default__",
        storage_cluster_id=doris_cluster.cluster_id,
    )
    models.DorisStorage.objects.create(
        bk_tenant_id="system",
        table_id="virtual_doris.__default__",
        origin_table_id="real_doris.__default__",
        storage_cluster_id=999,
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.DORISBINDING.value,
        storage_kind=DataLinkKind.DORIS.value,
        name="doris_binding",
        namespace="bklog",
        tenant="system",
        storage_name="doris_default",
    )
    _mock_storage_binding_lists(mocker, {("bklog", "dorisbindings"): [remote_config]})

    assert batch_check_storage_binding_references("system") == []


@pytest.mark.django_db(databases="__all__")
def test_batch_check_vm_reports_ambiguous_local_clusters(mocker):
    models.VMStorageBindingConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="vm_binding",
        data_link_name="vm_binding",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        table_id="vm_table.__default__",
        vm_cluster_name="vm_default",
    )
    for index, cluster_id in enumerate((101, 102), start=1):
        models.AccessVMRecord.objects.create(
            bk_tenant_id="system",
            result_table_id="vm_table.__default__",
            vm_cluster_id=cluster_id,
            bk_base_data_id=index,
            vm_result_table_id=f"2_vm_table_{index}",
        )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.VMSTORAGEBINDING.value,
        storage_kind=DataLinkKind.VMSTORAGE.value,
        name="vm_binding",
        namespace="bkmonitor",
        tenant="system",
        storage_name="vm_default",
    )
    _mock_storage_binding_lists(mocker, {("bkmonitor", "vmstoragebindings"): [remote_config]})

    issues = batch_check_storage_binding_references("system")

    assert len(issues) == 1
    assert issues[0]["problems"] == ["local_storage_cluster_ambiguous"]
    assert issues[0]["local_cluster_ids"] == [101, 102]


def test_batch_check_storage_binding_references_propagates_api_error(mocker):
    list_data_link = mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        side_effect=RuntimeError("bkbase unavailable"),
    )

    with pytest.raises(RuntimeError, match="bkbase unavailable"):
        batch_check_storage_binding_references("tencent")

    list_data_link.assert_called_once_with(
        bk_tenant_id="tencent",
        namespace="bkmonitor",
        kind="elasticsearchbindings",
    )


@pytest.mark.django_db(databases="__all__")
def test_refresh_storage_binding_reference_issue_keeps_remote_status(mocker):
    component = models.ESStorageBindingConfig.objects.create(
        bk_tenant_id="tencent",
        namespace="bklog",
        name="es_binding",
        data_link_name="es_link",
        bk_biz_id=2,
        status=DataLinkResourceStatus.CREATING.value,
        es_cluster_name="new_es",
    )
    remote_config = _remote_storage_binding(
        binding_kind=DataLinkKind.ESSTORAGEBINDING.value,
        storage_kind=DataLinkKind.ELASTICSEARCH.value,
        name=component.name,
        namespace=component.namespace,
        tenant=component.bk_tenant_id,
        storage_name="new_es",
        index1="ElasticSearch/tencent/bklog/old_es",
    )
    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", return_value=[remote_config])
    warning = mocker.patch("metadata.task.bkbase.logger.warning")

    statuses_by_link, untrusted_links, _, refresh_stats = _reconcile_data_link_components()

    component.refresh_from_db()
    assert component.status == DataLinkResourceStatus.OK.value
    assert refresh_stats.updated_count == 1
    assert statuses_by_link[("tencent", "es_link")] == [DataLinkResourceStatus.OK.value]
    assert untrusted_links == set()
    warning.assert_called_once()


@pytest.mark.django_db(databases="__all__")
def test_refresh_components_batches_by_tenant_namespace_and_kind(mocker):
    _create_result_table_component("rt_a", "link_a")
    _create_result_table_component("rt_b", "link_b")
    _create_result_table_component("rt_c", "link_c", tenant="tenant-a", namespace="bklog")

    list_data_link = mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link")

    def list_side_effect(**kwargs):
        if kwargs["bk_tenant_id"] == "system":
            return [
                _remote_component("rt_a", DataLinkResourceStatus.OK.value),
                _remote_component("rt_b", DataLinkResourceStatus.PENDING.value),
            ]
        return [_remote_component("rt_c", DataLinkResourceStatus.FAILED.value)]

    list_data_link.side_effect = list_side_effect

    _, _, _, refresh_stats = _reconcile_data_link_components()

    assert refresh_stats.updated_count == 3
    assert models.ResultTableConfig.objects.get(name="rt_a").status == DataLinkResourceStatus.OK.value
    assert models.ResultTableConfig.objects.get(name="rt_b").status == DataLinkResourceStatus.PENDING.value
    assert models.ResultTableConfig.objects.get(name="rt_c").status == DataLinkResourceStatus.FAILED.value
    assert list_data_link.call_args_list == [
        call(bk_tenant_id="system", namespace="bkmonitor", kind="resulttables"),
        call(bk_tenant_id="tenant-a", namespace="bklog", kind="resulttables"),
    ]


@pytest.mark.django_db(databases="__all__")
def test_refresh_discovers_all_component_kinds_without_local_records(mocker):
    mocker.patch("metadata.task.bkbase.api.bk_login.list_tenant", return_value=[{"id": "tenant-a"}])
    remote_configs = {
        DataLinkKind.get_choice_value(kind): _remote_component_for_kind(kind, f"discovered_{kind.lower()}")
        for kind in COMPONENT_CLASS_MAP
    }
    remote_configs["resulttables"] = _remote_component_for_kind(
        DataLinkKind.RESULTTABLE.value,
        "discovered_result_table",
    )
    list_data_link = mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link")

    def list_side_effect(**kwargs):
        if kwargs["namespace"] == "bkmonitor":
            return [remote_configs[kwargs["kind"]]]
        return []

    list_data_link.side_effect = list_side_effect

    _, _, _, refresh_stats = _reconcile_data_link_components()

    assert refresh_stats.created_count == len(COMPONENT_CLASS_MAP)
    assert refresh_stats.untrusted_batch_count == len(COMPONENT_CLASS_MAP)
    assert list_data_link.call_count == len(COMPONENT_CLASS_MAP) * 2
    for kind, component_class in COMPONENT_CLASS_MAP.items():
        name = "discovered_result_table" if kind == DataLinkKind.RESULTTABLE.value else f"discovered_{kind.lower()}"
        component = component_class.objects.get(bk_tenant_id="tenant-a", namespace="bkmonitor", name=name)
        assert component.status == DataLinkResourceStatus.OK.value
        assert component.data_link_name == ""


@pytest.mark.django_db(databases="__all__")
def test_refresh_uses_one_response_for_config_status_and_aggregation(mocker):
    component = _create_result_table_component("reconcile_rt", "reconcile_link")
    component.bkbase_table_id = "old_table_id"
    component.save(update_fields=["bkbase_table_id", "last_modify_time"])
    bkbase_record = _create_bkbase_result_table("reconcile_link")
    list_data_link = mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        return_value=[_remote_component("reconcile_rt", DataLinkResourceStatus.OK.value)],
    )

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 1
    assert changed_bkbase_count == 1
    assert component.bkbase_table_id == "2_reconcile_rt"
    assert component.status == DataLinkResourceStatus.OK.value
    assert bkbase_record.status == DataLinkResourceStatus.OK.value
    list_data_link.assert_called_once_with(
        bk_tenant_id="system",
        namespace="bkmonitor",
        kind="resulttables",
    )


@pytest.mark.django_db(databases="__all__")
def test_refresh_tenant_discovery_failure_still_refreshes_local_custom_namespace(mocker):
    component = _create_result_table_component("custom_rt", "custom_link", namespace="custom")
    mocker.patch("metadata.task.bkbase.api.bk_login.list_tenant", side_effect=RuntimeError("tenant unavailable"))
    list_data_link = mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        return_value=[_remote_component("custom_rt", DataLinkResourceStatus.OK.value)],
    )

    _, _, _, refresh_stats = _reconcile_data_link_components()

    component.refresh_from_db()
    assert refresh_stats.updated_count == 1
    assert component.status == DataLinkResourceStatus.OK.value
    list_data_link.assert_called_once_with(
        bk_tenant_id="system",
        namespace="custom",
        kind="resulttables",
    )


@pytest.mark.django_db(databases="__all__")
def test_refresh_updates_databus_consumer_group(mocker):
    component = _create_databus_component("consumer_databus", "consumer_link")
    remote_config = _remote_databus_component("consumer_databus", DataLinkResourceStatus.OK.value)
    remote_config["spec"]["consumerGroup"] = "bkmonitor_consumer"
    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", return_value=[remote_config])

    _, _, _, refresh_stats = _reconcile_data_link_components()

    component.refresh_from_db()
    assert refresh_stats.updated_count == 1
    assert component.consumer_group == "bkmonitor_consumer"
    assert component.status == DataLinkResourceStatus.OK.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_updates_empty_surrealdb_definitions(mocker):
    component = models.SurrealDBBindingConfig.objects.create(
        name="graph_rt",
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_name="graph_link",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="graph_rt",
        table_type="normal",
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    remote_config = _remote_component_for_kind(DataLinkKind.SURREALDBBINDING.value, "graph_rt")
    remote_config["spec"]["storage"]["name"] = "surreal-default"
    remote_config["spec"]["data"]["name"] = "graph_rt"
    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", return_value=[remote_config])

    _reconcile_data_link_components()

    component.refresh_from_db()
    assert component.vertices == []
    assert component.relations == []


@pytest.mark.django_db(databases="__all__")
def test_refresh_keeps_falsy_non_surrealdb_fields(mocker):
    component = models.DataIdConfig.objects.create(
        name="metric_data",
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_name="metric_link",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        bk_data_id=60010,
    )
    remote_config = _remote_component_for_kind(DataLinkKind.DATAID.value, "metric_data")
    remote_config["metadata"]["annotations"] = {}
    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", return_value=[remote_config])

    _, _, _, refresh_stats = _reconcile_data_link_components()

    component.refresh_from_db()
    assert refresh_stats.updated_count == 0
    assert component.bk_data_id == 60010


@pytest.mark.django_db(databases="__all__")
def test_refresh_storage_bindings_fill_table_id_from_result_table(mocker):
    result_table = _create_result_table_component("graph_rt", "graph_link", status=DataLinkResourceStatus.OK.value)
    result_table.table_id = "2_graph_rt.__default__"
    result_table.save(update_fields=["table_id", "last_modify_time"])
    vm_binding = models.VMStorageBindingConfig.objects.create(
        name="graph_vm",
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_name="graph_link",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        vm_cluster_name="vm-default",
        bkbase_result_table_name="graph_rt",
    )
    surrealdb_binding = models.SurrealDBBindingConfig.objects.create(
        name="graph_surrealdb",
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_name="graph_link",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="graph_rt",
    )

    def list_side_effect(**kwargs):
        if kwargs["kind"] == "resulttables":
            return [_remote_component("graph_rt", DataLinkResourceStatus.OK.value)]
        if kwargs["kind"] == "vmstoragebindings":
            config = _remote_component_for_kind(DataLinkKind.VMSTORAGEBINDING.value, "graph_vm")
            config["spec"]["data"]["name"] = "graph_rt"
            return [config]
        config = _remote_component_for_kind(DataLinkKind.SURREALDBBINDING.value, "graph_surrealdb")
        config["spec"]["data"]["name"] = "graph_rt"
        return [config]

    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=list_side_effect)

    _reconcile_data_link_components()

    vm_binding.refresh_from_db()
    surrealdb_binding.refresh_from_db()
    assert vm_binding.table_id == "2_graph_rt.__default__"
    assert surrealdb_binding.table_id == "2_graph_rt.__default__"


@pytest.mark.django_db(databases="__all__")
def test_refresh_marks_missing_component_and_link_terminated(mocker):
    component = _create_result_table_component("missing_rt", "terminated_link")
    bkbase_record = _create_bkbase_result_table("terminated_link")
    mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        return_value=[_remote_component("another_rt", DataLinkResourceStatus.OK.value)],
    )

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 1
    assert changed_bkbase_count == 1
    assert component.status == DataLinkResourceStatus.TERMINATED.value
    assert bkbase_record.status == DataLinkResourceStatus.TERMINATED.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_aggregates_mixed_component_status_as_pending(mocker):
    _create_result_table_component("mixed_rt", "mixed_link")
    _create_databus_component("mixed_databus", "mixed_link")
    bkbase_record = _create_bkbase_result_table("mixed_link", status=DataLinkResourceStatus.OK.value)

    def list_side_effect(**kwargs):
        if kwargs["kind"] == "resulttables":
            return [_remote_component("mixed_rt", DataLinkResourceStatus.OK.value)]
        return [_remote_databus_component("mixed_databus", DataLinkResourceStatus.FAILED.value)]

    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=list_side_effect)

    _refresh_and_aggregate()

    bkbase_record.refresh_from_db()
    assert bkbase_record.status == DataLinkResourceStatus.PENDING.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_aggregates_all_ok_components_as_ok(mocker):
    _create_result_table_component("ok_rt", "ok_link")
    _create_databus_component("ok_databus", "ok_link")
    bkbase_record = _create_bkbase_result_table("ok_link")

    def list_side_effect(**kwargs):
        if kwargs["kind"] == "resulttables":
            return [_remote_component("ok_rt", DataLinkResourceStatus.OK.value)]
        return [_remote_databus_component("ok_databus", DataLinkResourceStatus.OK.value)]

    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=list_side_effect)

    _refresh_and_aggregate()

    bkbase_record.refresh_from_db()
    assert bkbase_record.status == DataLinkResourceStatus.OK.value


@pytest.mark.parametrize(
    "remote_result",
    [
        [],
        [{}],
        [{"metadata": {"name": "safe_rt"}, "status": {}}],
        [{"metadata": {"name": "safe_rt"}, "status": {"phase": "Ok"}}],
        "invalid",
    ],
)
@pytest.mark.django_db(databases="__all__")
def test_refresh_skips_empty_or_invalid_batch(mocker, remote_result):
    component = _create_result_table_component("safe_rt", "safe_link")
    bkbase_record = _create_bkbase_result_table("safe_link")
    component_modify_time = component.last_modify_time
    bkbase_modify_time = bkbase_record.last_modify_time
    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", return_value=remote_result)

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 0
    assert changed_bkbase_count == 0
    assert component.status == DataLinkResourceStatus.CREATING.value
    assert component.last_modify_time == component_modify_time
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.last_modify_time == bkbase_modify_time


@pytest.mark.django_db(databases="__all__")
def test_refresh_skips_failed_batch_and_link_aggregation(mocker):
    component = _create_result_table_component("failed_batch_rt", "failed_batch_link")
    bkbase_record = _create_bkbase_result_table("failed_batch_link")
    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=RuntimeError("bkbase unavailable"))

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 0
    assert changed_bkbase_count == 0
    assert component.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_rolls_back_failed_batch_and_skips_link_aggregation(mocker):
    component = _create_result_table_component("rollback_rt", "rollback_link")
    bkbase_record = _create_bkbase_result_table("rollback_link")
    mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        return_value=[_remote_component("rollback_rt", DataLinkResourceStatus.OK.value)],
    )
    mocker.patch.object(models.ResultTableConfig.objects, "bulk_update", side_effect=RuntimeError("db unavailable"))

    statuses_by_link, untrusted_links, biz_id_by_link, refresh_stats = _reconcile_data_link_components()
    changed_bkbase_count = _refresh_bkbase_result_table_statuses(
        statuses_by_link=statuses_by_link,
        untrusted_links=untrusted_links,
        biz_id_by_link=biz_id_by_link,
    )

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert refresh_stats.updated_count == 0
    assert refresh_stats.untrusted_batch_count == 1
    assert changed_bkbase_count == 0
    assert component.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value
    assert ("system", "rollback_link") in untrusted_links


@pytest.mark.django_db(databases="__all__")
def test_refresh_skips_link_aggregation_when_one_component_batch_is_untrusted(mocker):
    result_table = _create_result_table_component("partial_rt", "partial_link")
    databus = _create_databus_component("partial_databus", "partial_link")
    bkbase_record = _create_bkbase_result_table("partial_link")

    def list_side_effect(**kwargs):
        if kwargs["kind"] == "resulttables":
            return [_remote_component("partial_rt", DataLinkResourceStatus.OK.value)]
        return []

    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=list_side_effect)

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    result_table.refresh_from_db()
    databus.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 1
    assert changed_bkbase_count == 0
    assert result_table.status == DataLinkResourceStatus.OK.value
    assert databus.status == DataLinkResourceStatus.CREATING.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value


@pytest.mark.django_db(databases="__all__")
def test_refresh_does_not_write_unchanged_status(mocker):
    component = _create_result_table_component(
        "unchanged_rt",
        "unchanged_link",
        status=DataLinkResourceStatus.OK.value,
    )
    bkbase_record = _create_bkbase_result_table("unchanged_link", status=DataLinkResourceStatus.OK.value)
    component_modify_time = component.last_modify_time
    bkbase_modify_time = bkbase_record.last_modify_time
    mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        return_value=[_remote_component("unchanged_rt", DataLinkResourceStatus.OK.value)],
    )

    changed_count, changed_bkbase_count = _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert changed_count == 0
    assert changed_bkbase_count == 0
    assert component.last_modify_time == component_modify_time
    assert bkbase_record.last_modify_time == bkbase_modify_time


@pytest.mark.django_db(databases="__all__")
def test_refresh_component_without_data_link_does_not_update_bkbase_status(mocker):
    component = _create_result_table_component("orphan_rt", "")
    bkbase_record = _create_bkbase_result_table("orphan_link")
    mocker.patch(
        "metadata.task.bkbase.api.bkdata.list_data_link",
        return_value=[_remote_component("orphan_rt", DataLinkResourceStatus.OK.value)],
    )

    _refresh_and_aggregate()

    component.refresh_from_db()
    bkbase_record.refresh_from_db()
    assert component.status == DataLinkResourceStatus.OK.value
    assert bkbase_record.status == DataLinkResourceStatus.CREATING.value
