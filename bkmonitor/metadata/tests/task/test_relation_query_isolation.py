"""Run the relation sync logic with storage and service boundaries replaced.

These tests do not need project services or a database. The entire production
task is loaded; only imports that connect to Django models/services are replaced.
"""

import ast
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def relation_sync():
    source_path = Path(__file__).parents[2] / "task" / "sync_cmdb_relation.py"
    tree = ast.parse(source_path.read_text())
    tree.body = [
        node for node in tree.body if not isinstance(node, ast.ImportFrom) or node.module in {"dataclasses", "typing"}
    ]
    data_source = type("DataSource", (), {"objects": Mock(), "create_data_source": Mock()})
    result_table = type("ResultTable", (), {"objects": Mock(), "modify": Mock()})
    group = type("TimeSeriesGroup", (), {"objects": Mock(), "create_time_series_group": Mock()})
    existing_table = SimpleNamespace(bk_tenant_id="system", table_id="2_bkcc_built_in_time_series.__default__")
    existing_group = SimpleNamespace(**vars(existing_table), token="existing-group-token")
    result_table.objects.filter.return_value = [existing_table]
    group.objects.filter.return_value = [existing_group]
    data_source.objects.get.return_value = SimpleNamespace(bk_data_id=50010, token="independent-data-source-token")
    data_source.create_data_source.return_value = SimpleNamespace(bk_data_id=50011)
    group.create_time_series_group.return_value = SimpleNamespace(
        token="created-group-token", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc)
    )
    redis = Mock()
    redis.hgetall.return_value = {b"bkcc__2": b'{"token":"old-token"}', b"bkcc__3": b'{"token":""}'}
    namespace = {
        "__name__": __name__,
        "settings": SimpleNamespace(BUILTIN_DATA_RT_REDIS_KEY="relation:tokens"),
        "transaction": SimpleNamespace(atomic=lambda **kwargs: nullcontext()),
        "share_lock": lambda **kwargs: lambda func: func,
        "bk_biz_id_to_bk_tenant_id": lambda biz_id: "system",
        "transform_data_id_to_token": Mock(return_value="fallback-token"),
        "metrics": Mock(),
        "config": SimpleNamespace(DATABASE_CONNECTION_NAME="monitor_api"),
        "DataSource": data_source,
        "ResultTable": result_table,
        "TimeSeriesGroup": group,
        "Label": SimpleNamespace(RESULT_TABLE_LABEL_OTHER="other"),
        "Space": Mock(),
        "EtlConfigs": SimpleNamespace(BK_STANDARD_V2_TIME_SERIES=SimpleNamespace(value="bk_standard_v2_time_series")),
        "RedisTools": redis,
        "TASK_STARTED": "started",
        "TASK_FINISHED_SUCCESS": "success",
    }
    exec(compile(tree, str(source_path), "exec"), namespace)
    return SimpleNamespace(**namespace)


@pytest.mark.parametrize("query_biz_ids", [[], [2, 3]])
@pytest.mark.parametrize("old_biz_ids", [[], [2, 3]])
def test_query_gray_list_does_not_change_relation_writes(relation_sync, query_biz_ids, old_biz_ids):
    relation_sync.settings.RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST = query_biz_ids
    relation_sync.settings.GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST = old_biz_ids

    relation_sync.sync_relation_redis_data()

    writes = {call.args[1]: json.loads(call.args[2]) for call in relation_sync.RedisTools.hset_to_redis.call_args_list}
    assert writes["bkcc__2"]["token"] == "existing-group-token"
    assert writes["bkcc__3"] == {"token": "created-group-token", "modifyTime": 1733198214}
    relation_sync.DataSource.create_data_source.assert_called_once()
    relation_sync.TimeSeriesGroup.create_time_series_group.assert_called_once()
    assert relation_sync.TimeSeriesGroup.create_time_series_group.call_args.kwargs["is_sync_db"] is True
    relation_sync.ResultTable.modify.assert_not_called()
    assert relation_sync.DataSource.objects.get.return_value.token == "independent-data-source-token"


def test_existing_token_without_result_table_is_preserved(relation_sync):
    relation_sync.RedisTools.hgetall.return_value = {b"bkcc__3": b'{"token":"existing-token"}'}

    relation_sync.sync_relation_redis_data()

    relation_sync.DataSource.create_data_source.assert_not_called()
    relation_sync.TimeSeriesGroup.create_time_series_group.assert_not_called()
    relation_sync.RedisTools.hset_to_redis.assert_not_called()


def test_failed_business_does_not_prevent_next_token_sync(relation_sync):
    relation_sync.DataSource.objects.get.side_effect = RuntimeError("metadata lookup failed")

    relation_sync.sync_relation_redis_data()

    relation_sync.RedisTools.hset_to_redis.assert_called_once()
    assert relation_sync.RedisTools.hset_to_redis.call_args.args[1] == "bkcc__3"
