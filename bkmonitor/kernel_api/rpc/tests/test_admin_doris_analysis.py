from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from kernel_api.rpc.functions.admin import doris_analysis as analysis
from metadata.models.storage import ClusterInfo


@pytest.mark.parametrize(
    "value,expected", [("1.5 GB", 1610612736), ("0", 0), (None, None), ("unknown", None), ("1,024 KB", 1048576)]
)
def test_capacity_units(value, expected):
    assert ClusterInfo._parse_doris_size_bytes(value) == expected


def test_association_does_not_guess_or_double_count():
    owners = {"db.a": {"3_bklog.demo": "historical"}, "db.b": {"3_bklog.demo": "current", "4_bklog.demo": "current"}}
    assert analysis.associate_table("db", "a", owners)["match_status"] == "historical"
    assert analysis.associate_table("db", "a", owners)["bk_biz_id"] == 3
    assert analysis.associate_table("db", "b", owners)["match_reason"] == "ambiguous"
    assert analysis.associate_table("db", "3_bklog_demo", owners)["matched_table_id"] is None
    assert analysis.sum_known([{"size": None}], "size") is None


def test_snapshot_retains_metadata_when_one_database_usage_fails():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.side_effect = [
        [{"Database": "information_schema"}, {"Database": "db"}, {"Database": "denied"}],
        [{"TABLE_NAME": "a", "TABLE_ROWS": 12}],
        [{"TableName": "a", "Size": "2 KB", "ReplicaCount": 3}, {"TableName": "Total", "Size": "2 KB"}],
        [{"TABLE_NAME": "b", "TABLE_ROWS": None}],
    ]
    show_count = 0

    def execute(sql, *args):
        nonlocal show_count
        if sql == "SHOW DATA":
            show_count += 1
            if show_count == 2:
                raise PermissionError("denied")

    cursor.execute.side_effect = execute
    connection = MagicMock()
    connection.cursor.return_value = cursor
    cluster = SimpleNamespace(
        cluster_id=40, cluster_name="doris", domain_name="localhost", port=9030, username="u", password="p"
    )
    with (
        patch.object(analysis, "build_ownership", return_value={"db.a": {"3_bklog.demo": "current"}}),
        patch.object(analysis.pymysql, "connect", return_value=connection),
    ):
        result, warnings = analysis.build_doris_storage_analysis(cluster, "system")
    assert result["summary"]["total_store_bytes"] == 2048
    assert result["summary"]["table_count"] == 2
    assert result["tables"][0]["row_count"] == 12
    assert result["tables"][1]["store_bytes"] is None
    assert len(warnings) == 1
    connection.close.assert_called_once()
    assert all("COUNT(" not in str(call) for call in cursor.execute.call_args_list)


def test_ownership_merges_current_and_history_and_excludes_virtual():
    current = SimpleNamespace(
        table_id="3_bklog.demo", storage_cluster_id=40, physical_tables={"main": "db.a", "labels": "db.labels"}
    )
    old = SimpleNamespace(table_id="4_bklog.old", storage_cluster_id=41, physical_tables={"main": "other.current"})
    missing = SimpleNamespace(table_id="space_125_bklog.demo", storage_cluster_id=40, physical_tables={})
    binding = SimpleNamespace(table_id=missing.table_id, physical_tables={"main": "db.space"})
    history = [
        SimpleNamespace(table_id=current.table_id, physical_tables={"main": "db.a"}),
        SimpleNamespace(table_id=current.table_id, physical_tables={"main": "db.old"}),
        SimpleNamespace(table_id=old.table_id, physical_tables={"main": "db.migrated"}),
        SimpleNamespace(table_id="virtual", physical_tables={"main": "db.a"}),
    ]
    with (
        patch.object(analysis.models.DorisStorage, "objects") as storages,
        patch.object(analysis.models.StorageClusterRecord, "objects") as records,
        patch("metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.objects") as bindings,
    ):
        storages.filter.return_value.__iter__.return_value = iter([current, old, missing])
        storages.filter.return_value.exclude.return_value.values_list.return_value = ["virtual"]
        records.filter.return_value = history
        bindings.filter.return_value.order_by.return_value = [binding]
        result = analysis.build_ownership(40, "system", [])
    assert result["db.a"] == {current.table_id: "current"}
    assert result["db.labels"] == {current.table_id: "current"}
    assert result["db.old"] == {current.table_id: "historical"}
    assert result["db.migrated"] == {old.table_id: "historical"}
    assert result["db.space"] == {missing.table_id: "current"}
    assert "other.current" not in result


def test_rpc_validates_target_and_marks_inspect():
    from kernel_api.rpc.functions.admin.cluster_info import analyze_doris_storage_usage
    from kernel_api.rpc import KernelRPCRegistry

    assert KernelRPCRegistry.get_function_detail("admin.cluster_info.doris_storage_analysis")
    cluster = SimpleNamespace(cluster_id=40)
    with (
        patch("kernel_api.rpc.functions.admin.cluster_info.models.ClusterInfo.objects") as manager,
        patch.object(analysis, "build_doris_storage_analysis", return_value=({"tables": []}, [])) as build,
    ):
        manager.get.return_value = cluster
        response = analyze_doris_storage_usage({"bk_tenant_id": "tenant-a", "cluster_id": 40})
    manager.get.assert_called_once_with(bk_tenant_id="tenant-a", cluster_id=40, cluster_type="doris")
    build.assert_called_once_with(cluster, "tenant-a")
    assert response["meta"]["safety_level"] == "inspect"
    with pytest.raises(Exception, match="cluster_id"):
        analyze_doris_storage_usage({"cluster_id": "invalid"})
