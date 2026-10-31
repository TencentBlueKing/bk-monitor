"""链路停用仅删除 Databus，保留历史数据查询所需的组件与映射。"""

import pytest

from metadata import models
from metadata.models.data_link.component_reuse import ALL_DATA_LINK_COMPONENT_KINDS

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.mark.parametrize("strategy", [strategy for strategy, _ in models.DataLink.DATA_LINK_STRATEGY_CHOICES])
def test_delete_data_link_only_deletes_databuses(mocker, strategy):
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

    assert delete_remote.call_count == len(databus_names)
    assert {call.kwargs["name"] for call in delete_remote.call_args_list} == databus_names
    assert all(
        call.kwargs["kind"] == "databuses"
        and call.kwargs["bk_tenant_id"] == link.bk_tenant_id
        and call.kwargs["namespace"] == link.namespace
        for call in delete_remote.call_args_list
    )
    link.refresh_from_db()
    assert link.table_ids == ["test.disabled"]
    for component in components:
        if isinstance(component, models.DataBusConfig):
            assert not models.DataBusConfig.objects.filter(pk=component.pk).exists()
        else:
            component.refresh_from_db()
            assert component.data_link_name == link.pk


@pytest.mark.parametrize(
    "other_scope",
    [{"bk_tenant_id": "other"}, {"namespace": "other"}, {"data_link_name": "other_link"}],
)
def test_delete_data_link_does_not_delete_other_databuses(mocker, other_scope):
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

    delete_remote.assert_called_once_with(
        bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, kind="databuses", name=databus.name
    )
    other.refresh_from_db()


def test_result_table_disable_preserves_doris_relations(mocker):
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

    delete_remote.assert_called_once_with(
        bk_tenant_id=link.bk_tenant_id, namespace=link.namespace, kind="databuses", name="doris_databus"
    )
    link.refresh_from_db()
    result_table_config.refresh_from_db()
    binding.refresh_from_db()
    record.refresh_from_db()
    assert result_table_config.bkbase_table_id == record.bkbase_table_id == "2_doris_rt"
    assert not models.DataBusConfig.objects.filter(data_link_name=link.pk).exists()
