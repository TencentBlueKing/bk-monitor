"""链路停用仅停止 Databus，保留历史数据查询所需的组件与映射。"""

import pytest

from metadata import models
from metadata.models.data_link.component_reuse import ALL_DATA_LINK_COMPONENT_KINDS

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.mark.parametrize("strategy", [strategy for strategy, _ in models.DataLink.DATA_LINK_STRATEGY_CHOICES])
def test_delete_data_link_only_stops_databuses(mocker, strategy, databus_remote):
    link = models.DataLink.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        data_link_name="disabled_link",
        data_link_strategy=strategy,
        table_ids=["test.disabled"],
    )
    scope = dict(bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, data_link_name=link.pk, bk_biz_id=2)
    components = [
        component_class.objects.create(name=f"disabled_{component_class.__name__}", **scope)
        for component_class in [models.DataIdConfig, *ALL_DATA_LINK_COMPONENT_KINDS]
    ]
    components.append(models.DataBusConfig.objects.create(name="second_databus", **scope))
    databus_names = {component.name for component in components if isinstance(component, models.DataBusConfig)}
    delete_remote = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    link.delete_data_link()
    link.delete_data_link()

    delete_remote.assert_not_called()
    assert databus_remote.apply.call_count == 2 * len(databus_names)
    assert set(databus_remote.configs) == databus_names
    for config in databus_remote.configs.values():
        assert config["metadata"]["annotations"] == {"owner": "monitor", "task_stopped": "true"}
        assert config["spec"]["consumerGroup"] == "existing-group"
        assert config["metadata"]["labels"] == {"bk_biz_id": "2"}
        assert "status" not in config
    link.refresh_from_db()
    assert link.table_ids == ["test.disabled"]
    for component in components:
        component.refresh_from_db()
        assert component.data_link_name == link.pk


@pytest.mark.parametrize(
    "other_scope",
    [{"bk_tenant_id": "other"}, {"namespace": "other"}, {"data_link_name": "other_link"}],
)
def test_delete_data_link_does_not_stop_other_databuses(mocker, other_scope, databus_remote):
    link = models.DataLink.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        data_link_name="disabled_link",
        data_link_strategy=models.DataLink.BK_LOG,
    )
    scope = dict(bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, data_link_name=link.pk, bk_biz_id=2)
    databus = models.DataBusConfig.objects.create(name="disabled_databus", **scope)
    other = models.DataBusConfig.objects.create(name="other_databus", **(scope | other_scope))
    delete_remote = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    link.delete_data_link()

    delete_remote.assert_not_called()
    databus_remote.get.assert_called_once_with(
        bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, kind="databuses", name=databus.name
    )
    other.refresh_from_db()


def test_result_table_disable_preserves_doris_relations(mocker, databus_remote):
    table = models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id="test.doris",
        is_custom_table=True,
        is_enable=False,
        default_storage=models.ClusterInfo.TYPE_DORIS,
    )
    link = models.DataLink.objects.create(
        bk_tenant_id=table.bk_tenant_id,
        namespace="bkmonitor",
        data_link_name="doris_link",
        data_link_strategy=models.DataLink.BK_LOG,
        table_ids=[table.table_id],
    )
    scope = dict(bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, data_link_name=link.pk, bk_biz_id=2)
    result_table_config = models.ResultTableConfig.objects.create(
        name="doris_rt", table_id=table.table_id, bkbase_table_id="2_doris_rt", **scope
    )
    binding = models.DorisStorageBindingConfig.objects.create(name="doris_binding", **scope)
    models.DataBusConfig.objects.create(name="doris_databus", **scope)
    record = models.BkBaseResultTable.objects.create(
        bk_tenant_id=link.bk_tenant_id,
        data_link_name=link.pk,
        monitor_table_id=table.table_id,
        bkbase_table_id=result_table_config.bkbase_table_id,
        storage_type=models.ClusterInfo.TYPE_DORIS,
    )
    delete_remote = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    table.delete_datalink()

    delete_remote.assert_not_called()
    databus_remote.get.assert_called_once_with(
        bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, kind="databuses", name="doris_databus"
    )
    link.refresh_from_db()
    result_table_config.refresh_from_db()
    binding.refresh_from_db()
    record.refresh_from_db()
    assert result_table_config.bkbase_table_id == record.bkbase_table_id == "2_doris_rt"
    assert models.DataBusConfig.objects.filter(data_link_name=link.pk).exists()


def test_stop_missing_databus_preserves_local_record(mocker, databus_remote):
    from core.errors.api import BKAPIError

    databus = models.DataBusConfig.objects.create(name="missing", bk_biz_id=2)
    databus_remote.get.side_effect = BKAPIError(result={"code": "404", "message": "resource not found"})
    delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")
    databus.stop_config()
    databus.refresh_from_db()
    databus_remote.apply.assert_not_called()
    delete.assert_not_called()


@pytest.mark.parametrize("operation", ["get", "apply"])
@pytest.mark.parametrize("cleanup", [False, True])
def test_stop_failure_preserves_local_record(databus_remote, operation, cleanup):
    from core.errors.api import BKAPIError

    databus = models.DataBusConfig.objects.create(name="failure", bk_biz_id=2)
    # apply 返回 404 也不能触发通用清理路径的本地删除。
    error = BKAPIError(result={"code": "404" if operation == "apply" else "503", "message": "unavailable"})
    getattr(databus_remote, operation).side_effect = error
    with pytest.raises(BKAPIError):
        if cleanup:
            models.DataLink()._cleanup_absent_components([databus], raise_on_error=True)
        else:
            databus.stop_config()
    databus.refresh_from_db()


def test_cleanup_stop_failure_can_retry(databus_remote):
    databus = models.DataBusConfig.objects.create(name="retry", bk_biz_id=2)
    databus_remote.apply.side_effect = RuntimeError("offline")
    models.DataLink()._cleanup_absent_components([databus])
    databus.refresh_from_db()
    databus_remote.apply.side_effect = None
    models.DataLink()._cleanup_absent_components([databus], raise_on_error=True)
    databus.refresh_from_db()
    assert databus_remote.apply.call_count == 2


@pytest.mark.parametrize("component_class", [models.DataBusConfig, models.LogDataBusConfig])
def test_delete_config_still_deletes_databus(mocker, databus_remote, component_class):
    databus = component_class.objects.create(name="delete_explicitly", bk_biz_id=2)
    pk = databus.pk
    delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    databus.delete_config()

    delete.assert_called_once_with(
        bk_tenant_id=databus.bk_tenant_id, namespace=databus.namespace, kind="databuses", name=databus.name
    )
    assert not component_class.objects.filter(pk=pk).exists()
    databus_remote.get.assert_not_called()
    databus_remote.apply.assert_not_called()


@pytest.mark.parametrize(
    ("compose_method", "kwargs"),
    [
        ("compose_config", {"sinks": []}),
        ("compose_log_config", {"sinks": [], "rules": []}),
        ("compose_base_event_config", {}),
    ],
)
def test_databus_config_explicitly_starts_task(mocker, compose_method, kwargs):
    from copy import deepcopy

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    databus = models.DataBusConfig(name="restart", bk_biz_id=2, data_id_name="source")
    config = getattr(databus, compose_method)(**kwargs)
    assert config["metadata"]["annotations"]["task_stopped"] == "false"

    existing = deepcopy(config)
    existing["metadata"]["annotations"] = {"task_stopped": "true", "owner": "monitor"}
    merged = models.DataLink.merge_component_config(existing, config)
    assert merged["metadata"]["annotations"] == {"task_stopped": "false", "owner": "monitor"}
    assert existing["metadata"]["annotations"]["task_stopped"] == "true"
