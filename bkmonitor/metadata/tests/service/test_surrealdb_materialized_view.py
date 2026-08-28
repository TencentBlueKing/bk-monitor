from unittest.mock import ANY

import pytest

from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import SurrealDBBindingConfig
from metadata.service.surrealdb_materialized_view import (
    SurrealDBScope,
    build_materialized_view_ddl,
    reconcile_materialized_views,
    resolve_surrealdb_scope,
)
from metadata.task.bkbase import reconcile_surrealdb_materialized_view


def _binding(**kwargs):
    defaults = {
        "name": "graph_binding",
        "bk_biz_id": 2,
        "status": DataLinkResourceStatus.OK.value,
        "vertices": [
            {"name": "node", "id_fields": ["bcs_cluster_id", "node"]},
            {"name": "pod", "id_fields": ["bcs_cluster_id", "namespace", "pod"]},
        ],
        "relations": [{"name": "node_with_pod", "from": "node", "to": "pod"}],
    }
    defaults.update(kwargs)
    return SurrealDBBindingConfig(**defaults)


def _remote_config():
    return {
        "metadata": {
            "annotations": {
                "SurrealDBNamespace": "bkmonitor",
                "surrealdb_database": "biz_2",
            }
        },
        "status": {"phase": DataLinkResourceStatus.OK.value},
    }


def test_resolve_surrealdb_scope_from_annotations():
    assert resolve_surrealdb_scope(_remote_config()) == SurrealDBScope(namespace="bkmonitor", database="biz_2")


def test_resolve_surrealdb_scope_rejects_missing_database():
    with pytest.raises(ValueError, match="namespace/database"):
        resolve_surrealdb_scope({"metadata": {"annotations": {"SurrealDBNamespace": "bkmonitor"}}})


def test_build_materialized_view_ddl():
    ddl = build_materialized_view_ddl(_binding(), SurrealDBScope(namespace="bkmonitor", database="biz_2"))

    assert "USE NS `bkmonitor` DB `biz_2`;" in ddl
    assert "BEGIN TRANSACTION;" in ddl
    assert "DEFINE TABLE IF NOT EXISTS `node_with_pod_active_edge_view` SCHEMALESS;" in ddl
    assert "FIELDS source_liveness_id UNIQUE;" in ddl
    assert "FIELDS source_id, active_period_start_ms;" in ddl
    assert "FIELDS source_id, active_period_end_ms;" in ddl
    assert "FIELDS target_id, active_period_start_ms;" in ddl
    assert "FIELDS target_id, active_period_end_ms;" in ddl
    assert "FIELDS source_data.bcs_cluster_id, source_data.node, active_period_start_ms;" in ddl
    assert "FIELDS target_data.bcs_cluster_id, target_data.namespace, target_data.pod, active_period_end_ms;" in ddl
    assert "DEFINE EVENT OVERWRITE `materialize_node_with_pod_active_edge`" in ddl
    assert "ON TABLE `node_with_pod_liveness_record`" in ddl
    assert "source_liveness_id = $after.id" in ddl
    assert "node: $edge.in.node" in ddl
    assert "pod: $edge.out.pod" in ddl
    assert "DEFINE EVENT OVERWRITE `delete_node_with_pod_active_edge`" in ddl
    assert "DELETE `node_with_pod_active_edge_view` WHERE source_liveness_id = $before.id" in ddl
    assert "DEFINE EVENT OVERWRITE `remove_invalid_node_with_pod_active_edge`" in ddl
    assert "DELETE `node_with_pod_active_edge_view` WHERE source_liveness_id = $after.id" in ddl
    assert " TYPE NORMAL AS" not in ddl
    assert ddl.rstrip().endswith("COMMIT TRANSACTION;")


def test_build_materialized_view_ddl_rejects_unsafe_identifier():
    with pytest.raises(ValueError, match="合法的 SurrealDB 标识符"):
        build_materialized_view_ddl(
            _binding(relations=[{"name": "node;REMOVE", "from": "node", "to": "pod"}]),
            SurrealDBScope(namespace="bkmonitor", database="biz_2"),
        )


@pytest.mark.django_db(databases="__all__")
def test_reconcile_materialized_views_applies_once(mocker):
    binding = _binding()
    binding.save()
    query_data = mocker.patch("core.drf_resource.api.bkdata.query_data")

    assert reconcile_materialized_views(binding, _remote_config()) is True
    binding.refresh_from_db()
    assert binding.materialized_view_status == DataLinkResourceStatus.OK.value
    assert len(binding.materialized_view_definition_hash) == 64
    assert binding.materialized_view_last_apply_time is not None
    query_data.assert_called_once_with(sql=ANY, prefer_storage="surrealdb")

    assert reconcile_materialized_views(binding, _remote_config()) is False
    query_data.assert_called_once()


@pytest.mark.django_db(databases="__all__")
def test_reconcile_materialized_views_records_failure(mocker):
    binding = _binding()
    binding.save()
    mocker.patch(
        "core.drf_resource.api.bkdata.query_data",
        side_effect=RuntimeError("query failed"),
    )

    with pytest.raises(RuntimeError, match="query failed"):
        reconcile_materialized_views(binding, _remote_config())

    binding.refresh_from_db()
    assert binding.materialized_view_status == DataLinkResourceStatus.FAILED.value
    assert binding.materialized_view_last_error == "query failed"


@pytest.mark.django_db(databases="__all__")
def test_reconcile_materialized_views_records_scope_failure():
    binding = _binding()
    binding.save()

    with pytest.raises(ValueError, match="namespace/database"):
        reconcile_materialized_views(binding, {"metadata": {"annotations": {"SurrealDBNamespace": "bkmonitor"}}})

    binding.refresh_from_db()
    assert binding.materialized_view_status == DataLinkResourceStatus.FAILED.value
    assert "namespace/database" in binding.materialized_view_last_error


@pytest.mark.django_db(databases="__all__")
def test_reconcile_materialized_view_task_keeps_failure_state():
    binding = _binding()
    binding.save()

    reconcile_surrealdb_materialized_view.run(
        binding.pk,
        {"metadata": {"annotations": {"SurrealDBNamespace": "bkmonitor"}}},
    )

    binding.refresh_from_db()
    assert binding.materialized_view_status == DataLinkResourceStatus.FAILED.value
    assert "namespace/database" in binding.materialized_view_last_error
