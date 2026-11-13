"""独立 DataSource 登记不参与采集链路同步或空链路迁移。"""

from unittest.mock import MagicMock

from metadata import models
from metadata.models.data_link.constants import DataLinkKind
from metadata.task.bkbase import _reconcile_data_link_components


def test_sync_only_managed_dataid_namespaces(mocker):
    records = [
        models.DataIdConfig(bk_tenant_id="system", namespace=ns, name=f"source_{ns}", bk_data_id=960001)
        for ns in ("bkmonitor", "bklog", "shared")
    ]
    queryset = mocker.patch.object(models.DataIdConfig.objects, "all").return_value
    queryset.iterator.return_value = iter(records)

    def filtered_records(**kwargs):
        filtered = MagicMock()
        filtered.iterator.return_value = iter(r for r in records if r.namespace in kwargs["namespace__in"])
        return filtered

    queryset.filter.side_effect = filtered_records
    # 其他类型仍应同步其已有 namespace，不能被 DataId 的过滤收窄。
    databus = models.DataBusConfig(bk_tenant_id="system", namespace="shared", name="shared_bus", data_link_name="")
    mocker.patch.object(models.DataBusConfig.objects, "all").return_value.iterator.return_value = iter([databus])
    mocker.patch(
        "metadata.task.bkbase.COMPONENT_CLASS_MAP",
        {
            DataLinkKind.DATAID.value: models.DataIdConfig,
            DataLinkKind.DATABUS.value: models.DataBusConfig,
        },
    )
    mocker.patch("metadata.task.bkbase._get_data_link_discovery_tenant_ids", return_value=set())
    request = mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", return_value=[])
    _reconcile_data_link_components()
    assert {(c.kwargs["kind"], c.kwargs["namespace"]) for c in request.call_args_list} == {
        ("dataids", "bkmonitor"),
        ("dataids", "bklog"),
        ("databuses", "shared"),
    }
