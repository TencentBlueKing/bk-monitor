"""Execute the actual Celery task locally, never dispatch to a broker."""

from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry
from django.test import override_settings

from bkmonitor.iam.adapters.grant_tasks import grant_v4_creator_action
from iam_engine.exceptions import ProviderError, ProviderUnavailable


@pytest.fixture
def grant(monkeypatch):
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
    client.add_authorization.assert_called_once_with(data["payload"], operator="alice")
    assert data["payload"][0]["expired_at"] == 1893456000


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
