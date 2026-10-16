from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.db import transaction

from iam_engine.exceptions import CreatorGrantFailed, ProviderUnavailable
from tests.iam.helpers import grant_creator_actions
from bkmonitor.iam.backends.config import build_provider


@pytest.fixture
def offline_django(django_db_blocker):
    if not settings.configured:
        settings.configure(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
            SECRET_KEY="offline-only",
            USE_TZ=True,
            INSTALLED_APPS=[],
        )
        import django

        django.setup()
    assert settings.DATABASES["default"]["NAME"] == ":memory:"
    with django_db_blocker.unblock():
        yield


@pytest.fixture
def providers(offline_django, monkeypatch):
    schema = SimpleNamespace(actions={}, resource_types={}, roles={})
    options = {
        "base_url": "https://example.test/",
        "bk_tenant_id": "system",
        "credentials": {"app_code": "offline", "app_secret": "offline"},
        "system": {"id": "bk_monitorv3", "name": "Monitor", "provider_config": {"host": "https://example.test/"}},
    }
    legacy, current = (
        build_provider("v3", schema=schema, options=options),
        build_provider("v4", schema=schema),
    )
    legacy._get_client, current._get_client = Mock(), Mock()
    legacy._get_client.return_value.grant_resource_creator_actions.return_value = (True, "success")
    dispatch = Mock()
    monkeypatch.setattr(transaction, "on_commit", dispatch)
    return legacy, current, dispatch


def test_real_providers_both_grant_before_commit(providers, monkeypatch):
    legacy, current, dispatch = providers
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr("bkmonitor.iam.backends.v4.writer.timezone.now", lambda: fixed)
    with transaction.atomic():
        result = grant_creator_actions([legacy, current], "space", "-1", "user", tenant_id="tenant-b")
        assert result.is_success
        legacy._get_client.return_value.grant_resource_creator_actions.assert_called_once()
        current._get_client.return_value.add_authorization.assert_called_once()
        payload = current._get_client.return_value.add_authorization.call_args.kwargs["items"]
        assert payload[0]["expired_at"] - int(fixed.timestamp()) == 365 * 86400
        assert payload[0]["resources"] == [{"type": "space", "id": "space|-1"}]
        assert payload[0]["subject"] == {"type": "user", "id": "user"}
        current._get_client.assert_called_with("tenant-b")
        dispatch.assert_not_called()


@pytest.mark.parametrize("role", ["web", "api", "worker"])
@pytest.mark.parametrize("mode", ["v4", "union"])
def test_v4_failure_is_single_attempt_without_commit_callback(providers, settings, role, mode):
    legacy, current, on_commit = providers
    settings.ROLE = role
    selected = [current] if mode == "v4" else [legacy, current]
    current._get_client.return_value.add_authorization.side_effect = ProviderUnavailable("offline timeout")
    result = grant_creator_actions(selected, "space", "-1", "user", tenant_id="tenant-b")
    assert result.is_success is False
    assert not result.failed[0].retry_scheduled
    assert result.failed[0].error_type == "ProviderUnavailable"
    current._get_client.return_value.add_authorization.assert_called_once()
    assert legacy._get_client.return_value.grant_resource_creator_actions.call_count == (mode == "union")
    on_commit.assert_not_called()


@pytest.mark.parametrize("role", ["web", "api", "worker"])
def test_explicit_strict_v4_failure_raises_without_retry(providers, settings, role):
    from bkmonitor.iam.permission import Permission
    from iam import Resource
    from iam_engine.core.config import AuthMode

    settings.ROLE = role
    _, current, on_commit = providers
    current._get_client.return_value.add_authorization.side_effect = ProviderUnavailable("offline timeout")
    permission = Permission(username="alice", bk_tenant_id="system")
    permission._providers = {"v4": current}
    permission.mode_provider = SimpleNamespace(get_mode=lambda: AuthMode.V4)
    with pytest.raises(CreatorGrantFailed):
        permission.grant_creator_action(Resource("bk_monitorv3", "space", "2", {}), raise_exception=True)
    current._get_client.return_value.add_authorization.assert_called_once()
    on_commit.assert_not_called()


def test_api_default_v3_failure_keeps_existing_non_strict_contract(providers, settings):
    settings.ROLE = "api"
    legacy, current, on_commit = providers
    legacy._get_client.return_value.grant_resource_creator_actions.return_value = (False, "denied")
    result = grant_creator_actions([legacy], "space", "-1", "user", tenant_id="tenant-b")
    assert result.failed[0].provider_name == "v3"
    assert not result.failed[0].retry_scheduled
    legacy._get_client.return_value.grant_resource_creator_actions.assert_called_once()
    current._get_client.assert_not_called()
    on_commit.assert_not_called()


def test_v3_false_response_is_failed_but_does_not_block_v4(providers):
    legacy, current, dispatch = providers
    legacy._get_client.return_value.grant_resource_creator_actions.return_value = (False, "denied")
    result = grant_creator_actions([legacy, current], "space", "-1", "user", tenant_id="tenant-b")
    assert result.is_partial_failure
    assert result.failed[0].provider_name == "v3"
    current._get_client.return_value.add_authorization.assert_called_once()
    dispatch.assert_not_called()


@pytest.mark.parametrize("mode", ["v3", "v4", "union"])
def test_mode_selects_actual_write_targets(providers, mode):
    from types import SimpleNamespace
    from iam_engine.core.config import AuthMode
    from bkmonitor.iam.permission import Permission
    from iam import Resource

    legacy, current, _ = providers
    permission = Permission(username="alice", bk_tenant_id="tenant-a")
    permission._providers = {"v3": legacy, "v4": current}
    permission.mode_provider = SimpleNamespace(get_mode=lambda *args: AuthMode(mode))
    result = permission.grant_creator_action(
        Resource("bk_monitorv3", "space", "2", {}), creator="alice", raise_exception=True
    )
    assert result is not None
    assert legacy._get_client.return_value.grant_resource_creator_actions.call_count == (mode != "v4")
    assert current._get_client.return_value.add_authorization.call_count == (mode != "v3")
