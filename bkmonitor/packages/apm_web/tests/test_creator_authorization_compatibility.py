"""Offline real APM caller/task regressions; no broker, IAM or product writes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from iam import Resource

from apm_web.models import application as am
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.permission import Permission
from iam_engine.core.config import AuthMode
from iam_engine.exceptions import ProviderUnavailable


@pytest.fixture
def grants(monkeypatch, settings, django_db_blocker):
    assert settings.DATABASES["default"]["NAME"] == ":memory:"
    schema = SimpleNamespace(actions={}, resource_types={}, roles={})
    legacy = build_provider(
        "v3",
        schema=schema,
        options={
            "base_url": "https://iam.example.test/",
            "bk_tenant_id": "system",
            "credentials": {"app_code": "offline", "app_secret": "offline"},
            "system": {"id": "bk_monitorv3", "name": "Monitor"},
        },
    )
    current = build_provider("v4", schema=schema)
    legacy._get_client, current._get_client = Mock(), Mock()
    legacy._get_client.return_value.grant_resource_creator_actions.return_value = (True, "success")
    permission = Permission(username="creator", bk_tenant_id="system")
    permission._providers = {"v3": legacy, "v4": current}
    monkeypatch.setattr(am, "Permission", lambda *args, **kwargs: permission)
    monkeypatch.setattr(am, "get_request_tenant_id", lambda: "system")
    monkeypatch.setattr(am.Application, "get_application_by_app_id", lambda app_id: SimpleNamespace(bk_biz_id=2))
    monkeypatch.setattr(
        am.resource.cc,
        "get_app_by_id",
        lambda biz: SimpleNamespace(maintainers=["user-a", "user-b", "user-c"]),
    )
    monkeypatch.setattr(
        am.ResourceEnum.APM_APPLICATION,
        "create_simple_instance",
        lambda app_id, attributes: Resource("bk_monitorv3", "apm_application", str(app_id), attributes),
    )
    with django_db_blocker.unblock():
        yield permission, legacy._get_client.return_value, current._get_client.return_value


def configure(grants, mode, failed_backend):
    permission, legacy, current = grants
    permission.mode_provider = SimpleNamespace(get_mode=Mock(return_value=AuthMode(mode)))
    if failed_backend == "v4":
        current.add_authorization.side_effect = ProviderUnavailable("offline V4 timeout")
    else:
        legacy.grant_resource_creator_actions.return_value = (False, "offline V3 denial")
    return permission, legacy, current


def application():
    return SimpleNamespace(
        application_id=7,
        bk_biz_id=2,
        update_user="creator",
        owners=["explicit-owner"],
        grant_owners=Mock(),
    )


@pytest.mark.parametrize("role", ["web", "api"])
@pytest.mark.parametrize("mode", ["v3", "v4", "union"])
@pytest.mark.parametrize("failed_backend", ["v3", "v4"])
def test_creator_failure_keeps_maintainer_dispatch_and_explicit_owners(
    grants, monkeypatch, settings, role, mode, failed_backend
):
    settings.ROLE = role
    permission, legacy, current = configure(grants, mode, failed_backend)
    dispatch = Mock()
    monkeypatch.setattr(am.Application.authorization_to_maintainers, "delay", dispatch)
    app = application()

    am.Application.authorization(app)

    dispatch.assert_called_once_with("creator", 7)
    app.grant_owners.assert_called_once_with(["explicit-owner"], previous_owners=[], grant_log=False)
    permission.mode_provider.get_mode.assert_called_once()
    assert legacy.grant_resource_creator_actions.call_count == (mode != "v4")
    assert current.add_authorization.call_count == (mode != "v3")


@pytest.mark.parametrize("role", ["web", "api"])
@pytest.mark.parametrize("mode", ["v3", "v4", "union"])
@pytest.mark.parametrize("failed_backend", ["v3", "v4"])
def test_maintainer_task_attempts_every_user_after_grant_failure(grants, settings, role, mode, failed_backend):
    settings.ROLE = role
    _, legacy, current = configure(grants, mode, failed_backend)

    # Real Celery task execution, including its exception/result handling; never publish.
    result = am.Application.authorization_to_maintainers.apply(args=("creator", 7), throw=False)

    assert result.successful()
    expected = ["user-a", "user-b", "user-c"]
    assert [call.args[0]["creator"] for call in legacy.grant_resource_creator_actions.call_args_list] == (
        expected if mode != "v4" else []
    )
    assert [call.kwargs["items"][0]["subject"]["id"] for call in current.add_authorization.call_args_list] == (
        expected if mode != "v3" else []
    )


@pytest.mark.parametrize("mode", ["v3", "v4", "union"])
def test_api_creator_to_eager_maintainers_chain_continues_after_v4_failure(grants, monkeypatch, settings, mode):
    settings.ROLE = "api"
    _, legacy, current = configure(grants, mode, "v4")
    task = am.Application.authorization_to_maintainers
    # Exercise the actual delay -> eager apply path used by API, without a broker.
    monkeypatch.setitem(task.app.conf, "task_always_eager", True)
    monkeypatch.setitem(task.app.conf, "task_eager_propagates", False)
    app = application()

    am.Application.authorization(app)

    expected = ["creator", "user-a", "user-b", "user-c"]
    assert [call.args[0]["creator"] for call in legacy.grant_resource_creator_actions.call_args_list] == (
        expected if mode != "v4" else []
    )
    assert [call.kwargs["items"][0]["subject"]["id"] for call in current.add_authorization.call_args_list] == (
        expected if mode != "v3" else []
    )
    app.grant_owners.assert_called_once_with(["explicit-owner"], previous_owners=[], grant_log=False)
