"""Random names are allocated once; stored identities drive retries and references."""

import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import IntegrityError, close_old_connections

from metadata import models
from metadata.models.data_link import utils
from metadata.models.data_link.component_reuse import ComponentReuseError
from metadata.models.vm.utils import _ensure_named_data_link

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def source():
    ds = models.DataSource.objects.create(
        bk_tenant_id="system",
        bk_data_id=960001,
        data_name="random-name-source",
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=False,
        etl_config="bk_standard_v2_time_series",
    )
    models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id="random_name.metric",
        table_name_zh="test",
        is_custom_table=True,
        bk_biz_id=2,
        creator="system",
    )
    return ds


def register(source, namespace="bkmonitor", name="existing_source"):
    return models.DataIdConfig.objects.create(
        bk_tenant_id=source.bk_tenant_id,
        namespace=namespace,
        name=name,
        bk_data_id=source.bk_data_id,
        bk_biz_id=2,
    )


def make_link(source):
    register(source)
    return _ensure_named_data_link(
        source, "random_name.metric", models.DataLink.BK_STANDARD_V2_TIME_SERIES, "bkmonitor"
    )[0]


@pytest.fixture(autouse=True)
def mock_tenant_default_biz_id(mocker):
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)


def compose(link, source, table_id="random_name.metric"):
    link.compose_configs(bk_biz_id=2, data_source=source, table_id=table_id, storage_cluster_name="name-test-vm")
    rt = models.ResultTableConfig.objects.get(data_link_name=link.pk)
    binding = models.VMStorageBindingConfig.objects.get(data_link_name=link.pk)
    databus = models.DataBusConfig.objects.get(data_link_name=link.pk)
    return rt.name, binding.name, databus.name, databus.data_id_name


@pytest.mark.parametrize("scene", sorted(utils.RANDOM_NAME_SCENES))
def test_random_name_format_and_length(scene):
    name = utils.generate_bkdata_resource_name(scene, 2**63 - 1)
    assert len(name) <= 40
    assert re.fullmatch(rf"bkm_{scene}_{2**63 - 1}_[a-z0-9]{{12}}", name)
    assert name != utils.generate_bkdata_resource_name(scene, 2**63 - 1)


@pytest.mark.parametrize(
    "scene,source_id", [("bad", 1), ("ts", 0), ("ts", -1), ("ts", True), ("ts", "1"), ("ts", 2**63)]
)
def test_reject_invalid_name_sources(scene, source_id):
    with pytest.raises(ValueError):
        utils.generate_bkdata_resource_name(scene, source_id)


def test_register_retry_reuses_name_after_remote_failure(source, mocker):
    mocker.patch.object(models.DataIdConfig, "compose_predefined_config", return_value={})
    mocker.patch.object(models.DataIdConfig, "compose_data_source_config", return_value={})
    remote = mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link", side_effect=RuntimeError("offline"))
    with pytest.raises(RuntimeError, match="offline"):
        source.register_to_bkbase(2)
    registered = models.DataIdConfig.objects.get(bk_data_id=source.bk_data_id)
    assert registered.name.startswith(f"bkm_did_{source.bk_data_id}_")
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    remote.side_effect = None
    source.register_to_bkbase(2)
    assert models.DataIdConfig.objects.filter(bk_data_id=source.bk_data_id).count() == 1
    assert models.DataIdConfig.objects.get(pk=registered.pk).name == registered.name
    generator.assert_not_called()


def test_explicit_registration_name_stays_fixed(source, mocker):
    mocker.patch.object(models.DataIdConfig, "compose_predefined_config", return_value={})
    mocker.patch.object(models.DataIdConfig, "compose_data_source_config", return_value={})
    mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    source.register_to_bkbase(2, bkbase_data_name="fixed_legacy_name")
    assert models.DataIdConfig.objects.get(bk_data_id=source.bk_data_id).name == "fixed_legacy_name"


def test_link_and_components_reuse_with_switch_off(source, mocker, settings):
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
    link = make_link(source)
    assert link.data_link_name.startswith("bkm_ts_960001_")
    assert link.data_link_name != "existing_source"
    names = compose(link, source)
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    again, _, _ = _ensure_named_data_link(source, "random_name.metric", link.data_link_strategy, "bkmonitor")
    assert again.pk == link.pk
    assert compose(again, source) == names
    generator.assert_not_called()


def test_missing_mapping_recovers_link_by_source_and_table(source, mocker):
    link = make_link(source)
    models.BkBaseResultTable.objects.filter(data_link_name=link.pk).delete()
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    restored, _, _ = _ensure_named_data_link(source, "random_name.metric", link.data_link_strategy, "bkmonitor")
    assert restored.pk == link.pk
    assert models.BkBaseResultTable.objects.get(data_link_name=link.pk).monitor_table_id == "random_name.metric"
    generator.assert_not_called()


def test_missing_components_restore_saved_references(source, mocker):
    link = make_link(source)
    names = compose(link, source)
    rt_name, binding_name, _, _ = names
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    models.ResultTableConfig.objects.filter(data_link_name=link.pk).delete()
    assert compose(link, source) == names
    assert models.ResultTableConfig.objects.get(data_link_name=link.pk).name == rt_name
    models.VMStorageBindingConfig.objects.filter(data_link_name=link.pk).delete()
    assert compose(link, source) == names
    assert models.VMStorageBindingConfig.objects.get(data_link_name=link.pk).name == binding_name
    generator.assert_not_called()


def test_ambiguous_components_never_allocate_replacements(source, mocker):
    link = make_link(source)
    compose(link, source)
    models.ResultTableConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        data_link_name=link.pk,
        bk_biz_id=2,
        name="another_rt",
        table_id="random_name.metric",
    )
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name")
    with pytest.raises(ComponentReuseError):
        compose(link, source)
    generator.assert_not_called()


def test_name_collision_retries_without_overwriting_existing(source, mocker):
    existing = register(source, name="occupied")
    mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=["occupied", "available"])
    created = utils.create_resource_with_random_name(
        models.DataIdConfig,
        "did",
        source.bk_data_id,
        bk_tenant_id="system",
        namespace="bkmonitor",
        bk_biz_id=2,
        bk_data_id=960002,
    )
    assert created.name == "available"
    existing.refresh_from_db()
    assert existing.bk_data_id == source.bk_data_id


def test_non_name_database_error_is_not_retried(source, mocker):
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", return_value="available")
    mocker.patch("django.db.models.query.QuerySet.create", side_effect=IntegrityError("unrelated constraint"))
    with pytest.raises(IntegrityError, match="unrelated constraint"):
        utils.create_resource_with_random_name(
            models.DataIdConfig,
            "did",
            source.bk_data_id,
            bk_tenant_id="system",
            namespace="bkmonitor",
            bk_biz_id=2,
        )
    generate.assert_called_once()


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_concurrent_first_link_creation_has_one_identity(source):
    register(source)
    barrier = Barrier(2)

    def allocate():
        close_old_connections()
        try:
            ds = models.DataSource.objects.get(pk=source.pk)
            barrier.wait(timeout=10)
            return _ensure_named_data_link(
                ds, "random_name.metric", models.DataLink.BK_STANDARD_V2_TIME_SERIES, "bkmonitor"
            )[0].pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(allocate) for _ in range(2)]
        names = [future.result(timeout=20) for future in futures]
    assert names[0] == names[1]
    assert models.DataLink.objects.filter(bk_data_id=source.bk_data_id).count() == 1


def test_health_check_uses_registered_name_and_reports_missing_mapping(source, mocker):
    from metadata.health_check import get_data_id_status
    from metadata.models.constants import DataIdCreatedFromSystem

    source.created_from = DataIdCreatedFromSystem.BKDATA.value
    source.save(update_fields=["created_from"])
    registered = register(source, name="bkm_did_960001_randomsaved1")
    resource = {"metadata": {"annotations": {"dataId": str(source.bk_data_id)}}, "status": {"phase": "Ok"}}
    remote = mocker.patch("metadata.models.data_link.service.api.bkdata.get_data_link", return_value=resource)
    mocker.patch("metadata.health_check.api.metadata.kafka_tail", return_value=[])
    mocker.patch.object(utils, "compose_bkdata_data_id_name", side_effect=AssertionError("inferred name"))
    mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("generated name"))
    status = get_data_id_status(source.bk_tenant_id, 2, source.bk_data_id, with_detail=True)
    assert status.bkbase_data_id_name == registered.name
    assert status.bkbase_status == "Ok"
    assert status.bkbase_config == resource
    assert remote.call_args.kwargs["name"] == registered.name
    registered.delete()
    remote.reset_mock()
    status = get_data_id_status(source.bk_tenant_id, 2, source.bk_data_id)
    assert status.bkbase_status == "Error"
    assert "DataIdConfig not found" in status.message
    remote.assert_not_called()


def test_same_normalized_table_names_get_distinct_identities(source):
    register(source)
    names = []
    for table_id in ("random-a.metric", "random_a.metric"):
        models.ResultTable.objects.create(
            bk_tenant_id="system",
            table_id=table_id,
            table_name_zh="test",
            is_custom_table=True,
            bk_biz_id=2,
            creator="system",
        )
        link = _ensure_named_data_link(source, table_id, models.DataLink.BK_STANDARD_V2_TIME_SERIES, "bkmonitor")[0]
        output_names = compose(link, source, table_id)
        names.append((link.pk, output_names[0]))
    assert utils.compose_bkdata_table_id("random-a.metric") == utils.compose_bkdata_table_id("random_a.metric")
    assert names[0][0] != names[1][0]
    assert names[0][1] != names[1][1]


def test_registered_identity_is_tenant_and_namespace_scoped(source):
    register(source, namespace="bklog", name="log_identity")
    register(source, namespace="bkmonitor", name="metric_identity")
    models.DataIdConfig.objects.create(
        bk_tenant_id="other",
        namespace="bkmonitor",
        name="other_tenant",
        bk_data_id=source.bk_data_id,
        bk_biz_id=2,
    )
    assert utils.get_registered_bkdata_data_id_name(source, "bklog") == "log_identity"
    assert utils.get_registered_bkdata_data_id_name(source, "bkmonitor") == "metric_identity"


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_concurrent_registration_allocates_one_name(source, mocker):
    mocker.patch.object(models.DataIdConfig, "compose_predefined_config", return_value={})
    mocker.patch.object(models.DataIdConfig, "compose_data_source_config", return_value={})
    mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link")
    barrier = Barrier(2)

    def allocate():
        close_old_connections()
        try:
            ds = models.DataSource.objects.get(pk=source.pk)
            barrier.wait(timeout=10)
            ds.register_to_bkbase(2)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(allocate) for _ in range(2)]
        for future in futures:
            future.result(timeout=20)
    assert models.DataIdConfig.objects.filter(bk_data_id=source.bk_data_id, namespace="bkmonitor").count() == 1


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_concurrent_component_creation_allocates_one_chain(source):
    link = make_link(source)
    barrier = Barrier(2)

    def allocate():
        close_old_connections()
        try:
            ds = models.DataSource.objects.get(pk=source.pk)
            current_link = models.DataLink.objects.get(pk=link.pk)
            barrier.wait(timeout=10)
            return compose(current_link, ds)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(allocate) for _ in range(2)]
        names = [future.result(timeout=20) for future in futures]
    assert names[0] == names[1]
    for model in (models.ResultTableConfig, models.VMStorageBindingConfig, models.DataBusConfig):
        assert model.objects.filter(data_link_name=link.pk).count() == 1


def prepare_graph_rebuild(source):
    register(source)
    scope = dict(bk_tenant_id="system", namespace="bkmonitor", bk_biz_id=2)
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=source.bk_data_id,
        table_id="random_name.metric",
    )
    models.ResultTableOption.create_option(
        bk_tenant_id="system",
        table_id="random_name.metric",
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value={"write_targets": ["vm"]},
        creator="test",
    )
    models.ResultTableConfig.objects.create(
        name="saved_graph_vm",
        table_id="random_name.metric",
        bkbase_table_id="2_saved_graph_vm",
        **scope,
    )
    models.VMStorageBindingConfig.objects.create(
        name="saved_graph_binding",
        table_id="random_name.metric",
        bkbase_result_table_name="saved_graph_vm",
        vm_cluster_name="unused",
        **scope,
    )
    return models.DataBusConfig.objects.create(
        name="saved_graph_bus",
        data_id_name="existing_source",
        bk_data_id=source.bk_data_id,
        sink_names=["VmStorageBinding:saved_graph_binding"],
        **scope,
    )


def test_graph_rebuild_preview_is_read_only_and_repeated_execution_skips(source, mocker):
    from metadata.models.data_link.relation import rebuild_databus_relation

    databus = prepare_graph_rebuild(source)
    preview = rebuild_databus_relation(databus, dry_run=True)
    assert preview["data_link_name"].startswith(f"rebuilt__bkm_gr_{databus.pk}_")
    assert not models.DataLink.objects.filter(bk_data_id=source.bk_data_id).exists()
    databus.refresh_from_db()
    assert databus.data_link_name == ""
    link = rebuild_databus_relation(databus, dry_run=False)
    assert link.pk.startswith(f"rebuilt__bkm_gr_{databus.pk}_")
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    assert rebuild_databus_relation(databus, dry_run=False) is None
    assert models.DataLink.objects.filter(bk_data_id=source.bk_data_id).count() == 1
    generator.assert_not_called()


@pytest.mark.django_db(databases="__all__", transaction=True)
def test_graph_rebuild_concurrent_execution_reuses_link(source):
    from metadata.models.data_link.relation import rebuild_databus_relation

    databus = prepare_graph_rebuild(source)
    barrier = Barrier(2)

    def rebuild():
        close_old_connections()
        try:
            bus = models.DataBusConfig.objects.get(pk=databus.pk)
            barrier.wait(timeout=10)
            result = rebuild_databus_relation(bus, dry_run=False)
            return result.pk if result else None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(rebuild) for _ in range(2)]
        names = [future.result(timeout=20) for future in futures]
    link = models.DataLink.objects.get(bk_data_id=source.bk_data_id)
    assert {name for name in names if name} == {link.pk}
    databus.refresh_from_db()
    assert databus.data_link_name == link.pk
    assert models.VMStorageBindingConfig.objects.get(name="saved_graph_binding").data_link_name == link.pk


def test_graph_rebuild_reuses_link_with_missing_component_relations(source, mocker):
    from metadata.models.data_link.relation import rebuild_databus_relation

    databus = prepare_graph_rebuild(source)
    existing_link = models.DataLink.objects.create(
        bk_tenant_id=source.bk_tenant_id,
        namespace=databus.namespace,
        data_link_name="saved_graph_link",
        bk_data_id=source.bk_data_id,
        table_ids=["random_name.metric"],
        data_link_strategy=models.DataLink.GRAPH_RELATION_TIME_SERIES,
    )
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))

    link = rebuild_databus_relation(databus, dry_run=False)

    assert link.pk == existing_link.pk
    assert models.DataLink.objects.filter(bk_data_id=source.bk_data_id).count() == 1
    for model in (models.DataBusConfig, models.VMStorageBindingConfig, models.ResultTableConfig):
        assert model.objects.get(namespace=databus.namespace).data_link_name == existing_link.pk
    assert (
        models.BkBaseResultTable.objects.get(monitor_table_id="random_name.metric").data_link_name == existing_link.pk
    )
    generator.assert_not_called()


def test_partial_vm_mapping_uses_persisted_rt_instead_of_generating_route(source, mocker):
    from metadata.models.vm.utils import create_bkbase_data_link

    register(source)
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=996001,
        cluster_name="name-test-vm",
        cluster_type="victoria_metrics",
        domain_name="localhost",
        port=80,
        is_default_cluster=False,
    )
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    mocker.patch.object(models.DataLink, "get_existing_component_config", return_value=None)
    mocker.patch.object(models.DataLink, "apply_data_link_with_retry", return_value={})
    # sync_metadata leaves the initial mapping without a VMRT; the caller must use the real component.
    mocker.patch.object(models.DataLink, "sync_metadata")
    create_bkbase_data_link(
        bk_biz_id=2,
        data_source=source,
        monitor_table_id="random_name.metric",
        storage_cluster_name="name-test-vm",
    )
    output = models.ResultTableConfig.objects.get(table_id="random_name.metric")
    record = models.AccessVMRecord.objects.get(result_table_id="random_name.metric")
    assert record.vm_result_table_id == f"2_{output.name}"


def test_multiple_orphan_relations_do_not_create_a_new_identity(source, mocker):
    register(source)
    for name in ("orphan_one", "orphan_two"):
        models.BkBaseResultTable.objects.create(
            bk_tenant_id="system",
            monitor_table_id="random_name.metric",
            data_link_name=name,
            storage_type=models.ClusterInfo.TYPE_VM,
        )
    generator = mocker.patch.object(utils, "generate_bkdata_resource_name")
    with pytest.raises(ValueError, match="ambiguous orphan"):
        _ensure_named_data_link(source, "random_name.metric", models.DataLink.BK_STANDARD_V2_TIME_SERIES, "bkmonitor")
    generator.assert_not_called()
    assert not models.DataLink.objects.filter(bk_data_id=source.bk_data_id).exists()


def test_empty_databus_source_is_repaired_from_registered_identity(source, mocker):
    link = make_link(source)
    names = compose(link, source)
    models.DataBusConfig.objects.filter(data_link_name=link.pk).update(data_id_name="")
    mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=AssertionError("regenerated"))
    assert compose(link, source) == names


@pytest.mark.parametrize(
    "strategy",
    [
        models.DataLink.BK_STANDARD_V2_TIME_SERIES,
        models.DataLink.BK_STANDARD_TIME_SERIES,
        models.DataLink.BK_EXPORTER_TIME_SERIES,
    ],
)
def test_compose_creates_complete_components_once(source, strategy):
    from django.db.models.signals import post_save

    link = make_link(source)
    link.data_link_strategy = strategy
    link.save(update_fields=["data_link_strategy"])
    writes = []

    def capture(sender, instance, created, **kwargs):
        writes.append((sender, created))
        if sender is models.VMStorageBindingConfig:
            assert instance.vm_cluster_name == "name-test-vm"
            assert instance.bkbase_result_table_name
        elif sender is models.DataBusConfig:
            assert instance.data_id_name == "existing_source"
            assert instance.sink_names

    components = (models.ResultTableConfig, models.VMStorageBindingConfig, models.DataBusConfig)
    for model in components:
        post_save.connect(capture, sender=model)
    try:
        compose(link, source)
    finally:
        for model in components:
            post_save.disconnect(capture, sender=model)
    assert writes == [(model, True) for model in components]


def test_direct_compose_failure_rolls_back_component_creation(source, mocker):
    link = make_link(source)
    mocker.patch.object(models.VMStorageBindingConfig, "compose_config", side_effect=RuntimeError("render failed"))
    with pytest.raises(RuntimeError, match="render failed"):
        compose(link, source)
    for model in (models.ResultTableConfig, models.VMStorageBindingConfig, models.DataBusConfig):
        assert not model.objects.filter(data_link_name=link.pk).exists()


def test_first_compose_avoids_names_occupied_by_other_components(source, mocker):
    link = make_link(source)
    existing = models.VMStorageBindingConfig.objects.create(
        bk_tenant_id=source.bk_tenant_id,
        namespace=link.namespace,
        name="occupied_binding",
        data_link_name="unrelated_link",
        bk_biz_id=2,
        vm_cluster_name="other-vm",
    )
    generate = mocker.patch.object(utils, "generate_bkdata_resource_name", side_effect=["occupied_binding", "new_name"])
    rt_name, binding_name, databus_name, _ = compose(link, source)
    assert (rt_name, binding_name, databus_name) == ("new_name", "new_name", "new_name")
    assert generate.call_count == 2
    existing.refresh_from_db()
    assert existing.data_link_name == "unrelated_link"
    assert existing.vm_cluster_name == "other-vm"
