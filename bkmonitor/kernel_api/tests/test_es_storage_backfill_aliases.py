import datetime
from unittest.mock import Mock, PropertyMock

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin import es_storage as rpc
from metadata.models.storage import ESStorage


@pytest.fixture
def storage(mocker):
    storage = ESStorage(table_id="test.events", retention=3, need_create_index=True, date_format="%Y%m%d")
    mocker.patch.object(
        ESStorage,
        "now",
        new_callable=PropertyMock,
        return_value=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
    )
    mocker.patch.object(storage, "get_index_names", return_value=["v2_test_events_20260101_0"])
    mocker.patch.object(storage, "_update_aliases_with_retry")
    return storage


def test_default_retention_preview_crosses_year(storage):
    result = storage.backfill_aliases()
    assert result["days"] == 3
    assert result["start_date"] == "2025-12-30"
    assert result["end_date"] == "2026-01-01"
    assert result["aliases"] == [
        "write_20251230_test_events",
        "test_events_20251230_read",
        "write_20251231_test_events",
        "test_events_20251231_read",
        "write_20260101_test_events",
        "test_events_20260101_read",
    ]
    assert result["dry_run"] is True
    storage._update_aliases_with_retry.assert_not_called()


def test_backfill_one_day_submits_only_alias_additions(storage):
    result = storage.backfill_aliases(days=1, dry_run=False)
    assert result["start_date"] == result["end_date"] == "2026-01-01"
    storage._update_aliases_with_retry.assert_called_once_with(
        actions=[
            {"add": {"index": "v2_test_events_20260101_0", "alias": "write_20260101_test_events"}},
            {"add": {"index": "v2_test_events_20260101_0", "alias": "test_events_20260101_read"}},
        ],
        new_index_name="v2_test_events_20260101_0",
    )


@pytest.mark.parametrize("days", [0, -1, 4, 1.5, True, "2"])
def test_invalid_days_do_not_access_es(storage, days):
    with pytest.raises(ValueError, match="days"):
        storage.backfill_aliases(days=days, dry_run=False)
    storage.get_index_names.assert_not_called()
    storage._update_aliases_with_retry.assert_not_called()


@pytest.mark.parametrize("indices", [[], ["index1", "index2"]])
def test_requires_single_index(storage, indices):
    storage.get_index_names.return_value = indices
    with pytest.raises(ValueError, match="只有一个物理索引"):
        storage.backfill_aliases(dry_run=False)
    storage._update_aliases_with_retry.assert_not_called()


@pytest.mark.parametrize(
    "field,value", [("origin_table_id", "physical.rt"), ("need_create_index", False), ("date_format", "%Y%m%d%H")]
)
def test_unsupported_storage_does_not_access_es(storage, field, value):
    setattr(storage, field, value)
    with pytest.raises(ValueError):
        storage.backfill_aliases(dry_run=False)
    storage.get_index_names.assert_not_called()


def test_es_failure_propagates(storage):
    storage._update_aliases_with_retry.side_effect = RuntimeError("ES unavailable")
    with pytest.raises(RuntimeError, match="ES unavailable"):
        storage.backfill_aliases(dry_run=False)


@pytest.mark.parametrize("params,days,dry_run", [({}, 3, True), ({"days": 1, "dry_run": False}, 1, False)])
def test_rpc_calls_model_with_tenant_scope(storage, monkeypatch, params, days, dry_run):
    lookup = Mock(return_value=storage)
    monkeypatch.setattr(ESStorage.objects, "get", lookup)
    result = rpc.backfill_es_storage_aliases({"bk_tenant_id": "tenant-a", "table_id": "test.events", **params})
    lookup.assert_called_once_with(bk_tenant_id="tenant-a", table_id="test.events")
    assert result["data"]["days"] == days
    assert result["data"]["dry_run"] is dry_run
    if dry_run:
        storage._update_aliases_with_retry.assert_not_called()
    else:
        storage._update_aliases_with_retry.assert_called_once()


def test_rpc_reports_retention_limit(storage, monkeypatch):
    monkeypatch.setattr(ESStorage.objects, "get", Mock(return_value=storage))
    with pytest.raises(CustomException, match="存储时长"):
        rpc.backfill_es_storage_aliases({"table_id": "test.events", "days": 4})


def test_rpc_is_registered():
    function = KernelRPCRegistry.get_function_detail(rpc.FUNC_ES_STORAGE_BACKFILL_ALIASES)
    assert "days" in function["params_schema"]
    assert "dry_run" in function["params_schema"]


@pytest.mark.parametrize(
    "hour,minute,expected_days",
    [(15, 59, 3), (16, 0, 2), (16, 1, 2)],
)
@pytest.mark.parametrize("requested_days", [None, 3])
def test_backfill_excludes_aliases_at_cleanup_boundary(storage, mocker, hour, minute, expected_days, requested_days):
    # time_zone=-8 时，12/30 别名解析为 12/29 16:00 UTC，1/2 16:00 恰好到清理边界。
    storage.time_zone = -8
    mocker.patch.object(
        ESStorage,
        "now",
        new_callable=PropertyMock,
        return_value=datetime.datetime(2026, 1, 2, hour, minute, tzinfo=datetime.timezone.utc),
    )
    result = storage.backfill_aliases(days=requested_days, dry_run=False)
    assert result["days"] == expected_days
    assert result["start_date"] == ("2025-12-30" if expected_days == 3 else "2025-12-31")
    aliases = result["aliases"]
    assert len(aliases) == expected_days * 2
    groups = storage.group_expired_alias(
        {result["target_index"]: {"aliases": dict.fromkeys(aliases, {})}}, storage.retention
    )
    assert groups[result["target_index"]]["expired_alias"] == []
    actions = storage._update_aliases_with_retry.call_args.kwargs["actions"]
    assert [action["add"]["alias"] for action in actions] == aliases


def test_backfill_does_not_submit_when_all_aliases_expired(storage, mocker):
    storage.retention = 1
    storage.time_zone = -8
    mocker.patch.object(
        ESStorage,
        "now",
        new_callable=PropertyMock,
        return_value=datetime.datetime(2026, 1, 2, 16, tzinfo=datetime.timezone.utc),
    )
    result = storage.backfill_aliases(dry_run=False)
    assert result["days"] == 0
    assert result["aliases"] == []
    assert result["start_date"] is None
    assert result["end_date"] is None
    storage._update_aliases_with_retry.assert_not_called()
