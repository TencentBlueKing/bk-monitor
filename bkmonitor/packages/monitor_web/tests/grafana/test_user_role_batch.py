from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bk_dataview.permissions import GrafanaRole
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.permission import Permission
from iam_engine.core.config import AuthMode
from monitor_web.grafana import permissions as grafana

ROLE_ACTIONS = (ActionEnum.MANAGE_DATASOURCE.id, ActionEnum.MANAGE_DASHBOARD.id, ActionEnum.VIEW_DASHBOARD.id)


def build_permission(monkeypatch, mode=AuthMode.V3, client=None, request=None):
    permission = Permission(username="alice", bk_tenant_id="system")
    provider = build_provider("v3", "system", username="alice")
    provider.client_factory = lambda tenant_id: client
    permission._providers = {"v3": provider}
    permission.skip_check = False
    permission.request = request
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    monkeypatch.setattr(grafana, "Permission", lambda **kwargs: permission)
    monkeypatch.setattr(grafana, "get_request_tenant_id", lambda: "system")
    return permission


def v3_client(granted=(), batch_error=None):
    client = Mock()
    client.make_resource = lambda rt, rid, **kwargs: SimpleNamespace(id=rid)
    if batch_error:
        client.batch_resource_multi_actions_allowed.side_effect = batch_error
    else:
        client.batch_resource_multi_actions_allowed.return_value = {
            "2": {action_id: action_id in granted for action_id in ROLE_ACTIONS}
        }
    return client


@pytest.mark.parametrize(
    "granted,expected",
    [
        (ROLE_ACTIONS, GrafanaRole.Admin),
        (ROLE_ACTIONS[1:], GrafanaRole.Editor),
        (ROLE_ACTIONS[2:], GrafanaRole.Viewer),
        ((), GrafanaRole.Anonymous),
    ],
)
def test_v3_resolves_role_with_one_policy_query(monkeypatch, granted, expected):
    client = v3_client(granted)
    build_permission(monkeypatch, client=client)

    assert grafana.DashboardPermission.get_user_role("alice", "2") == expected
    client.batch_resource_multi_actions_allowed.assert_called_once()
    client.is_allowed.assert_not_called()
    client.is_allowed_with_cache.assert_not_called()


def test_v3_batch_error_falls_back_to_per_action_checks(monkeypatch):
    client = v3_client(batch_error=RuntimeError("iam unavailable"))
    client.is_allowed.return_value = False
    client.is_allowed_with_cache.return_value = True
    build_permission(monkeypatch, client=client)

    assert grafana.DashboardPermission.get_user_role("alice", "2") == GrafanaRole.Viewer
    assert client.is_allowed.call_count == 2
    client.is_allowed_with_cache.assert_called_once()


@pytest.mark.parametrize(
    "mode,request_",
    [
        (AuthMode.V4, None),
        (AuthMode.UNION, None),
        (AuthMode.V3, SimpleNamespace(token="share-token")),
    ],
)
def test_short_circuit_checks_kept_outside_plain_v3(monkeypatch, mode, request_):
    permission = build_permission(monkeypatch, mode=mode, request=request_)
    permission.batch_is_allowed = Mock()
    permission.is_allowed_by_biz = Mock(return_value=True)

    assert grafana.DashboardPermission.get_user_role("alice", "2") == GrafanaRole.Admin
    permission.batch_is_allowed.assert_not_called()
    permission.is_allowed_by_biz.assert_called_once_with(2, ActionEnum.MANAGE_DATASOURCE)
