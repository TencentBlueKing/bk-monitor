from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import SurrealDBBindingConfig
from metadata.service.surrealdb_materialized_view import SurrealDBRemoteConfig


def _binding():
    return SurrealDBBindingConfig.objects.create(
        name="graph_binding",
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_name="graph_link",
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="graph_binding",
        vertices=[{"name": "node", "id_fields": ["node"]}],
        relations=[{"name": "node_with_node", "from": "node", "to": "node"}],
    )


def _remote_config() -> SurrealDBRemoteConfig:
    return {
        "metadata": {
            "name": "graph_binding",
            "annotations": {"SurrealDBNamespace": "bkmonitor", "SurrealDBDatabase": "biz_2"},
        },
        "status": {"phase": DataLinkResourceStatus.OK.value},
    }


@pytest.mark.django_db(databases="__all__")
def test_reconcile_surrealdb_materialized_views_forces_task(mocker):
    binding = _binding()
    list_data_link = mocker.patch(
        "metadata.management.commands.reconcile_surrealdb_materialized_views.api.bkdata.list_data_link",
        return_value=[_remote_config()],
    )
    reconcile = mocker.patch(
        "metadata.management.commands.reconcile_surrealdb_materialized_views.reconcile_surrealdb_materialized_view.run"
    )
    out = StringIO()

    call_command(
        "reconcile_surrealdb_materialized_views",
        bk_tenant_id="system",
        namespace="bkmonitor",
        binding_name=binding.name,
        stdout=out,
    )

    list_data_link.assert_called_once_with(
        bk_tenant_id="system",
        namespace="bkmonitor",
        kind=DataLinkKind.get_choice_value(DataLinkKind.SURREALDBBINDING.value),
    )
    reconcile.assert_called_once_with(binding.pk, _remote_config(), force=True)
    assert "已强制重新下发物化视图定义" in out.getvalue()


@pytest.mark.django_db(databases="__all__")
def test_reconcile_surrealdb_materialized_views_rejects_missing_remote_binding(mocker):
    binding = _binding()
    mocker.patch(
        "metadata.management.commands.reconcile_surrealdb_materialized_views.api.bkdata.list_data_link",
        return_value=[],
    )
    with pytest.raises(CommandError, match="重建失败"):
        call_command(
            "reconcile_surrealdb_materialized_views",
            bk_tenant_id="system",
            namespace="bkmonitor",
            binding_name=binding.name,
        )
