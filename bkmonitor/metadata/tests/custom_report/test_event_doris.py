"""自定义事件按默认存储接入 Doris，保留 ES 历史绑定。"""

import copy

import pytest

from metadata import models
from metadata.models.data_link.component_reuse import ExistingComponentContext
from metadata.models.data_link.data_link import CUSTOM_EVENT_CLEAN_RULES, DataLink
from metadata.models.data_link.data_link_configs import DataBusConfig, DorisStorageBindingConfig, ESStorageBindingConfig
from metadata.task.datalink import apply_event_group_datalink
from metadata.tests.custom_report import test_event_index_failure
from metadata.tests.task import test_apply_v4_datalink

event_records = test_event_index_failure.event_records
event_group_v4_records = test_apply_v4_datalink.event_group_v4_records

pytestmark = pytest.mark.django_db(databases="__all__")

DORIS_CONFIG = {
    "storage_keys": ["time", "event_name", "target"],
    "json_fields": ["event", "dimensions"],
    "original_json_fields": [],
    "field_config_group": {"bloomfilter": ["event_name"]},
    "tokenizers": {"event.content": "._"},
    "flush_timeout": 10,
}


@pytest.fixture
def doris_cluster():
    return models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_name="event_doris",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="localhost",
        port=9030,
        is_default_cluster=False,
    )


def test_create_event_with_doris(event_records, doris_cluster, mocker):
    mocker.patch.object(models.ResultTable, "apply_datalink")
    create_es = mocker.patch.object(models.ESStorage, "create_table")
    config = {"storage_cluster_id": doris_cluster.cluster_id, "expire_days": 7, "doris_storage_config": DORIS_CONFIG}
    original_config = copy.deepcopy(config)
    group = models.EventGroup.create_event_group(
        bk_tenant_id="system",
        bk_data_id=event_records[1].bk_data_id,
        bk_biz_id=2,
        event_group_name="event_doris",
        label="other_rt",
        operator="admin",
        default_storage="doris",
        default_storage_config=config,
    )
    rt = models.ResultTable.objects.get(table_id=group.table_id, bk_tenant_id="system")
    storage = rt.get_storage("doris")
    assert rt.default_storage == "doris"
    assert storage.doris_storage_config == DORIS_CONFIG
    assert storage.expire_days == 7
    assert config == original_config
    create_es.assert_not_called()
    assert not models.ResultTableOption.objects.filter(
        table_id=group.table_id,
        name=models.ResultTableOption.OPTION_ES_DOCUMENT_ID,
    ).exists()
    assert not models.ResultTableFieldOption.objects.filter(table_id=group.table_id, name__startswith="es_").exists()
    assert models.EventGroup.DEFAULT_STORAGE == "elasticsearch"


def test_doris_storage_config_update_and_legacy_default(doris_cluster):
    storage = models.DorisStorage.create_table("event_config", storage_cluster_id=doris_cluster.cluster_id)
    assert storage.doris_storage_config == {}
    storage.update_storage(doris_storage_config=DORIS_CONFIG)
    storage.refresh_from_db()
    assert storage.doris_storage_config == DORIS_CONFIG
    assert storage.consul_config["storage_config"]["doris_storage_config"] == DORIS_CONFIG
    storage.update_storage(expire_days=9)
    storage.refresh_from_db()
    assert storage.doris_storage_config == DORIS_CONFIG
    storage.update_storage(doris_storage_config={})
    storage.refresh_from_db()
    assert storage.doris_storage_config == {}


@pytest.mark.parametrize("multi_tenant", [False, True])
def test_event_switch_to_doris_preserves_es_binding(
    event_group_v4_records, doris_cluster, mocker, settings, multi_tenant
):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    ctx = event_group_v4_records
    rt = ctx["rt"]
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        name=models.ResultTableOption.OPTION_ES_DOCUMENT_ID,
        value='["time", "event_name"]',
        value_type="list",
        creator="admin",
    )
    mocker.patch("metadata.models.data_link.data_link.generate_result_table_field_list", return_value=[])
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    mocker.patch(
        "metadata.models.data_link.data_link.utils.get_registered_bkdata_data_id_name", return_value="event_data"
    )
    link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="event_link",
        namespace="bklog",
        data_link_strategy=DataLink.BK_STANDARD_V2_EVENT,
        bk_data_id=ctx["ds"].bk_data_id,
        table_ids=[rt.table_id],
    )
    configs = link.compose_custom_event_configs(rt.bk_biz_id, ctx["ds"], rt.table_id)
    assert configs[1]["kind"] == "ElasticSearchBinding"
    es_binding = ESStorageBindingConfig.objects.get(data_link_name=link.data_link_name)
    storage = models.DorisStorage.create_table(
        rt.table_id,
        storage_cluster_id=doris_cluster.cluster_id,
        doris_storage_config=DORIS_CONFIG,
        table_type="duplicate_table",
        expire_days=7,
        create_storage_cluster_record=False,
    )
    rt.default_storage = "doris"
    rt.save(update_fields=["default_storage"])
    for _ in range(2):
        context = ExistingComponentContext.from_datalink(link)
        configs = link.compose_custom_event_configs(rt.bk_biz_id, ctx["ds"], rt.table_id, existing_context=context)
        link._check_leftover_or_raise(context)
        binding = configs[1]
        assert binding["kind"] == "DorisBinding"
        assert binding["spec"]["storage_config"]["table_type"] == storage.table_type
        assert binding["spec"]["storage_config"]["expires"] == "7d"
        for key, value in DORIS_CONFIG.items():
            assert binding["spec"]["storage_config"][key] == value
        databus = DataBusConfig.objects.get(data_link_name=link.data_link_name)
        assert databus.sink_names == ["DorisBinding:event_link"]
        assert len(configs) == 3
        assert ("tenant" in binding["metadata"]) is multi_tenant
    assert ESStorageBindingConfig.objects.filter(pk=es_binding.pk).exists()
    assert DorisStorageBindingConfig.objects.filter(data_link_name=link.data_link_name).count() == 1
    assert link._get_absent_components_to_delete(configs, force_delete=True) == []
    assert configs[2]["spec"]["transforms"][0]["rules"] == CUSTOM_EVENT_CLEAN_RULES

    bkbase_rt = models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=link.data_link_name,
        monitor_table_id=rt.table_id,
        storage_type="elasticsearch",
    )
    mocker.patch.object(link, "_get_databus_option_labels", return_value={})
    mocker.patch.object(link, "_get_databus_prefer_cluster", return_value=None)
    mocker.patch.object(link, "merge_existing_component_configs", side_effect=lambda configs: configs)
    remote_apply = mocker.patch.object(link, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(bk_biz_id=rt.bk_biz_id, data_source=ctx["ds"], table_id=rt.table_id)
    bkbase_rt.refresh_from_db()
    assert bkbase_rt.storage_type == "doris"
    assert remote_apply.call_args.args[0][2]["spec"]["sinks"][0]["kind"] == "DorisBinding"
    assert ESStorageBindingConfig.objects.filter(pk=es_binding.pk).exists()


def test_apply_doris_event_backfills_storage_and_publishes_route(event_group_v4_records, doris_cluster, mocker):
    ctx = event_group_v4_records
    rt = ctx["rt"]
    rt.default_storage = "doris"
    rt.save(update_fields=["default_storage"])
    storage = models.DorisStorage.create_table(rt.table_id, storage_cluster_id=doris_cluster.cluster_id)
    link_name = f"bkmonitor_custom_event_{ctx['ds'].bk_data_id}"
    models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=link_name,
        monitor_table_id=rt.table_id,
        bkbase_table_id="1001_event_rt",
        storage_type="elasticsearch",
    )
    mocker.patch.object(DataLink, "apply_data_link")
    sync = mocker.patch.object(DataLink, "sync_metadata")
    publish = mocker.patch("metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_table_id_detail")
    apply_event_group_datalink(bk_tenant_id="system", table_id=rt.table_id)
    sync.assert_called_once_with(table_id=rt.table_id, storage_cluster_id=doris_cluster.cluster_id)
    storage.refresh_from_db()
    assert storage.bkbase_table_id == "1001_event_rt"
    publish.assert_called_once_with(bk_tenant_id="system", table_id_list=[rt.table_id], is_publish=True)


def test_modify_doris_config_reapplies_event_link(event_group_v4_records, doris_cluster, mocker):
    ctx = event_group_v4_records
    rt = ctx["rt"]
    models.DorisStorage.create_table(rt.table_id, storage_cluster_id=doris_cluster.cluster_id)
    rt.default_storage = "doris"
    rt.save(update_fields=["default_storage"])
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    apply = mocker.patch("metadata.task.datalink.apply_event_group_datalink")
    rt.modify(operator="admin", external_storage={"doris": {"doris_storage_config": DORIS_CONFIG}})
    apply.assert_called_once_with(bk_tenant_id="system", table_id=rt.table_id)
    assert rt.get_storage("doris").doris_storage_config == DORIS_CONFIG


def test_doris_event_requires_existing_v4_switch(event_group_v4_records, mocker):
    ctx = event_group_v4_records
    ctx["rt"].default_storage = "doris"
    ctx["rt"].save(update_fields=["default_storage"])
    models.ResultTableOption.objects.filter(table_id=ctx["table_id"]).delete()
    apply = mocker.patch.object(DataLink, "apply_data_link")
    with pytest.raises(ValueError, match="V4"):
        apply_event_group_datalink(bk_tenant_id="system", table_id=ctx["table_id"])
    apply.assert_not_called()


def test_event_switch_routes_keep_es_history(event_group_v4_records, doris_cluster, mocker):
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    ctx = event_group_v4_records
    rt = ctx["rt"]
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    mocker.patch.object(models.ResultTable, "apply_datalink")
    models.ESStorage.objects.filter(table_id=rt.table_id).update(index_set=rt.table_id)
    models.StorageClusterRecord.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        cluster_id=ctx["es_cluster"].cluster_id,
        is_current=True,
    )
    rt.modify(
        operator="admin",
        default_storage="doris",
        external_storage={
            "doris": {
                "storage_cluster_id": doris_cluster.cluster_id,
                "bkbase_table_id": "1001_event_rt",
                "doris_storage_config": DORIS_CONFIG,
            }
        },
    )
    details, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[rt.table_id])
    route = details[rt.table_id]
    assert route["storage_id"] == doris_cluster.cluster_id
    assert route["db"] == "1001_event_rt"
    segments = models.StorageClusterRecord.objects.filter(table_id=rt.table_id).order_by("enable_time")
    assert segments[0].disable_time == segments[1].enable_time
    assert not segments[0].is_current
    assert segments[1].is_current
    history = route["storage_cluster_records"]
    assert {segment["storage_id"] for segment in history} == {ctx["es_cluster"].cluster_id, doris_cluster.cluster_id}
    assert models.ESStorage.objects.filter(table_id=rt.table_id).exists()
    assert SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="other", table_id_list=[rt.table_id])[0] == {}
