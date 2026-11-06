"""页面资源到 Data ID 的只读解析与新旧配置共存。"""

from unittest import mock

import pytest
from django.db import connections
from django.test.utils import CaptureQueriesContext

from apm.models import ApmApplication
from apm.models.datasource import MetricDataSource, TraceDataSource
from bkmonitor.iam import ActionEnum
from bkmonitor.views.resource_storage import QueryResourceStorageSerializer
from monitor.models import UptimeCheckTask
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    CustomEventGroup,
    CustomTSTable,
)
from monitor_web.models.collecting import DeploymentConfigVersion
from monitor_web.models.plugin import CollectorPluginConfig, CollectorPluginInfo, PluginVersionHistory
from monitor_web.scene_view.resources.resource_storage import (
    QueryResourceStorageResource,
    apm_references,
    collecting_references,
    custom_references,
    uptime_references,
)
from monitor_web.scene_view.views import SceneViewViewSet

pytestmark = pytest.mark.django_db(databases="__all__")


def insert(model, **fields):
    obj = model(**fields)
    model.objects.bulk_create([obj])
    return obj


@pytest.mark.parametrize("multi_tenant, new_default", [(False, False), (True, True), (True, False)])
def test_uptime_shared_and_business_storage_coexist(settings, multi_tenant, new_default):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    settings.ENABLE_UPTIMECHECK_BKDATA = new_default
    settings.UPTIMECHECK_HTTP_DATAID = 1011
    insert(UptimeCheckTask, id=12, bk_biz_id=100, name="旧任务", protocol="HTTP", indepentent_dataid=False)
    insert(UptimeCheckTask, id=34, bk_biz_id=100, name="新任务", protocol="HTTP", indepentent_dataid=True)
    insert(UptimeCheckTask, id=56, bk_biz_id=200, name="其他业务", protocol="HTTP", indepentent_dataid=True)
    references = {item["resource_id"]: item for item in uptime_references(100)}
    assert set(references) == {"12", "34"}
    assert references["12"]["bk_data_id"] == 1011
    assert references["12"]["is_builtin"] is True
    assert references["34"]["data_name"] == "uptimecheck_http_100"
    assert "bk_data_id" not in references["34"]


def make_collection(config_id, plugin_id="redis", plugin_type="Exporter"):
    if not CollectorPluginMeta.objects.filter(plugin_id=plugin_id).exists():
        insert(CollectorPluginMeta, plugin_id=plugin_id, plugin_type=plugin_type, bk_biz_id=100, bk_tenant_id="system")
    info = insert(CollectorPluginInfo, plugin_display_name="Redis")
    config = insert(CollectorPluginConfig)
    version = insert(
        PluginVersionHistory,
        bk_tenant_id="system",
        plugin_id=plugin_id,
        info=info,
        config=config,
        config_version=config_id,
    )
    deployment = insert(DeploymentConfigVersion, plugin_version=version, config_meta_id=config_id, params={})
    return insert(
        CollectConfigMeta,
        id=config_id,
        bk_tenant_id="system",
        bk_biz_id=100,
        plugin_id=plugin_id,
        collect_type=plugin_type,
        name=f"collection-{config_id}",
        deployment_config=deployment,
        last_operation="START",
    )


def test_default_collection_grouping_and_explicit_config_selection():
    make_collection(1)
    make_collection(2)
    make_collection(3, "bkprocessbeat", "Process")
    result = collecting_references("system", 100, [])
    assert [(r["scene"], r["resource_id"], r["data_type"]) for r in result] == [
        ("plugin", "redis", "metric"),
        ("collect_config", "3", "process_perf"),
        ("collect_config", "3", "process_port"),
    ]
    assert {r["data_name"] for r in result if r["resource_id"] == "3"} == {
        "100_custom_time_series_process_perf",
        "100_custom_time_series_process_port",
    }
    explicit = collecting_references("system", 100, [{"scene": "collect_config", "resource_ids": ["2"]}])
    assert any(r["scene"] == "collect_config" and r["resource_id"] == "2" for r in explicit)


def test_collection_query_count_does_not_grow_with_configs():
    make_collection(1)
    connection = connections[CollectConfigMeta.objects.db]
    with CaptureQueriesContext(connection) as single:
        collecting_references("system", 100, [])
    for index in range(2, 15):
        make_collection(index)
    with CaptureQueriesContext(connection) as batch:
        result = collecting_references("system", 100, [])
    assert len(result) == 1
    assert len(single) == len(batch) == 2


def test_apm_resolves_saved_shared_and_independent_bindings():
    insert(ApmApplication, bk_tenant_id="tenant-a", bk_biz_id=100, app_name="checkout", app_alias="结算")
    insert(ApmApplication, bk_tenant_id="tenant-b", bk_biz_id=200, app_name="private", app_alias="private")
    insert(
        MetricDataSource,
        bk_biz_id=100,
        app_name="checkout",
        bk_data_id=7001,
        result_table_id="shared.metrics",
        shared_datasource_id=1,
    )
    insert(TraceDataSource, bk_biz_id=100, app_name="checkout", bk_data_id=7002, result_table_id="business.traces")
    result = apm_references("tenant-a", 100)
    assert {(item["data_type"], item["bk_data_id"], item["table_id"]) for item in result} == {
        ("metric", 7001, "shared.metrics"),
        ("trace", 7002, "business.traces"),
    }
    assert apm_references("tenant-b", 100) == []


def test_custom_groups_keep_direct_ids_and_tenant_scope():
    insert(
        CustomTSTable,
        bk_tenant_id="tenant-a",
        bk_biz_id=100,
        time_series_group_id=71,
        bk_data_id=7001,
        name="指标",
        table_id="metrics.base",
    )
    insert(
        CustomEventGroup,
        bk_tenant_id="tenant-a",
        bk_biz_id=100,
        bk_event_group_id=72,
        bk_data_id=7002,
        name="事件",
        table_id="events.base",
        is_enable=False,
    )
    assert custom_references("tenant-a", 100, "custom_metric")[0]["expand_tables"] is True
    event = custom_references("tenant-a", 100, "custom_event")[0]
    assert event["resource_id"] == "72"
    assert event["resource_status"] == "disabled"
    assert custom_references("tenant-b", 100, "custom_event") == []


def test_public_resource_passes_context_tenant_and_one_batch():
    insert(UptimeCheckTask, id=12, bk_biz_id=100, name="旧任务", protocol="HTTP", indepentent_dataid=False)
    insert(UptimeCheckTask, id=34, bk_biz_id=100, name="新任务", protocol="HTTP", indepentent_dataid=True)
    serializer = QueryResourceStorageSerializer(
        data={
            "bk_biz_id": 100,
            "bk_tenant_id": "untrusted",
            "selectors": [{"scene": "uptime_check", "resource_ids": ["34"]}],
        }
    )
    assert serializer.is_valid(), serializer.errors
    with (
        mock.patch("monitor_web.scene_view.resources.resource_storage.get_request_tenant_id", return_value="tenant-a"),
        mock.patch(
            "monitor_web.scene_view.resources.resource_storage.api.metadata.query_resource_storage",
            return_value={"items": []},
        ) as batch,
    ):
        QueryResourceStorageResource().perform_request(serializer.validated_data)
    batch.assert_called_once()
    assert batch.call_args.kwargs["bk_tenant_id"] == "tenant-a"
    assert [item["resource_id"] for item in batch.call_args.kwargs["resources"]] == ["34"]


def test_public_view_uses_business_view_permission():
    view = SceneViewViewSet()
    view.action = "query_resource_storage"
    with mock.patch("monitor_web.scene_view.views.BusinessActionPermission") as permission:
        view.get_permissions()
    permission.assert_called_once_with([ActionEnum.VIEW_BUSINESS])


def test_apm_without_registered_source_keeps_resource_information():
    insert(ApmApplication, bk_tenant_id="system", bk_biz_id=100, app_name="new", app_alias="新应用")
    references = apm_references("system", 100)
    assert {item["data_type"] for item in references} == {"metric", "trace"}
    assert all(item["resource_id"] == "new" and item["error"] for item in references)


def test_recording_rule_selector_is_forwarded_to_metadata_in_one_batch():
    serializer = QueryResourceStorageSerializer(
        data={
            "bk_biz_id": 100,
            "selectors": [{"scene": "recording_rule", "resource_ids": ["12"], "data_types": ["metric"]}],
        }
    )
    assert serializer.is_valid(), serializer.errors
    with (
        mock.patch("monitor_web.scene_view.resources.resource_storage.get_request_tenant_id", return_value="tenant-a"),
        mock.patch(
            "monitor_web.scene_view.resources.resource_storage.api.metadata.query_resource_storage",
            return_value={"items": []},
        ) as batch,
        CaptureQueriesContext(connections["default"]) as queries,
    ):
        QueryResourceStorageResource().perform_request(serializer.validated_data)
    batch.assert_called_once()
    assert batch.call_args.kwargs["resources"] == []
    assert batch.call_args.kwargs["selectors"] == serializer.validated_data["selectors"]
    assert batch.call_args.kwargs["bk_tenant_id"] == "tenant-a"
    assert len(queries) == 0
