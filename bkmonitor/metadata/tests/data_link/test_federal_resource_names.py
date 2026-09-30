"""Federation reuses shared historical resources before allocating new names."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections

from metadata import models
from metadata.models.data_link import utils
from metadata.models.vm.utils import _ensure_named_data_link, create_bkbase_data_link

pytestmark = pytest.mark.django_db(databases="__all__")
TABLE = "federal.proxy"
VM = "federal-test-vm"


@pytest.fixture
def source(mocker):
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    mocker.patch.object(models.DataLink, "get_existing_component_config", return_value=None)
    mocker.patch.object(models.DataLink, "apply_data_link_with_retry", return_value={})
    ds = models.DataSource.objects.create(
        bk_tenant_id="system",
        bk_data_id=970001,
        data_name="federal-source",
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=False,
        etl_config="bk_standard_v2_time_series",
    )
    models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id=TABLE,
        table_name_zh="test",
        is_custom_table=True,
        bk_biz_id=2,
        creator="system",
    )
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        name="saved_source",
        namespace="bkmonitor",
        bk_data_id=ds.pk,
        bk_biz_id=2,
    )
    models.ClusterInfo.objects.create(
        cluster_id=970001,
        cluster_name=VM,
        is_default_cluster=False,
        cluster_type=models.ClusterInfo.TYPE_VM,
        bk_tenant_id="system",
        domain_name="localhost",
        port=8428,
        description="test",
    )
    return ds


def proxy_link(source):
    return _ensure_named_data_link(source, TABLE, models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES, "bkmonitor")[0]


def historical_components(source, *, record=True):
    scope = dict(bk_tenant_id="system", namespace="bkmonitor", data_link_name="", bk_biz_id=0)
    rt = models.ResultTableConfig.objects.create(name="historical_rt", bkbase_table_id="42_historical_rt", **scope)
    binding = models.VMStorageBindingConfig.objects.create(
        name="historical_binding",
        bkbase_result_table_name=rt.name,
        vm_cluster_name=VM,
        **scope,
    )
    if record:
        models.AccessVMRecord.objects.create(
            bk_tenant_id="system",
            result_table_id=TABLE,
            vm_result_table_id=rt.bkbase_table_id,
            bk_base_data_id=source.pk,
            bk_base_data_name="saved_source",
            vm_cluster_id=970001,
        )
    return rt, binding


def compose_proxy(link, source):
    return link.compose_configs(bk_biz_id=2, data_source=source, table_id=TABLE, storage_cluster_name=VM)


def make_subset(source, name="saved_subset"):
    table_id = f"federal.{name}"
    models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        table_name_zh="test",
        is_custom_table=True,
        bk_biz_id=2,
        creator="system",
    )
    link = models.DataLink.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        data_link_name=name,
        data_link_strategy=models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
        bk_data_id=source.pk,
        table_ids=[table_id],
    )
    return link


def compose_subset(link, source):
    return link.compose_configs(
        bk_biz_id=2,
        data_source=source,
        table_id=link.table_ids[0],
        storage_cluster_name=VM,
        federation_routes=[dict(fed_cluster_id="BCS-K8S-PROXY", namespaces=["ns1"], target_metric_table_id=TABLE)],
    )


@pytest.mark.parametrize("reuse", [False, True])
@pytest.mark.parametrize("mapping", ["access", "bkbase", "both"])
def test_proxy_repairs_historical_components_in_place(source, mocker, settings, reuse, mapping):
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = {models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES} if reuse else set()
    link = proxy_link(source)
    rt, binding = historical_components(source, record=mapping != "bkbase")
    if mapping != "access":
        models.BkBaseResultTable.objects.filter(pk=link.pk).update(bkbase_table_id=rt.bkbase_table_id)
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    first = compose_proxy(link, source)
    assert compose_proxy(link, source) == first
    rt.refresh_from_db()
    binding.refresh_from_db()
    assert (rt.data_link_name, rt.table_id, rt.bk_biz_id) == (link.pk, TABLE, 2)
    assert (binding.data_link_name, binding.table_id, binding.bk_biz_id) == (link.pk, TABLE, 2)
    assert rt.bkbase_table_id == "42_historical_rt"
    assert first[0]["metadata"]["name"] == rt.name
    assert first[0]["spec"]["bizId"] == 42
    assert first[1]["metadata"]["name"] == binding.name
    assert first[1]["spec"]["data"]["name"] == rt.name
    assert models.ResultTableConfig.objects.count() == models.VMStorageBindingConfig.objects.count() == 1
    generate.assert_not_called()


def test_subset_uses_ownerless_binding_without_claiming_it(source):
    rt, binding = historical_components(source)
    subset = make_subset(source)
    result = compose_subset(subset, source)
    assert result[0]["spec"]["conditions"][0]["sinks"][0]["name"] == binding.name
    rt.refresh_from_db()
    binding.refresh_from_db()
    assert rt.data_link_name == binding.data_link_name == ""
    assert rt.table_id == binding.table_id == ""


def test_shared_binding_survives_subsets_and_subset_deletion(source, mocker):
    parent = proxy_link(source)
    rt, binding = historical_components(source)
    compose_proxy(parent, source)
    children = [make_subset(source, f"subset_{i}") for i in range(2)]
    for child in children:
        compose_subset(child, source)
    delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")
    # Even an old child-owned RT/Binding must not be included in subset deletion.
    models.ResultTableConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="child_legacy_rt",
        data_link_name=children[0].pk,
        bk_biz_id=2,
    )
    children[0].delete_data_link()
    assert {call.kwargs["kind"] for call in delete.call_args_list} == {"databuses", "conditionalsinks"}
    assert models.ResultTableConfig.objects.filter(pk=rt.pk).exists()
    assert models.VMStorageBindingConfig.objects.filter(pk=binding.pk).exists()
    assert models.ResultTableConfig.objects.filter(name="child_legacy_rt").exists()
    assert compose_subset(children[1], source)[0]["spec"]["conditions"][0]["sinks"][0]["name"] == binding.name


@pytest.mark.parametrize(
    "kind,field,value",
    [
        ("rt", "data_link_name", "foreign_link"),
        ("binding", "data_link_name", "foreign_link"),
        ("rt", "table_id", "foreign.table"),
        ("binding", "table_id", "foreign.table"),
        ("binding", "vm_cluster_name", "other-vm"),
    ],
)
def test_proxy_rejects_conflicts_without_creating_resources(source, mocker, kind, field, value):
    link = proxy_link(source)
    rt, binding = historical_components(source)
    component = rt if kind == "rt" else binding
    setattr(component, field, value)
    component.save(update_fields=[field])
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name")
    with pytest.raises(ValueError):
        compose_proxy(link, source)
    assert models.ResultTableConfig.objects.count() == models.VMStorageBindingConfig.objects.count() == 1
    rt.refresh_from_db()
    assert rt.bk_biz_id == 0
    generate.assert_not_called()


@pytest.mark.parametrize("kind", ["rt", "binding"])
def test_ambiguous_fallback_fails(source, mocker, kind):
    parent = proxy_link(source)
    rt, binding = historical_components(source)
    component = rt if kind == "rt" else binding
    component.pk = None
    component.name += "_duplicate"
    component.save()
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name")
    with pytest.raises((ValueError, models.ResultTableConfig.MultipleObjectsReturned)):
        compose_proxy(parent, source)
    with pytest.raises(ValueError):
        compose_subset(make_subset(source), source)
    generate.assert_not_called()


def test_normal_binding_association_wins_over_unowned_duplicate(source):
    parent = proxy_link(source)
    rt, binding = historical_components(source)
    compose_proxy(parent, source)
    binding.pk = None
    binding.name = "unowned_duplicate"
    binding.data_link_name = ""
    binding.table_id = ""
    binding.save()
    assert compose_proxy(parent, source)[1]["metadata"]["name"] == "historical_binding"
    assert (
        compose_subset(make_subset(source), source)[0]["spec"]["conditions"][0]["sinks"][0]["name"]
        == "historical_binding"
    )


def test_subset_selects_actual_parent_storage(source):
    rt, binding = historical_components(source)
    other = models.VMStorageBindingConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="other_cluster_binding",
        bk_biz_id=0,
        bkbase_result_table_name=rt.name,
        vm_cluster_name="other-vm",
    )
    result = compose_subset(make_subset(source), source)
    assert result[0]["spec"]["conditions"][0]["sinks"][0]["name"] == binding.name
    other.refresh_from_db()
    assert other.data_link_name == ""


@pytest.mark.parametrize("field,value", [("bk_tenant_id", "other"), ("namespace", "other")])
def test_historical_lookup_is_isolated(source, mocker, field, value):
    parent = proxy_link(source)
    rt, binding = historical_components(source)
    for component in (rt, binding):
        setattr(component, field, value)
        component.save(update_fields=[field])
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name")
    with pytest.raises(ValueError, match="config missing"):
        compose_proxy(parent, source)
    with pytest.raises(ValueError, match="ResultTable"):
        compose_subset(make_subset(source), source)
    generate.assert_not_called()


def test_conflicting_persisted_vmrt_fails(source, mocker):
    parent = proxy_link(source)
    historical_components(source)
    models.BkBaseResultTable.objects.filter(pk=parent.pk).update(bkbase_table_id="42_other_rt")
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name")
    with pytest.raises(ValueError, match="conflicting federation VMRTs"):
        compose_proxy(parent, source)
    generate.assert_not_called()


def test_subset_mapping_is_not_a_real_vmrt(source):
    parent = proxy_link(source)
    rt, _ = historical_components(source)
    child = make_subset(source)
    models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=child.pk,
        monitor_table_id=TABLE,
        bkbase_table_id="2_conditional_sink",
    )
    assert utils.get_federal_vm_table_id("system", "bkmonitor", TABLE) == rt.bkbase_table_id
    compose_proxy(parent, source)


def test_proxy_recovers_missing_rt_from_owned_binding(source, mocker):
    parent = proxy_link(source)
    rt, binding = historical_components(source)
    compose_proxy(parent, source)
    rt.delete()
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    compose_proxy(parent, source)
    restored = models.ResultTableConfig.objects.get(data_link_name=parent.pk)
    assert restored.name == "historical_rt"
    assert restored.bkbase_table_id == "42_historical_rt"
    assert models.VMStorageBindingConfig.objects.get(pk=binding.pk).name == "historical_binding"
    generate.assert_not_called()


def test_proxy_recovers_saved_binding_reference(source, mocker):
    parent = proxy_link(source)
    rt, _ = historical_components(source)
    compose_proxy(parent, source)
    models.VMStorageBindingConfig.objects.all().delete()
    models.DataBusConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="old_bus",
        data_link_name=parent.pk,
        bk_biz_id=2,
        data_id_name="saved_source",
        bk_data_id=source.pk,
        sink_names=["VmStorageBinding:historical_binding"],
    )
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    assert compose_proxy(parent, source)[1]["metadata"]["name"] == "historical_binding"
    generate.assert_not_called()


def test_proxy_remote_failure_preserves_allocated_names(source, mocker):
    remote = mocker.patch.object(models.DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("offline"))
    kwargs = dict(
        bk_biz_id=2,
        data_source=source,
        monitor_table_id=TABLE,
        storage_cluster_name=VM,
        data_link_strategy=models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES,
    )
    with pytest.raises(RuntimeError, match="offline"):
        create_bkbase_data_link(**kwargs)
    parent = models.DataLink.objects.get(bk_data_id=source.pk)
    rt = models.ResultTableConfig.objects.get(data_link_name=parent.pk)
    assert parent.pk.startswith("bkm_fp_970001_")
    assert rt.name.startswith("bkm_fp_970001_") and rt.name != parent.pk
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    remote.side_effect = None
    create_bkbase_data_link(**kwargs)
    assert models.DataLink.objects.count() == models.ResultTableConfig.objects.count() == 1
    assert models.AccessVMRecord.objects.get(result_table_id=TABLE).vm_result_table_id.endswith(rt.name)
    generate.assert_not_called()


def test_proxy_full_apply_preserves_legacy_full_vmrt(source):
    rt, binding = historical_components(source)
    create_bkbase_data_link(
        bk_biz_id=2,
        data_source=source,
        monitor_table_id=TABLE,
        storage_cluster_name=VM,
        data_link_strategy=models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES,
    )
    assert models.AccessVMRecord.objects.get(result_table_id=TABLE).vm_result_table_id == rt.bkbase_table_id
    assert models.BkBaseResultTable.objects.get(monitor_table_id=TABLE).bkbase_table_id == rt.bkbase_table_id
    assert models.VMStorageBindingConfig.objects.get(pk=binding.pk).data_link_name


def test_subset_retry_preserves_source_and_names(source, mocker, settings):
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
    historical_components(source)
    child = make_subset(source)
    first = compose_subset(child, source)
    bus = models.DataBusConfig.objects.get(data_link_name=child.pk)
    sink = models.ConditionalSinkConfig.objects.get(data_link_name=child.pk)
    assert sink.name.startswith("bkm_fs_970001_")
    bus.data_id_name = "actual_v3_source"
    bus.save(update_fields=["data_id_name"])
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    second = compose_subset(child, source)
    assert first[0] == second[0]
    assert second[1]["spec"]["sources"][0]["name"] == "actual_v3_source"
    sink.delete()
    assert compose_subset(child, source) == second
    generate.assert_not_called()


def test_v3_source_never_falls_back_to_monitor_data_id(source, mocker):
    historical_components(source)
    models.AccessVMRecord.objects.update(bk_base_data_id=123456)
    api = mocker.patch.object(utils, "get_bkbase_raw_data_name_for_v3_datalink", return_value="actual_v3_name")
    assert utils.get_bkbase_raw_data_id_name(source, TABLE) == "actual_v3_name"
    api.assert_called_once_with("system", 123456)
    api.return_value = ""
    with pytest.raises(models.DataIdConfig.DoesNotExist):
        utils.get_bkbase_raw_data_id_name(source, TABLE)


@pytest.mark.django_db(databases="__all__", transaction=True)
@pytest.mark.parametrize("legacy", [True, False])
def test_concurrent_proxy_compose_creates_or_adopts_once(source, legacy):
    parent = proxy_link(source)
    if legacy:
        historical_components(source)
    barrier = Barrier(2)

    def apply():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            link = models.DataLink.objects.get(pk=parent.pk)
            ds = models.DataSource.objects.get(pk=source.pk)
            result = compose_proxy(link, ds)
            return [config["metadata"]["name"] for config in result]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: apply(), range(2)))
    assert results[0] == results[1]
    assert models.ResultTableConfig.objects.count() == models.VMStorageBindingConfig.objects.count() == 1


def test_standard_proxy_round_trip_preserves_components(source, mocker):
    delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")
    kwargs = dict(bk_biz_id=2, data_source=source, monitor_table_id=TABLE, storage_cluster_name=VM)
    create_bkbase_data_link(**kwargs)
    link = models.DataLink.objects.get(bk_data_id=source.pk)
    rt = models.ResultTableConfig.objects.get(data_link_name=link.pk)
    binding = models.VMStorageBindingConfig.objects.get(data_link_name=link.pk)
    for strategy in [models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES, models.DataLink.BK_STANDARD_V2_TIME_SERIES]:
        create_bkbase_data_link(**kwargs, data_link_strategy=strategy)
        assert models.DataLink.objects.get(bk_data_id=source.pk).pk == link.pk
        assert models.ResultTableConfig.objects.get(data_link_name=link.pk).pk == rt.pk
        assert models.VMStorageBindingConfig.objects.get(data_link_name=link.pk).pk == binding.pk
    assert len(delete.call_args_list) == 1
    assert delete.call_args.kwargs["kind"] == "databuses"


def test_repaired_proxy_to_standard_keeps_full_vmrt(source):
    historical_components(source)
    kwargs = dict(bk_biz_id=2, data_source=source, monitor_table_id=TABLE, storage_cluster_name=VM)
    create_bkbase_data_link(**kwargs, data_link_strategy=models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES)
    create_bkbase_data_link(**kwargs, data_link_strategy=models.DataLink.BK_STANDARD_V2_TIME_SERIES)
    assert models.AccessVMRecord.objects.get(result_table_id=TABLE).vm_result_table_id == "42_historical_rt"
    payload = models.DataLink.apply_data_link_with_retry.call_args.args[0]
    assert next(config for config in payload if config["kind"] == "ResultTable")["spec"]["bizId"] == 42


def test_subset_service_retry_and_delete_reuse_persisted_identity(source, mocker):
    from types import SimpleNamespace
    from metadata.service import federation_data_link as service

    historical_components(source)
    models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id="federal.child",
        table_name_zh="test",
        is_custom_table=True,
        bk_biz_id=2,
        creator="system",
    )
    context = service.FederationMetricContext(
        cluster=SimpleNamespace(bk_biz_id=2),
        data_source=source,
        table_id="federal.child",
        storage_cluster_name=VM,
    )
    mocker.patch.object(service, "_get_metric_context", return_value=context)
    mocker.patch.object(
        service,
        "_build_federation_routes",
        return_value=[dict(fed_cluster_id="BCS-K8S-PROXY", namespaces=["ns1"], target_metric_table_id=TABLE)],
    )
    remote = mocker.patch.object(models.DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("offline"))
    with pytest.raises(RuntimeError, match="offline"):
        service.ensure_federal_subset_data_link("system", "child")
    link = models.DataLink.objects.get(data_link_strategy=models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    sink = models.ConditionalSinkConfig.objects.get(data_link_name=link.pk)
    assert link.pk.startswith("bkm_fs_970001_") and sink.name != link.pk
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    remote.side_effect = None
    service.ensure_federal_subset_data_link("system", "child")
    assert models.ConditionalSinkConfig.objects.get(data_link_name=link.pk).pk == sink.pk
    mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")
    service.delete_federal_subset_data_link("system", "child")
    service.delete_federal_subset_data_link("system", "child")
    assert not models.DataLink.objects.filter(pk=link.pk).exists()
    assert models.VMStorageBindingConfig.objects.filter(name="historical_binding").exists()
    generate.assert_not_called()


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_concurrent_proxy_identity_allocation(source):
    barrier = Barrier(2)

    def create():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return proxy_link(models.DataSource.objects.get(pk=source.pk)).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        names = list(pool.map(lambda _: create(), range(2)))
    assert names[0] == names[1]
    assert models.DataLink.objects.count() == models.BkBaseResultTable.objects.count() == 1


def test_subset_rejects_wrong_parent_vm_cluster(source):
    _, binding = historical_components(source)
    binding.vm_cluster_name = "wrong_cluster"
    binding.save(update_fields=["vm_cluster_name"])
    with pytest.raises(ValueError, match="VM binding"):
        compose_subset(make_subset(source), source)


@pytest.mark.parametrize("reuse", [False, True])
def test_complete_federation_relations_do_not_scan_stale_vmrt_history(source, mocker, settings, reuse):
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = (
        {models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES}
        if reuse
        else set()
    )
    parent = proxy_link(source)
    rt, binding = historical_components(source)
    compose_proxy(parent, source)
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=TABLE,
        bk_base_data_id=source.pk,
        vm_result_table_id="2_obsolete_vmrt",
        vm_cluster_id=1,
    )
    fallback = mocker.patch.object(
        utils, "get_federal_vm_table_id", side_effect=AssertionError("unnecessary historical lookup")
    )
    assert compose_proxy(parent, source)[0]["metadata"]["name"] == rt.name
    configs = compose_subset(make_subset(source), source)
    assert configs[0]["spec"]["conditions"][0]["sinks"][0]["name"] == binding.name
    fallback.assert_not_called()


@pytest.mark.parametrize("data_type", ["metric", "log", "graph"])
def test_result_table_preserves_legacy_business_label(source, data_type):
    rt = models.ResultTableConfig(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="existing_rt",
        bkbase_table_id="42_existing_rt",
        bk_biz_id=2,
        data_type=data_type,
    )
    config = rt.compose_config()
    assert config["metadata"]["labels"]["bk_biz_id"] == "42"
    assert config["spec"]["bizId"] == 42
