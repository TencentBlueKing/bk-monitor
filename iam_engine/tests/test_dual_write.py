from unittest.mock import Mock

import pytest

from iam_engine.migration.dual_write import DualWriteGrantOrchestrator

APPLICATION = {"creator": "user", "system": "system", "type": "space", "id": "-1"}


def build():
    legacy, current, observer = Mock(), Mock(), Mock()
    legacy.grant_resource_creator_actions.return_value = "legacy-result"
    engine = DualWriteGrantOrchestrator(
        writers=(("v3", legacy), ("v4", current)),
        tenant_id="tenant-a",
        grant_observer=observer,
    )
    return engine, legacy, current, observer


def test_selected_union_writers_each_run_once_synchronously():
    engine, legacy, current, observer = build()
    assert engine.grant_creator_action(APPLICATION) == "legacy-result"
    legacy.grant_resource_creator_actions.assert_called_once_with(APPLICATION)
    current.grant_resource_creator_actions.assert_called_once_with(APPLICATION)
    observer.assert_any_call("v3", "space", "succeeded")
    observer.assert_any_call("v4", "space", "succeeded")


@pytest.mark.parametrize("target", ["v3", "v4"])
def test_failure_is_reported_once_without_automatic_replay(target):
    engine, legacy, current, observer = build()
    writer = legacy if target == "v3" else current
    writer.grant_resource_creator_actions.side_effect = TimeoutError("offline")
    engine.grant_creator_action(APPLICATION)
    legacy.grant_resource_creator_actions.assert_called_once()
    current.grant_resource_creator_actions.assert_called_once()
    observer.assert_any_call(target, "space", "failed")


@pytest.mark.parametrize("target", ["v3", "v4"])
def test_strict_failure_propagates_original_error(target):
    engine, legacy, current, _ = build()
    error = ValueError("invalid grant")
    writer = legacy if target == "v3" else current
    writer.grant_resource_creator_actions.side_effect = error
    with pytest.raises(ValueError) as caught:
        engine.grant_creator_action(APPLICATION, raise_exception=True)
    assert caught.value is error
    writer.grant_resource_creator_actions.assert_called_once()


def test_observer_failure_does_not_change_success():
    engine, legacy, current, observer = build()
    observer.side_effect = RuntimeError("metrics unavailable")
    assert engine.grant_creator_action(APPLICATION, raise_exception=True) == "legacy-result"
    legacy.grant_resource_creator_actions.assert_called_once()
    current.grant_resource_creator_actions.assert_called_once()
