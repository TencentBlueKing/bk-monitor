"""升级散件的副作用、重入与批量路由契约；外部 BKBase/Redis/采集接口均隔离。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.data_link_configs import DataIdConfig
from metadata.service.upgrade_v4 import (
    builtin,
    common,
    containers,
    events,
    metrics,
    plugins,
    prerequisites,
    routes,
    uptimecheck,
)
from metadata.task import datalink


@pytest.fixture(autouse=True)
def single_tenant(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.ENABLE_V2_VM_DATA_LINK = True


@pytest.mark.parametrize(
    "mode,rt,labels,spaces",
    [
        ("none", 0, 0, 0),
        ("rt", 1, 0, 0),
        ("data_label", 0, 1, 0),
        ("rt_and_data_label", 1, 1, 0),
        ("all", 1, 1, 2),
    ],
)
def test_route_modes_deduplicate_and_publish(mocker, mode, rt, labels, spaces):
    router = mocker.patch.object(routes, "UpgradeRouter").return_value
    routes.refresh_routes(
        table_ids=["a", "a", "b"], spaces=[("bkcc", "1"), ("bkcc", "1"), ("bkcc", "2")], mode=mode, is_publish=False
    )
    assert router.push_table_id_detail.call_count == rt
    assert router.push_data_label_table_ids.call_count == labels
    assert router.push_space_table_ids.call_count == spaces
    for call in router.mock_calls:
        assert call.kwargs["is_publish"] is False
        if "table_id_list" in call.kwargs:
            assert call.kwargs["table_id_list"] == ["a", "b"]


@pytest.mark.parametrize("mode", sorted(routes.ROUTE_MODES))
def test_empty_selection_never_refreshes_whole_tenant(mocker, mode):
    router = mocker.patch.object(routes, "UpgradeRouter").return_value
    routes.refresh_routes(mode=mode)
    assert router.mock_calls == []


def test_batch_continues_failed_item_and_refreshes_spaces_once(mocker):
    router = mocker.patch.object(routes, "UpgradeRouter").return_value
    attempts = []

    def migrate(item):
        attempts.append(item)
        if item == 2:
            raise RuntimeError("remote apply failed")
        return {"table_ids": [f"rt{item}"], "spaces": [("bkcc", "1")]}

    result = common.run_batch([1, 2, 3], migrate, route_refresh="all")
    assert attempts == [1, 2, 3]
    assert [r["success"] for r in result["results"]] == [True, False, True]
    router.push_table_id_detail.assert_called_once_with(
        bk_tenant_id="system", table_id_list=["rt1", "rt3"], is_publish=True
    )
    router.push_space_table_ids.assert_called_once_with("bkcc", "1", is_publish=True)


def test_bad_route_mode_fails_before_mutation():
    migrate = Mock()
    with pytest.raises(ValueError):
        common.run_batch([1], migrate, route_refresh="typo")
    migrate.assert_not_called()


def test_multitenant_fails_before_mutation(settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    migrate = Mock()
    with pytest.raises(ValueError):
        common.run_batch([1], migrate)
    migrate.assert_not_called()


def test_registration_retry_preserves_source_owner(mocker, django_db_blocker):
    source = models.DataSource(bk_tenant_id="system", bk_data_id=11, data_name="test", created_from="bkgse")
    source.save = Mock()
    mocker.patch.object(models.DataSource.objects, "select_for_update").return_value.get.return_value = source
    config = Mock(name="data_id_config")
    mocker.patch.object(DataIdConfig.objects, "update_or_create", return_value=(config, False))
    remote = mocker.patch(
        "metadata.models.data_source.api.bkdata.apply_data_link", side_effect=[RuntimeError("apply failed"), None, None]
    )
    mocker.patch("metadata.models.data_link.service.apply_data_source_config")
    with django_db_blocker.unblock():
        with pytest.raises(RuntimeError):
            source.register_to_bkbase(2, bkbase_data_name="stable", update_created_from=False)
        source.register_to_bkbase(2, bkbase_data_name="stable", update_created_from=False)
    assert source.created_from == "bkgse"
    source.save.assert_not_called()
    assert remote.call_count == 2
    with django_db_blocker.unblock():
        source.register_to_bkbase(2, bkbase_data_name="stable")
    assert source.created_from == DataIdCreatedFromSystem.BKDATA.value
    source.save.assert_called_once()


def test_finalize_retries_cleanup_for_already_bkdata(mocker):
    source = Mock(created_from="bkdata")
    mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    source.delete_consul_config.side_effect = [RuntimeError("consul unavailable"), None]
    with pytest.raises(RuntimeError):
        common.finalize_transfer([11])
    assert common.finalize_transfer([11, 11]) == [11]
    assert source.delete_consul_config.call_count == 2


def test_cluster_registration_reads_both_namespaces_and_caches_inventory(mocker):
    clusters = [
        models.ClusterInfo(cluster_id=i, cluster_name=f"k{i}", cluster_type="kafka", bk_tenant_id="system")
        for i in (1, 2)
    ]
    mocker.patch.object(models.ClusterInfo.objects, "filter").return_value.order_by.return_value = clusters
    remote = mocker.patch.object(
        prerequisites.api.bkdata,
        "list_data_link",
        return_value=[{"metadata": {"name": "k1"}, "status": {"phase": "Ok"}}],
    )
    result = prerequisites.check_cluster_registration()
    assert remote.call_count == 2  # 两个 namespace，各查一次，不按集群重复查询。
    assert set(result[0]["namespaces"]) == {"bkmonitor", "bklog"}
    assert all(v["registered"] for v in result[0]["namespaces"].values())
    assert not any(v["registered"] for v in result[1]["namespaces"].values())


def test_register_clusters_does_not_register_gse_or_choose_default(mocker):
    cluster = Mock()
    mocker.patch.object(models.ClusterInfo.objects, "get", return_value=cluster)
    sync = mocker.patch.object(prerequisites.ClusterConfig, "sync_cluster_config")
    gse = mocker.patch.object(prerequisites.KafkaGseSyncer, "register_to_gse")
    assert prerequisites.register_clusters([1, 1], namespaces=["bklog"]) == [1]
    sync.assert_called_once_with(cluster, sync_namespaces=["bklog"])
    gse.assert_not_called()
    cluster.save.assert_not_called()


def metric_context(mocker):
    mocker.patch.object(models.ResultTableOption.objects, "filter").return_value.exists.return_value = False
    source = Mock(bk_tenant_id="system", bk_data_id=11, is_enable=True, etl_config="bk_standard_v2_time_series")
    mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    mocker.patch.object(models.DataSourceResultTable.objects, "filter").return_value.values_list.return_value = ["rt"]
    table = Mock(table_id="rt")
    table.get_target_bk_biz_id.return_value = 2
    mocker.patch.object(models.ResultTable.objects, "filter", return_value=[table])
    mocker.patch.object(models.ClusterInfo.objects, "get", return_value=Mock(cluster_name="vm"))
    mocker.patch.object(metrics, "compose_transfer_consumer_group", return_value="transfer-topic")
    mocker.patch.object(metrics, "changed", return_value={"data_id": 11, "table_ids": ["rt"], "spaces": []})
    return source


def test_metric_retry_does_not_delete_transfer_or_refresh_routes(mocker):
    source = metric_context(mocker)
    apply = mocker.patch.object(metrics, "create_bkbase_data_link", side_effect=[RuntimeError("remote"), None])
    router = mocker.patch.object(routes, "UpgradeRouter")
    with pytest.raises(RuntimeError):
        metrics.migrate_metric(11, vm_cluster_name="vm")
    metrics.migrate_metric(11, vm_cluster_name="vm")
    assert source.register_to_bkbase.call_count == 2
    assert source.register_to_bkbase.call_args.kwargs["update_created_from"] is False
    assert apply.call_args.kwargs["consumer_group"] == "transfer-topic"
    source.delete_consul_config.assert_not_called()
    source.save.assert_not_called()
    router.assert_not_called()


def test_disabled_metric_has_no_writes(mocker):
    source = metric_context(mocker)
    source.is_enable = False
    apply = mocker.patch.object(metrics, "create_bkbase_data_link")
    assert metrics.migrate_metric(11, vm_cluster_name="vm")["skipped"]
    source.register_to_bkbase.assert_not_called()
    apply.assert_not_called()


def test_event_preparation_turns_false_option_on_without_finalizing(mocker):
    source = Mock(bk_tenant_id="system", bk_data_id=11, is_enable=True, etl_config="bk_standard_v2_event")
    mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    mocker.patch.object(models.EventGroup.objects, "filter", return_value=[Mock(table_id="event")])
    mocker.patch.object(
        models.ResultTable.objects, "get", return_value=Mock(table_id="event", is_enable=True, is_deleted=False)
    )
    option = mocker.patch.object(events, "set_option")
    apply = mocker.patch.object(events, "apply_event_group_datalink")
    mocker.patch.object(events, "changed", return_value={})
    events.migrate_event(11)
    option.assert_called_once_with("event", "enable_v4_event_group_data_link", True, bk_tenant_id="system")
    apply.assert_called_once_with("system", "event", finalize=False, refresh_route=False)
    source.delete_consul_config.assert_not_called()


def test_plugin_partial_retry_uses_preparation_not_command_execution(mocker):
    context = Mock()
    context.table.pk = None
    context.table.get_target_bk_biz_id.return_value = 2
    context.default_exists = False
    context.source.is_enable = True
    context.source.etl_config = "bk_exporter"
    context.collect_metric_info.return_value = ([{"field_name": "m"}], [])
    mocker.patch.object(plugins, "MultiTableCommand", return_value=context)
    assert plugins.prepare_plugin(11, vm_cluster_name="vm") is context
    assert plugins.prepare_plugin(11, vm_cluster_name="vm") is context
    assert context.prepare_default.call_count == 2
    context.precheck.assert_not_called()  # 旧 precheck 会拒绝已有部分组件，不能用于可重入接口。
    context.execute_migration.assert_not_called()
    context.publish_and_finalize.assert_not_called()


def test_uptime_preparation_empty_selection_has_no_side_effect(mocker):
    mocker.patch.object(uptimecheck, "_tasks", return_value=[])
    router = mocker.patch.object(routes, "UpgradeRouter").return_value
    result = uptimecheck.migrate_uptimechecks([], vm_cluster_name="vm", route_refresh="all")
    assert result["results"] == []
    assert router.mock_calls == []


def test_uptime_switch_does_not_start_stopped_tasks_and_can_reenter(mocker):
    task = Mock(pk=1, bk_biz_id=2, protocol="HTTP", status="stoped")
    task.Status.RUNNING = "running"
    mocker.patch.object(uptimecheck, "_tasks", return_value=[task])
    mocker.patch.object(models.DataSource.objects, "get", return_value=Mock(bk_data_id=11))
    mocker.patch.object(models.TimeSeriesGroup.objects, "get")
    mocker.patch("monitor.models.ApplicationConfig.objects.update_or_create")
    mocker.patch(
        "monitor_web.commons.data_access.UptimecheckDataAccessor", return_value=Mock(data_name="uptime", version="v1")
    )
    deploy = mocker.patch("bk_monitor_base.uptime_check.control_task")
    for _ in range(2):
        assert uptimecheck.switch_uptimecheck_tasks([1], deploy=True)[0]["deploy_requested"] is False
    assert task.indepentent_dataid is True
    deploy.assert_not_called()


def test_containers_deduplicate_ids_and_allow_event_only(mocker):
    cluster = SimpleNamespace(
        cluster_id="BCS-1", K8sMetricDataID=11, CustomMetricDataID=11, K8sEventDataID=12, CustomEventDataID=12
    )
    mocker.patch.object(
        models.BCSClusterInfo.objects, "filter"
    ).return_value.exclude.return_value.order_by.return_value = [cluster]
    metric = mocker.patch.object(containers, "migrate_metric")
    event = mocker.patch.object(containers, "migrate_event", return_value={"table_ids": [], "spaces": []})
    containers.migrate_containers(metrics=False, route_refresh="none")
    metric.assert_not_called()
    event.assert_called_once_with(12, bk_tenant_id="system")


def test_host_preparation_keeps_kafka_and_source_owner(mocker, settings):
    source = Mock(is_enable=True, bk_data_id=settings.SNAPSHOT_DATAID, mq_cluster_id=99)
    mocker.patch.object(builtin, "_source", return_value=source)
    mocker.patch.object(models.ClusterInfo.objects, "get", return_value=Mock(cluster_name="vm"))
    link = mocker.patch.object(builtin, "_link").return_value
    mocker.patch.object(builtin, "_vm_record")
    mocker.patch.object(builtin, "changed", return_value={"table_ids": [], "spaces": []})
    mocker.patch.object(builtin, "compose_transfer_consumer_group", return_value="old-group")
    builtin.migrate_host_metrics(vm_cluster_name="vm", route_refresh="none")
    assert source.mq_cluster_id == 99
    assert source.register_to_bkbase.call_args.kwargs["update_created_from"] is False
    assert link.apply_data_link.call_args.kwargs["consumer_group"] == "old-group"
    source.delete_consul_config.assert_not_called()


def test_event_partial_apply_reenters_same_link_without_cleanup(mocker, django_db_blocker):
    rt = Mock(table_id="event", bk_biz_id=2, default_storage=models.ClusterInfo.TYPE_ES)
    source = Mock(bk_tenant_id="system", bk_data_id=11, created_from="bkgse")
    mocker.patch.object(datalink.ResultTable.objects, "get", return_value=rt)
    mocker.patch.object(datalink.DataSourceResultTable.objects, "filter").return_value.last.return_value = Mock(
        bk_data_id=11
    )
    mocker.patch.object(datalink.DataSource.objects, "get", return_value=source)
    mocker.patch.object(
        datalink.ResultTableOption.objects, "filter"
    ).return_value.first.return_value.get_value.return_value = True
    mocker.patch.object(datalink.BkBaseResultTable.objects, "filter").return_value.first.return_value = None
    link = Mock()
    link.apply_data_link.side_effect = [RuntimeError("apply interrupted"), None]
    upsert = mocker.patch.object(datalink.DataLink.objects, "update_or_create", return_value=(link, True))
    mocker.patch.object(datalink, "compose_transfer_consumer_group", return_value="old-group")
    with django_db_blocker.unblock():
        with pytest.raises(RuntimeError):
            datalink.apply_event_group_datalink("system", "event", finalize=False, refresh_route=False)
        datalink.apply_event_group_datalink("system", "event", finalize=False, refresh_route=False)
    assert upsert.call_count == 2
    assert upsert.call_args_list[0] == upsert.call_args_list[1]
    assert source.register_to_bkbase.call_args.kwargs["update_created_from"] is False
    source.delete_consul_config.assert_not_called()
    link.sync_metadata.assert_called_once()


def test_explicit_empty_cluster_ids_do_not_register(mocker):
    get = mocker.patch.object(models.ClusterInfo.objects, "get")
    assert prerequisites.register_clusters([]) == []
    assert prerequisites.register_kafka_to_gse([]) == []
    get.assert_not_called()


def test_space_refresh_can_be_deferred_to_one_explicit_call(mocker):
    router = mocker.patch.object(routes, "UpgradeRouter").return_value
    common.run_batch([1], lambda _: {"table_ids": ["a"], "spaces": [("bkcc", "1")]})
    common.run_batch([2], lambda _: {"table_ids": ["b"], "spaces": [("bkcc", "1")]})
    router.push_space_table_ids.assert_not_called()
    routes.refresh_routes(spaces=[("bkcc", "1"), ("bkcc", "1")], mode="all")
    router.push_space_table_ids.assert_called_once_with("bkcc", "1", is_publish=True)
    assert router.push_table_id_detail.call_count == 2


def test_uptime_partial_prepare_reuses_group_and_never_deploys(mocker, django_db_blocker):
    task = Mock(pk=1, bk_biz_id=2, protocol="HTTP", indepentent_dataid=False)
    mocker.patch.object(uptimecheck, "_tasks", return_value=[task])
    accessor = Mock(data_name="uptimecheck_http_2", data_label="uptimecheck_http,uptimecheck.http")
    mocker.patch("monitor_web.commons.data_access.UptimecheckDataAccessor", return_value=accessor)
    source = Mock(bk_data_id=11)
    mocker.patch.object(models.DataSource.objects, "filter").return_value.first.return_value = source
    mocker.patch.object(models.DataSource.objects, "get", return_value=source)
    group = Mock(table_id="uptime.rt", is_enable=True, is_delete=False)
    mocker.patch.object(models.TimeSeriesGroup.objects, "filter").return_value.first.side_effect = [None, group]
    create = mocker.patch.object(models.TimeSeriesGroup, "_create", return_value=("uptime.rt", group))
    mocker.patch.object(models.TimeSeriesGroup, "_post_process_create")
    mocker.patch.object(models.ResultTable.objects, "filter").return_value.exists.side_effect = [False, True]
    create_rt = mocker.patch.object(models.ResultTable, "create_result_table")
    mocker.patch.object(uptimecheck, "set_source_options")
    mocker.patch.object(
        uptimecheck,
        "migrate_metric",
        side_effect=[RuntimeError("remote interrupted"), {"table_ids": ["uptime.rt"], "spaces": []}],
    )
    deploy = mocker.patch("bk_monitor_base.uptime_check.control_task")
    with django_db_blocker.unblock():
        first = uptimecheck.migrate_uptimechecks([1], vm_cluster_name="vm", route_refresh="none")
        second = uptimecheck.migrate_uptimechecks([1], vm_cluster_name="vm", route_refresh="none")
    assert not first["results"][0]["success"]
    assert second["results"][0]["success"]
    create.assert_called_once()
    create_rt.assert_called_once()
    assert create_rt.call_args.kwargs["is_sync_db"] is False
    accessor.create_data_id.assert_not_called()
    accessor.access.assert_not_called()
    task.save.assert_not_called()
    assert task.indepentent_dataid is False
    deploy.assert_not_called()


def test_explicit_uptime_deploy_allows_retry_after_start_failure(mocker):
    task = Mock(pk=1, bk_biz_id=2, status="start_failed")
    mocker.patch.object(uptimecheck, "_tasks", return_value=[task])
    deploy = mocker.patch("bk_monitor_base.uptime_check.control_task", return_value={"success": True})
    for _ in range(2):
        assert uptimecheck.deploy_uptimecheck_tasks([1])[0]["task_id"] == 1
    assert deploy.call_count == 2
