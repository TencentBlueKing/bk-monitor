"""Real Grafana permission entrypoints, with DB/API boundaries mocked."""

from types import SimpleNamespace
from unittest.mock import Mock

from bk_dataview import api
from bk_dataview.permissions import GrafanaPermission, GrafanaRole
from monitor_web.grafana import permissions as grafana


def test_proxy_collects_org_candidates_and_expands_folder_permissions(monkeypatch):
    monkeypatch.setattr(grafana, "get_or_create_org", lambda name: {"id": 10})
    monkeypatch.setattr(grafana, "get_request_tenant_id", lambda: "tenant-a")
    monkeypatch.setattr(grafana, "Permission", Mock(return_value=SimpleNamespace(skip_check=False)))
    monkeypatch.setattr(grafana.DashboardPermission, "get_user_role", lambda *args: GrafanaRole.Anonymous)
    manager = Mock()

    def candidates(**kwargs):
        if "folder_id__in" in kwargs:
            assert kwargs == {"org_id": 10, "folder_id__in": {7}, "is_folder": False}
            return Mock(values_list=Mock(return_value=["dash-b"]))
        assert kwargs == {"org_id": 10}
        return Mock(values_list=Mock(return_value=[(1, "dash-a", False), (7, "folder", True)]))

    manager.filter.side_effect = candidates
    monkeypatch.setattr(grafana.Dashboard, "objects", manager)
    framework = Mock()
    framework.filter_visible_resources.side_effect = [
        SimpleNamespace(all_granted=False, visible_ids=["10|dash-a"]),
        SimpleNamespace(all_granted=False, visible_ids=["folder:10|7"]),
    ]
    monkeypatch.setattr(grafana, "get_framework", lambda: framework)
    request = SimpleNamespace(user=SimpleNamespace(username="alice", is_superuser=False))
    allowed, role, acl = grafana.DashboardPermission.has_permission(request, None, "2", force_check=True)
    assert allowed
    assert role == GrafanaRole.Anonymous
    assert acl == {"dash-a": GrafanaPermission.View, "dash-b": GrafanaPermission.Edit}
    for call in framework.filter_visible_resources.call_args_list:
        subject, _, resources = call.args
        assert subject.tenant_id == "tenant-a"
        assert {resource.id for resource in resources} == {"10|dash-a", "folder:10|7"}
        assert all(resource.ancestor_chain[0].id == "2" for resource in resources)


def test_empty_desired_acl_revokes_only_existing_managed_role(monkeypatch):
    roles, permissions, dashboards = Mock(), Mock(), Mock()
    roles.filter.return_value.first.return_value = SimpleNamespace(id=99)
    dashboards.filter.return_value.values_list.return_value = ["dash-a"]
    monkeypatch.setattr(api.Role, "objects", roles)
    monkeypatch.setattr(api.Permission, "objects", permissions)
    monkeypatch.setattr(api.Dashboard, "objects", dashboards)
    monkeypatch.setattr(api, "_get_user_dashboard_actions", Mock(return_value=({"dash-a": ["dashboards:read"]}, False)))
    api.sync_dashboard_permission(10, 42, GrafanaRole.Anonymous, {})
    permissions.filter.return_value.delete.assert_called_once_with()
    assert dict(permissions.filter.call_args.args[0].children) == {
        "role_id": 99,
        "action": "dashboards:read",
        "scope": "dashboards:uid:dash-a",
    }
    roles.create.assert_not_called()
    permissions.bulk_create.assert_not_called()


def test_empty_desired_acl_without_managed_role_does_not_create_one(monkeypatch):
    roles = Mock()
    roles.filter.return_value.first.return_value = None
    monkeypatch.setattr(api.Role, "objects", roles)
    current_acl = Mock()
    monkeypatch.setattr(api, "_get_user_dashboard_actions", current_acl)
    api.sync_dashboard_permission(10, 42, GrafanaRole.Anonymous, {})
    roles.create.assert_not_called()
    current_acl.assert_not_called()
