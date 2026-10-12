from copy import deepcopy
from unittest.mock import Mock

import pytest

from iam_engine.migration.replay import freeze_grant_plan, replay_grant_plan


def entries():
    return [
        {
            "mapping_reference": "reviewed-test-mapping",
            "authorization": {
                "subject": {"type": "user", "id": "alice"},
                "role_id": "space_operator",
                "related_resource_type_id": "indices",
                "resources": [{"type": "indices", "id": "1"}],
            },
            "checks": [{"action_id": "search_log"}, {"action_id": "manage_indices"}],
        }
    ]


def test_preview_is_read_only_and_freezes_default_365_day_expiry():
    original = entries()
    plan = freeze_grant_plan(original, now=100)
    assert plan[0]["authorization"]["expired_at"] == 100 + 365 * 86400
    assert "expired_at" not in original[0]["authorization"]
    write = Mock()
    result = replay_grant_plan(plan, source_allowed=lambda *args: True, target_allowed=lambda *args: False, grant=write)
    assert result[0].status == "would_grant"
    write.assert_not_called()


def test_execute_read_back_and_repeat_do_not_extend_expiry_or_rewrite_v3():
    plan = freeze_grant_plan(entries(), now=100)
    confirmed = []
    writes = []

    def grant(payload):
        writes.append(payload)
        confirmed.append(True)

    options = {"source_allowed": lambda *args: True, "target_allowed": lambda *args: bool(confirmed), "grant": grant}
    assert replay_grant_plan(plan, apply=True, **options)[0].status == "granted"
    assert replay_grant_plan(deepcopy(plan), apply=True, **options)[0].status == "already_allowed"
    assert len(writes) == 1
    assert writes[0]["expired_at"] == 100 + 365 * 86400


@pytest.mark.parametrize("value", [False, None, "true", 1])
def test_denied_or_incomplete_source_blocks_all_writes(value):
    plan = freeze_grant_plan(entries(), now=100)
    write = Mock()
    with pytest.raises(ValueError):
        replay_grant_plan(
            plan, source_allowed=lambda *args: value, target_allowed=lambda *args: False, grant=write, apply=True
        )
    write.assert_not_called()


def test_failed_read_back_is_not_reported_as_success():
    with pytest.raises(RuntimeError, match="read-back"):
        replay_grant_plan(
            freeze_grant_plan(entries(), now=100),
            source_allowed=lambda *args: True,
            target_allowed=lambda *args: False,
            grant=Mock(),
            apply=True,
        )


def test_unknown_role_mapping_is_never_inferred():
    item = entries()
    item[0].pop("mapping_reference")
    with pytest.raises(ValueError, match="reviewed"):
        freeze_grant_plan(item, now=100)


def test_incomplete_target_response_never_triggers_a_write():
    write = Mock()
    with pytest.raises(ValueError, match="incomplete"):
        replay_grant_plan(
            freeze_grant_plan(entries(), now=100),
            source_allowed=lambda *args: True,
            target_allowed=lambda *args: None,
            grant=write,
            apply=True,
        )
    write.assert_not_called()
