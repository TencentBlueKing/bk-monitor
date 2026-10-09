"""
测试 metric_plugin.old_models 模块。
"""

import datetime
from types import SimpleNamespace

import pytest
from django.core.files.storage import FileSystemStorage
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
    MetricPluginModel,
    MetricPluginVersionModel,
)
from bk_monitor_base.infras import storage as storage_module


def _fake_storage_factory(*args, **kwargs):
    """为旧模型测试提供一个可实例化的本地存储。"""
    return lambda: FileSystemStorage(location="/tmp")


storage_module.get_storage_func = _fake_storage_factory

from bk_monitor_base.domains.metric_plugin import old_models


class _StaticQuerySet(list):
    """提供最小 queryset 接口，满足迁移代码中的链式调用。"""

    def order_by(self, *args, **kwargs):
        """返回自身，模拟 queryset 排序后的结果。"""
        return self


def _build_old_plugin_fixture() -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    """构造迁移所需的旧模型桩数据。"""
    old_plugin = SimpleNamespace(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        plugin_id="legacy_plugin",
        plugin_type="Script",
        label="legacy_label",
        is_internal=False,
        create_time=datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.UTC),
        create_user="legacy_creator",
        is_deleted=False,
        tag="legacy_tag",
    )
    old_config = SimpleNamespace(
        config_json="[]",
        collector_json="{}",
        is_support_remote=False,
    )
    old_info = SimpleNamespace(
        plugin_display_name="旧插件",
        description_md="# 旧插件",
        metric_json="[]",
        logo=None,
        enable_field_blacklist=True,
    )
    old_version = SimpleNamespace(
        bk_tenant_id="test_tenant",
        config_version=1,
        info_version=0,
        config=old_config,
        info=old_info,
        stage=old_models.PluginVersionHistory.Stage.DEBUG,
        version_log="初始化版本",
        create_time=datetime.datetime(2024, 2, 3, 4, 5, 6, tzinfo=datetime.UTC),
        create_user="legacy_version_creator",
        signature="legacy-signature",
        is_deleted=False,
    )
    old_deployment_config = SimpleNamespace(
        subscription_id=12345,
        task_ids="[101, 102]",
        plugin_version=old_version,
        params='{"collector": {"period": 60}}',
        target_nodes='[{"bk_host_id": 1}]',
        remote_collecting_host="",
        target_node_type=old_models.TargetNodeType.INSTANCE,
        create_time=datetime.datetime(2024, 3, 4, 5, 6, 7, tzinfo=datetime.UTC),
        create_user="legacy_deployment_creator",
    )
    old_collect_config = SimpleNamespace(
        pk=9527,
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        plugin_id="legacy_plugin",
        name="legacy_deployment",
        deployment_config=old_deployment_config,
        last_operation=old_models.OperationType.START,
        operation_result=old_models.OperationResult.SUCCESS,
        create_time=datetime.datetime(2024, 4, 5, 6, 7, 8, tzinfo=datetime.UTC),
        create_user="legacy_collect_creator",
        update_time=datetime.datetime(2024, 5, 6, 7, 8, 9, tzinfo=datetime.UTC),
        update_user="legacy_collect_updater",
        is_deleted=False,
    )
    return old_plugin, old_version, old_collect_config


def _mock_old_model_queries(
    mocker: MockerFixture,
    old_plugin: SimpleNamespace,
    old_version: SimpleNamespace,
    old_collect_config: SimpleNamespace,
) -> None:
    """Mock 旧模型查询，避免依赖历史库表。"""
    mocker.patch.object(old_models, "collect_and_migrate_all_files", return_value={})
    mocker.patch.object(old_models.CollectorPluginMeta.objects, "filter", return_value=_StaticQuerySet([old_plugin]))
    mocker.patch.object(old_models.PluginVersionHistory.objects, "filter", return_value=_StaticQuerySet([old_version]))
    mocker.patch.object(
        old_models.CollectConfigMeta.objects,
        "filter",
        return_value=_StaticQuerySet([old_collect_config]),
    )


@pytest.mark.django_db(databases=["default"])
class TestMigrateOldModelsToNewModels:
    """测试旧模型迁移到新模型时的时间字段保真逻辑。"""

    def test_should_preserve_timestamps_when_creating_records(self, mocker: MockerFixture) -> None:
        """首次迁移时，应保留旧模型时间字段而不是写入当前时间。"""
        old_plugin, old_version, old_collect_config = _build_old_plugin_fixture()
        _mock_old_model_queries(mocker, old_plugin, old_version, old_collect_config)

        result = old_models.migrate_old_models_to_new_models(
            bk_tenant_id=old_plugin.bk_tenant_id,
            plugin_ids=[old_plugin.plugin_id],
        )

        plugin_model = MetricPluginModel.objects.get(
            bk_tenant_id=old_plugin.bk_tenant_id,
            plugin_id=old_plugin.plugin_id,
        )
        version_model = MetricPluginVersionModel.objects.get(
            bk_tenant_id=old_plugin.bk_tenant_id,
            plugin=plugin_model,
            version="000001.000000",
        )
        deployment_model = MetricPluginDeploymentModel.objects.get(pk=old_collect_config.pk)
        deployment_version_model = MetricPluginDeploymentVersionModel.objects.get(deployment=deployment_model)

        assert result["errors"] == []
        assert result["plugins_migrated"] == 1
        assert result["versions_migrated"] == 1
        assert result["deployments_migrated"] == 1
        assert plugin_model.created_at == old_plugin.create_time
        assert version_model.updated_at == old_version.create_time
        assert version_model.enable_metric_discovery is True
        assert deployment_model.created_at == old_collect_config.create_time
        assert deployment_model.updated_at == old_collect_config.update_time
        assert deployment_version_model.created_at == old_collect_config.deployment_config.create_time

    def test_should_preserve_timestamps_when_updating_existing_records(self, mocker: MockerFixture) -> None:
        """重复迁移时，也应将 auto_now 字段回写为旧时间。"""
        old_plugin, old_version, old_collect_config = _build_old_plugin_fixture()
        _mock_old_model_queries(mocker, old_plugin, old_version, old_collect_config)

        plugin_model = MetricPluginModel.objects.create(
            bk_tenant_id=old_plugin.bk_tenant_id,
            bk_biz_id=999,
            plugin_id=old_plugin.plugin_id,
            type="Script",
            created_by="wrong_creator",
            label="wrong_label",
        )
        MetricPluginModel.objects.filter(pk=plugin_model.pk).update(
            created_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)
        )

        version_model = MetricPluginVersionModel.objects.create(
            bk_tenant_id=old_plugin.bk_tenant_id,
            bk_biz_id=old_plugin.bk_biz_id,
            plugin=plugin_model,
            name="错误版本",
            description_md="",
            params=[],
            define={},
            version="000001.000000",
            version_log="wrong",
            status="debug",
            updated_by="wrong_updater",
        )
        MetricPluginVersionModel.objects.filter(pk=version_model.pk).update(
            updated_at=datetime.datetime(2025, 2, 2, 0, 0, 0, tzinfo=datetime.UTC)
        )

        deployment_model = MetricPluginDeploymentModel.objects.create(
            id=old_collect_config.pk,
            bk_tenant_id=old_plugin.bk_tenant_id,
            bk_biz_id=old_plugin.bk_biz_id,
            plugin=plugin_model,
            name=old_collect_config.name,
            created_by="wrong_creator",
            updated_by="wrong_updater",
        )
        MetricPluginDeploymentModel.objects.filter(pk=deployment_model.pk).update(
            created_at=datetime.datetime(2025, 3, 3, 0, 0, 0, tzinfo=datetime.UTC),
            updated_at=datetime.datetime(2025, 4, 4, 0, 0, 0, tzinfo=datetime.UTC),
        )

        old_models.migrate_old_models_to_new_models(
            bk_tenant_id=old_plugin.bk_tenant_id,
            plugin_ids=[old_plugin.plugin_id],
        )

        plugin_model.refresh_from_db()
        version_model.refresh_from_db()
        deployment_model.refresh_from_db()

        assert plugin_model.created_at == old_plugin.create_time
        assert version_model.updated_at == old_version.create_time
        assert version_model.enable_metric_discovery is True
        assert deployment_model.created_at == old_collect_config.create_time
        assert deployment_model.updated_at == old_collect_config.update_time
