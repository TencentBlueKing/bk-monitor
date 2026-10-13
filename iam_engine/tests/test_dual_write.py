from unittest.mock import Mock

from iam_engine.migration.dual_write import DualWriteGrantOrchestrator
from iam_engine.provider.capabilities import PreparedAuthorizationGrant


APPLICATION = {"creator": "user", "system": "system", "type": "space", "id": "-1"}


def build():
    legacy, current, dispatch, observer = Mock(), Mock(), Mock(), Mock()
    prepared = PreparedAuthorizationGrant(
        payload=[{"expired_at": 2000000000}], role_id="space_operator", expired_at=2000000000
    )
    current.prepare_resource_creator_actions.return_value = prepared
    callbacks = []
    engine = DualWriteGrantOrchestrator(
        writers=(("v3", legacy), ("v4", current)),
        tenant_id="tenant-a",
        operator="user",
        dispatch_retry_grant=dispatch,
        grant_observer=observer,
        on_commit=callbacks.append,
    )
    return engine, legacy, current, dispatch, observer, callbacks


def test_selected_union_writers_run_synchronously():
    engine, legacy, current, dispatch, _, callbacks = build()
    engine.grant_creator_action(APPLICATION)
    legacy.grant_resource_creator_actions.assert_called_once_with(APPLICATION)
    current.grant_prepared.assert_called_once()
    assert callbacks == []
    dispatch.assert_not_called()


def test_current_failure_queues_after_commit_with_frozen_expiry():
    engine, _, current, dispatch, observer, callbacks = build()
    current.grant_prepared.side_effect = TimeoutError("offline")
    engine.grant_creator_action(APPLICATION)
    dispatch.assert_not_called()
    assert len(callbacks) == 1
    callbacks[0]()
    kwargs = dispatch.call_args.args[0]
    assert kwargs["tenant_id"] == "tenant-a"
    assert kwargs["expired_at"] == kwargs["payload"][0]["expired_at"] == 2000000000
    observer.assert_any_call("v4", "space", "fallback_dispatched")


def test_rollback_never_runs_registered_callback():
    engine, _, current, dispatch, _, callbacks = build()
    current.grant_prepared.side_effect = TimeoutError("offline")
    engine.grant_creator_action(APPLICATION)
    # Transaction adapter discards callbacks on rollback, as Django.on_commit does.
    callbacks.clear()
    dispatch.assert_not_called()


def test_preparation_error_is_terminal_and_cannot_replay_incomplete_request():
    engine, legacy, current, dispatch, observer, callbacks = build()
    current.prepare_resource_creator_actions.side_effect = ValueError("bad resource")
    engine.grant_creator_action(APPLICATION)
    legacy.grant_resource_creator_actions.assert_called_once()
    assert callbacks == []
    dispatch.assert_not_called()
    observer.assert_any_call("v4", "space", "prepare_failed")


def test_observer_and_dispatch_errors_do_not_break_other_commit_callbacks():
    engine, _, current, dispatch, observer, callbacks = build()
    current.grant_prepared.side_effect = TimeoutError("offline")
    dispatch.side_effect = RuntimeError("broker unavailable")
    observer.side_effect = RuntimeError("metrics unavailable")
    engine.grant_creator_action(APPLICATION)
    callbacks[0]()
    dispatch.assert_called_once()
