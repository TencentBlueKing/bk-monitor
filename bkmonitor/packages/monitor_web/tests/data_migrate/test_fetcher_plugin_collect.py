import pytest
from constants.cmdb import TargetNodeType, TargetObjectType
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.data_migrate.data_export import _iter_fetcher_objects
from monitor_web.data_migrate.fetcher.plugin_collect import get_collector_plugin_fetcher
from monitor_web.models import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.plugin.constant import PluginType

pytestmark = pytest.mark.django_db


def _create_plugin_with_version(plugin_id: str, bk_biz_id: int) -> tuple[CollectorPluginMeta, PluginVersionHistory]:
    plugin = CollectorPluginMeta.objects.create(
        plugin_id=plugin_id,
        bk_biz_id=bk_biz_id,
        plugin_type=PluginType.SCRIPT,
        label="os",
    )
    config = CollectorPluginConfig.objects.create(config_json=[], collector_json={})
    info = CollectorPluginInfo.objects.create(plugin_display_name=plugin_id, metric_json=[])
    version = PluginVersionHistory.objects.create(
        plugin_id=plugin.plugin_id,
        config=config,
        info=info,
        config_version=1,
        info_version=1,
        stage=PluginVersionHistory.Stage.RELEASE,
        is_packaged=True,
    )
    version.plugin = plugin
    return plugin, version


def test_get_collector_plugin_fetcher_excludes_global_plugin_definition_for_biz_export():
    biz_id = 2
    global_plugin, global_version = _create_plugin_with_version("global_plugin", bk_biz_id=0)
    biz_plugin, biz_version = _create_plugin_with_version("biz_plugin", bk_biz_id=biz_id)

    deployment = DeploymentConfigVersion.objects.create(
        plugin_version=global_version,
        config_meta_id=0,
        subscription_id=0,
        target_node_type=TargetNodeType.INSTANCE,
        params={},
        target_nodes=[],
    )
    collect_config = CollectConfigMeta.objects.create(
        bk_biz_id=biz_id,
        name="collect_global_plugin",
        collect_type=PluginType.SCRIPT,
        plugin_id=global_plugin.plugin_id,
        target_object_type=TargetObjectType.HOST,
        deployment_config=deployment,
        last_operation=OperationType.CREATE,
        operation_result=OperationResult.SUCCESS,
        label="os",
    )
    deployment.config_meta_id = collect_config.id
    deployment.save(update_fields=["config_meta_id"])

    export_objects = list(_iter_fetcher_objects(get_collector_plugin_fetcher(biz_id)))

    exported_plugin_meta_keys = {
        (instance.plugin_id, instance.bk_biz_id)
        for instance in export_objects
        if isinstance(instance, CollectorPluginMeta)
    }
    exported_version_plugin_ids = {
        instance.plugin_id for instance in export_objects if isinstance(instance, PluginVersionHistory)
    }
    exported_plugin_config_ids = {
        instance.id for instance in export_objects if isinstance(instance, CollectorPluginConfig)
    }
    exported_plugin_info_ids = {instance.id for instance in export_objects if isinstance(instance, CollectorPluginInfo)}

    assert (global_plugin.plugin_id, global_plugin.bk_biz_id) not in exported_plugin_meta_keys
    assert (biz_plugin.plugin_id, biz_plugin.bk_biz_id) in exported_plugin_meta_keys
    assert global_version.plugin_id not in exported_version_plugin_ids
    assert biz_version.plugin_id in exported_version_plugin_ids
    assert global_version.config_id not in exported_plugin_config_ids
    assert global_version.info_id not in exported_plugin_info_ids
