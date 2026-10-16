"""Execute the actual Celery task locally, never dispatch to a broker."""

from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry
from django.test import override_settings

from bkmonitor.iam.tasks.grant import grant_v4_creator_action
from iam_engine.exceptions import ProviderError, ProviderUnavailable


@pytest.fixture
def grant(monkeypatch):
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v4")
    client = Mock()
    provider = Mock()
    provider._get_client.return_value = client
    monkeypatch.setattr("bkmonitor.iam.backends.config.build_provider", lambda name, tenant_id: provider)
    data = {
        "tenant_id": "tenant-a",
        "operator": "alice",
        "role_id": "space_operator",
        "expired_at": 1893456000,
        "resource_meta": {"type": "space", "id": "2\nforged-line"},
        "payload": [
            {
                "subject": {"type": "user", "id": "alice"},
                "expired_at": 1893456000,
                "role_id": "space_operator",
                "related_resource_type_id": "space",
                "resources": [{"type": "space", "id": "2"}],
            }
        ],
    }
    return provider, client, data


def run_task(data, retries=0):
    grant_v4_creator_action.push_request(retries=retries)
    try:
        return grant_v4_creator_action.run(**data)
    finally:
        grant_v4_creator_action.pop_request()


def test_retry_replays_exact_payload_expiry_and_tenant(grant):
    provider, client, data = grant
    run_task(data, retries=4)
    provider._get_client.assert_called_once_with("tenant-a")
    client.add_authorization.assert_called_once_with(items=data["payload"], operator="alice")
    assert data["payload"][0]["expired_at"] == 1893456000


def test_historical_v4_task_is_suppressed_after_switch_to_v3(grant, monkeypatch):
    provider, client, data = grant
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v3")
    with patch.object(grant_v4_creator_action, "retry") as retry:
        run_task(data, retries=4)
    provider._get_client.assert_not_called()
    client.add_authorization.assert_not_called()
    retry.assert_not_called()


def test_union_retry_keeps_frozen_request(grant, monkeypatch):
    _, client, data = grant
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "union")
    run_task(data)
    client.add_authorization.assert_called_once_with(items=data["payload"], operator="alice")


def test_commit_callback_does_not_dispatch_after_switch_to_v3(grant, monkeypatch):
    from bkmonitor.iam.tasks.grant import dispatch_v4_creator_grant

    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v3")
    with patch.object(grant_v4_creator_action, "apply_async") as dispatch:
        dispatch_v4_creator_grant(grant[2])
    dispatch.assert_not_called()


@pytest.mark.parametrize("eager", [False, True])
def test_grant_dispatch_is_broker_queued_even_for_eager_api(grant, eager):
    from bkmonitor.iam.tasks.grant import dispatch_v4_creator_grant

    app = grant_v4_creator_action.app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = eager
    try:
        with patch.object(app, "send_task") as send, patch.object(grant_v4_creator_action, "run") as run:
            dispatch_v4_creator_grant(grant[2])
        send.assert_called_once()
        assert send.call_args.args[0] == grant_v4_creator_action.name
        sent_kwargs = send.call_args.kwargs["kwargs"] if eager else send.call_args.args[2]
        assert sent_kwargs == grant[2]
        assert send.call_args.kwargs["queue"] == "celery_cron"
        run.assert_not_called()
        assert app.conf.task_always_eager is eager
    finally:
        app.conf.task_always_eager = previous


def test_eager_api_retry_preserves_delay_and_frozen_payload(grant):
    app = grant_v4_creator_action.app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = True
    try:
        with patch.object(app, "send_task") as send:
            grant_v4_creator_action.apply_async(kwargs=grant[2], countdown=60)
        assert send.call_args.kwargs["countdown"] == 60
        assert send.call_args.kwargs["kwargs"] is grant[2]
        assert send.call_args.kwargs["queue"] == "celery_cron"
    finally:
        app.conf.task_always_eager = previous


def test_worker_real_retry_requeues_with_backoff_and_frozen_request(grant):
    _, client, data = grant
    client.add_authorization.side_effect = ProviderUnavailable("offline timeout")
    app = grant_v4_creator_action.app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = False
    grant_v4_creator_action.push_request(
        id="offline-grant", retries=1, called_directly=False, is_eager=False, args=(), kwargs=data, delivery_info={}
    )
    try:
        with patch.object(app, "send_task") as send:
            with pytest.raises(Retry):
                grant_v4_creator_action.run(**data)
        assert send.call_args.args[2] == data
        assert send.call_args.kwargs["countdown"] == 60
        assert send.call_args.kwargs["retries"] == 2
        assert send.call_args.kwargs["queue"] == "celery_cron"
        assert client.add_authorization.call_count == 1
    finally:
        grant_v4_creator_action.pop_request()
        app.conf.task_always_eager = previous


def test_transient_failure_retries_with_backoff(grant):
    _, client, data = grant
    client.add_authorization.side_effect = ProviderUnavailable("offline timeout")
    with patch.object(grant_v4_creator_action, "retry", side_effect=Retry()) as retry:
        with pytest.raises(Retry):
            run_task(data, retries=1)
    assert retry.call_args.kwargs["countdown"] == 60


@pytest.mark.parametrize("error,retries", [(ProviderError("invalid request"), 0), (ProviderUnavailable("offline"), 2)])
@override_settings(BK_IAM_GRANT_MAX_ATTEMPTS=3)
def test_final_and_exhausted_failure_stop_and_log_without_newline(grant, error, retries, caplog):
    _, client, data = grant
    client.add_authorization.side_effect = error
    with patch.object(grant_v4_creator_action, "retry") as retry:
        run_task(data, retries)
    retry.assert_not_called()
    assert any("final failure" in record.getMessage() for record in caplog.records)
    assert all("\n" not in record.getMessage() for record in caplog.records)
