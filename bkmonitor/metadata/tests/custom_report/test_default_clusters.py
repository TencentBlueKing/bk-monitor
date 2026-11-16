"""场景默认集群的动态更新、创建入口及兼容优先级。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.cache.backends.locmem import LocMemCache

from bkmonitor.define.global_config import STANDARD_CONFIGS
from bkmonitor.models import GlobalConfig
from bkmonitor.utils import dynamic_settings
from metadata.models import ClusterInfo, DataSource, EventGroup, Label, TimeSeriesGroup
from metadata.models.bcs.cluster import BCSClusterInfo
from metadata.utils import default_cluster


@pytest.fixture(autouse=True)
def scene_cluster_exists(mocker):
    return mocker.patch.object(ClusterInfo.objects, "filter", return_value=Mock(exists=Mock(return_value=True)))


@pytest.mark.parametrize(
    "storage_type", [ClusterInfo.TYPE_KAFKA, ClusterInfo.TYPE_VM, ClusterInfo.TYPE_ES, ClusterInfo.TYPE_DORIS]
)
def test_scene_and_storage_isolation(settings, storage_type):
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {storage_type: 101}, "bcs_event": {storage_type: 102}}
    assert default_cluster.get_scene_default_cluster("custom_event", storage_type, "system") == 101
    assert default_cluster.get_scene_default_cluster("bcs_event", storage_type, "system") == 102
    assert default_cluster.get_scene_default_cluster("other", storage_type, "system", 103) == 103
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {storage_type: None}}
    assert default_cluster.get_scene_default_cluster("custom_event", storage_type, "system", 103) == 103


@pytest.mark.django_db(databases="__all__")
def test_dynamic_config_updates(mocker):
    assert STANDARD_CONFIGS["SCENE_DEFAULT_STORAGE_CLUSTERS"].default == {}
    cache = LocMemCache("scene-default-clusters-test", {})
    cache.clear()
    mocker.patch.object(dynamic_settings, "locmem_cache", cache)
    mocker.patch.object(dynamic_settings, "redis_cache", None)
    GlobalConfig.objects.filter(key="SCENE_DEFAULT_STORAGE_CLUSTERS").delete()
    dynamic = dynamic_settings.DynamicSettings(SimpleNamespace(SCENE_DEFAULT_STORAGE_CLUSTERS={}), GlobalConfig)
    mocker.patch.object(default_cluster, "settings", dynamic)
    assert default_cluster.get_scene_default_cluster("custom_event", "kafka", "system") is None
    for cluster_id in (101, 102):
        dynamic.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {"kafka": cluster_id}}
        assert default_cluster.get_scene_default_cluster("custom_event", "kafka", "system") == cluster_id
    cache.clear()


@pytest.mark.parametrize(
    "etl_config,explicit,configured,expected",
    [
        ("bk_standard_v2_event", None, 101, {"cluster_id": 101}),
        ("bk_standard_v2_event", 102, 101, {"cluster_id": 102}),
        ("bk_standard_v2_event", None, None, {"cluster_type": "kafka", "is_default_cluster": True}),
        ("bk_standard_v2_time_series", None, 101, {"cluster_type": "kafka", "is_default_cluster": True}),
    ],
)
def test_data_source_kafka_selection(settings, mocker, etl_config, explicit, configured, expected):
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {"kafka": configured}}
    mocker.patch.object(Label, "exists_label", return_value=True)
    mocker.patch.object(DataSource.objects, "filter").return_value.exists.return_value = False
    # 在实际集群查询边界停止，避免创建数据源或访问外部服务。
    lookup = mocker.patch.object(ClusterInfo.objects, "get", side_effect=RuntimeError("cluster selected"))
    with pytest.raises(RuntimeError, match="cluster selected"):
        DataSource.create_data_source(
            data_name="event",
            etl_config=etl_config,
            operator="admin",
            source_label="custom",
            type_label="event",
            bk_tenant_id="test-tenant",
            mq_cluster=explicit,
        )
    lookup.assert_called_once_with(bk_tenant_id="test-tenant", **expected)


@pytest.mark.parametrize("explicit,configured,expected", [(None, 201, 201), (202, 201, 202), (None, None, None)])
def test_event_es_selection(settings, explicit, configured, expected):
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {ClusterInfo.TYPE_ES: configured}}
    storage = {"cluster_id": explicit}
    EventGroup.process_default_storage_config(SimpleNamespace(table_id="event_table", bk_tenant_id="system"), storage)
    assert storage["cluster_id"] == expected
    assert storage["index_set"] == "event_table"
    assert storage["raise_on_index_error"] is False


@pytest.mark.parametrize(
    "configured,expected", [({}, (10, 20)), ({"kafka": 101, ClusterInfo.TYPE_ES: 201}, (101, 201))]
)
def test_bcs_event_overrides_leave_metrics_unchanged(settings, mocker, configured, expected):
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"bcs_event": configured}
    settings.BCS_KAFKA_STORAGE_CLUSTER_ID = 10
    settings.BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID = 20
    cluster = BCSClusterInfo(cluster_id="BCS-K8S-test", bk_biz_id=2, bk_tenant_id="system")
    mocker.patch.object(BCSClusterInfo.objects, "filter").return_value.exists.return_value = False
    mocker.patch.object(BCSClusterInfo.objects, "create", return_value=cluster)
    mocker.patch.object(cluster, "save")
    create_data_source = mocker.patch.object(cluster, "create_datasource")
    create_data_source.return_value = SimpleNamespace(bk_data_id=1001, data_name="test")
    event_group = mocker.patch.object(EventGroup, "create_custom_group")
    mocker.patch.object(TimeSeriesGroup, "create_custom_group")
    # ORM 写入已替换，跳过外围事务以便只测试注册流程。
    BCSClusterInfo.register_cluster.__wrapped__(
        BCSClusterInfo,
        bk_biz_id=2,
        cluster_id=cluster.cluster_id,
        project_id="test",
        creator="admin",
        bk_tenant_id="system",
    )
    kafka_by_usage = {call.kwargs["usage"]: call.kwargs["mq_cluster_id"] for call in create_data_source.call_args_list}
    assert kafka_by_usage == {"k8s_metric": 10, "custom_metric": 10, "k8s_event": expected[0]}
    assert event_group.call_args.kwargs["default_storage_config"]["cluster_id"] == expected[1]


@pytest.mark.parametrize("storage_type", [ClusterInfo.TYPE_KAFKA, ClusterInfo.TYPE_ES])
def test_scene_cluster_is_scoped_to_tenant(settings, scene_cluster_exists, storage_type):
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {storage_type: 101}}
    scene_cluster_exists.side_effect = lambda **query: Mock(
        exists=Mock(return_value=query == {"bk_tenant_id": "tenant-a", "cluster_type": storage_type, "cluster_id": 101})
    )
    assert default_cluster.get_scene_default_cluster("custom_event", storage_type, "tenant-a") == 101
    assert default_cluster.get_scene_default_cluster("custom_event", storage_type, "tenant-b") is None
    assert default_cluster.get_scene_default_cluster("custom_event", storage_type, "tenant-b", 202) == 202


@pytest.mark.parametrize("wrong_key", ["es", "vm", "typo"])
def test_nonstandard_key_uses_default(settings, scene_cluster_exists, wrong_key):
    settings.SCENE_DEFAULT_STORAGE_CLUSTERS = {"custom_event": {wrong_key: 101}}
    assert default_cluster.get_scene_default_cluster("custom_event", ClusterInfo.TYPE_ES, "system") is None
    scene_cluster_exists.assert_not_called()


def test_unavailable_scene_kafka_uses_tenant_default(settings, mocker, scene_cluster_exists):
    scene_cluster_exists.return_value.exists.return_value = False
    test_data_source_kafka_selection(
        settings,
        mocker,
        "bk_standard_v2_event",
        None,
        101,
        {"cluster_type": ClusterInfo.TYPE_KAFKA, "is_default_cluster": True},
    )
    scene_cluster_exists.assert_called_once_with(
        bk_tenant_id="test-tenant", cluster_type=ClusterInfo.TYPE_KAFKA, cluster_id=101
    )


def test_unavailable_scene_es_uses_tenant_default(settings, scene_cluster_exists):
    scene_cluster_exists.return_value.exists.return_value = False
    test_event_es_selection(settings, None, 201, None)
    scene_cluster_exists.assert_called_once_with(
        bk_tenant_id="system", cluster_type=ClusterInfo.TYPE_ES, cluster_id=201
    )


def test_unavailable_bcs_scene_uses_legacy_defaults(settings, mocker, scene_cluster_exists):
    scene_cluster_exists.return_value.exists.return_value = False
    test_bcs_event_overrides_leave_metrics_unchanged(
        settings, mocker, {"kafka": 101, ClusterInfo.TYPE_ES: 201}, (10, 20)
    )
