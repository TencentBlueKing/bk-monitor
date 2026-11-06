"""Real Grafana permission entrypoints, with DB/API boundaries mocked."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bk_dataview import api
from bk_dataview.permissions import GrafanaPermission, GrafanaRole
from monitor_web.grafana import permissions as grafana


@pytest.mark.parametrize("mode", ["v3", "v4", "union"])
def test_product_contract_expands_folder_for_dashboard_only_candidates(monkeypatch, mode):
    from bkmonitor.iam.permission import Permission
    from bkmonitor.iam.backends.v3.provider import V3PermissionProvider
    from iam_engine.core.config import AuthMode
    from iam_engine.provider.requests import VisibleResult

    monkeypatch.setattr(grafana, "get_or_create_org", lambda name: {"id": 10})
    monkeypatch.setattr(grafana, "get_request_tenant_id", lambda: "tenant-a")
    monkeypatch.setattr(grafana.DashboardPermission, "get_user_role", lambda *args: GrafanaRole.Anonymous)
    manager = Mock()

    def candidates(**kwargs):
        if "uid__in" in kwargs:
            assert kwargs == {"org_id": 10, "uid__in": {"dash-b"}, "is_folder": False}
            return Mock(values_list=Mock(return_value=[7]))
        assert kwargs == {"org_id": 10, "folder_id__in": {7}, "is_folder": False}
        return Mock(values_list=Mock(return_value=["dash-b"]))

    manager.filter.side_effect = candidates
    monkeypatch.setattr(grafana.Dashboard, "objects", manager)
    permission = Permission(username="alice", bk_tenant_id="tenant-a")
    permission.skip_check = False
    permission.mode_provider = Mock(get_mode=Mock(return_value=AuthMode(mode)))
    v3 = object.__new__(V3PermissionProvider)
    v3.query_policy = Mock(return_value={"op": "eq", "field": "grafana_dashboard.id", "value": "folder:10|7"})
    v4 = Mock(name="v4-provider")
    v4.name = "v4"
    v4.filter_visible_resources.return_value = VisibleResult()
    permission._providers = {"v3": v3, "v4": v4}
    monkeypatch.setattr(grafana, "Permission", Mock(return_value=permission))

    allowed, role, acl = grafana.DashboardPermission.get_user_permission("alice", "2", dashboard_uids=["dash-b"])
    assert allowed is True
    assert role == GrafanaRole.Anonymous
    assert acl == ({} if mode == "v4" else {"dash-b": GrafanaPermission.Edit})
    assert v3.query_policy.call_count == (0 if mode == "v4" else 2)
    assert v4.filter_visible_resources.call_count == (0 if mode == "v3" else 2)


def test_external_authorization_validator_uses_stable_three_value_contract(monkeypatch):
    from monitor_web.iam import resources

    check = Mock(return_value=(True, GrafanaRole.Editor, {}))
    monkeypatch.setattr(resources.DashboardPermission, "get_user_permission", check)
    serializer = resources.CreateOrUpdateExternalPermission.RequestSerializer()
    result = serializer.validate({"authorizer": "alice", "bk_biz_id": 2, "action_id": "manage_grafana"})
    assert result == {"bk_biz_id": 2, "action_id": "manage_grafana"}
    check.assert_called_once_with("alice", "2")


def test_external_authorization_list_uses_stable_three_value_contract(monkeypatch):
    from monitor_web.iam import resources

    config = Mock()
    config.get_or_create.return_value = (SimpleNamespace(value={"2": "alice"}), False)
    monkeypatch.setattr(resources.GlobalConfig, "objects", config)
    monkeypatch.setattr(resources.SpaceApi, "list_spaces_dict", lambda: [{"bk_biz_id": 2, "space_name": "biz"}])
    grant = SimpleNamespace(
        bk_biz_id=2,
        resources=["10|dash-b"],
        action_id="view_grafana",
        authorized_user="guest",
        get_status=Mock(return_value="valid"),
    )
    monkeypatch.setattr(resources.ExternalPermission, "objects", Mock(all=Mock(return_value=[grant])))
    check = Mock(return_value=(True, GrafanaRole.Viewer, {}))
    monkeypatch.setattr(resources.DashboardPermission, "get_user_permission", check)
    result = resources.GetExternalPermissionList().perform_request({"bk_biz_id": 0, "view_type": "resource"})
    assert result[0]["status"] == "valid"
    assert result[0]["authorizer"] == "alice"
    grant.get_status.assert_called_once_with(GrafanaRole.Viewer)
    check.assert_called_once_with("alice", "2")


def test_favorite_consumer_keeps_request_aware_permission_entrypoint(monkeypatch):
    from monitor_web.overview import resources

    request = SimpleNamespace(user=SimpleNamespace(username="alice"))
    monkeypatch.setattr(resources, "get_request", lambda **kwargs: request)
    users, stars, dashboards, orgs = Mock(), Mock(), Mock(), Mock()
    users.filter.return_value.first.return_value = SimpleNamespace(id=42)
    stars.filter.return_value.values_list.return_value = [1]
    dashboards.filter.return_value.only.return_value = [
        SimpleNamespace(id=1, org_id=10, uid="dash-b", title="dashboard", slug="dashboard")
    ]
    orgs.filter.return_value = [SimpleNamespace(id=10, name="2")]
    for model, manager in (
        (resources.User, users),
        (resources.Star, stars),
        (resources.Dashboard, dashboards),
        (resources.Org, orgs),
    ):
        monkeypatch.setattr(model, "objects", manager)
    check = Mock(return_value=(True, GrafanaRole.Anonymous, {"dash-b": GrafanaPermission.View}))
    monkeypatch.setattr(resources.DashboardPermission, "has_permission", check)

    result = resources.GetFunctionShortcutResource.get_favorite_shortcuts("alice", ["dashboard"])

    assert result[0]["items"][0]["dashboard_uid"] == "dash-b"
    check.assert_called_once_with(request, None, 2)


@pytest.mark.parametrize("external_user", [False, "guest"])
def test_directory_tree_keeps_product_permission_entrypoint(monkeypatch, external_user):
    from monitor_web.grafana.resources import manage

    request = SimpleNamespace(user=SimpleNamespace(username="alice"), external_user=external_user)
    monkeypatch.setattr(manage, "get_request", lambda **kwargs: request)
    monkeypatch.setattr(manage, "get_or_create_org", lambda name: {"id": 10})
    search = Mock(return_value={"data": [{"type": "dash-db", "uid": "dash-b", "folderId": 0}]})
    monkeypatch.setattr(manage, "api", SimpleNamespace(grafana=SimpleNamespace(search_folder_or_dashboard=search)))
    check = Mock(return_value=(True, GrafanaRole.Anonymous, {"dash-b": GrafanaPermission.View}))
    monkeypatch.setattr(manage.DashboardPermission, "has_permission", check)
    monkeypatch.setattr(
        manage.DashboardPermission,
        "get_user_permission",
        Mock(side_effect=AssertionError("the consumer must not bypass the request-aware product entrypoint")),
    )

    result = manage.GetDirectoryTree().perform_request({"bk_biz_id": 2, "filter_no_permission": True})

    check.assert_called_once_with(request, None, 2, force_check=True)
    search.assert_called_once_with(org_id=10)
    assert result[0]["dashboards"][0]["uid"] == "dash-b"
    assert result[0]["dashboards"][0]["has_permission"] is True
    assert result[0]["dashboards"][0]["editable"] is False


def test_proxy_query_failure_never_enters_acl_write(monkeypatch):
    from bk_dataview import views
    from iam_engine.exceptions import ProviderUnavailable

    permission = Mock()
    permission.has_permission.side_effect = ProviderUnavailable("IAM query unavailable")
    view = views.ProxyBaseView()
    view.permission_classes = [lambda: permission]
    view.org = {"id": 10, "name": "2"}
    view.user = {"id": 42}
    role_write, acl_write = Mock(), Mock()
    monkeypatch.setattr(views, "sync_user_role", role_write)
    monkeypatch.setattr(views, "sync_dashboard_permission", acl_write)
    with pytest.raises(ProviderUnavailable):
        view.sync_permissions(SimpleNamespace())
    role_write.assert_not_called()
    acl_write.assert_not_called()


def test_acl_delete_failure_is_visible_and_retry_recomputes_same_target(monkeypatch):
    roles, permissions, dashboards = Mock(), Mock(), Mock()
    roles.filter.return_value.first.return_value = SimpleNamespace(id=99)
    dashboards.filter.return_value.values_list.return_value = ["dash-a"]
    monkeypatch.setattr(api.Role, "objects", roles)
    monkeypatch.setattr(api.Permission, "objects", permissions)
    monkeypatch.setattr(api.Dashboard, "objects", dashboards)
    monkeypatch.setattr(api, "_get_user_dashboard_actions", Mock(return_value=({"dash-a": ["dashboards:read"]}, False)))
    permissions.filter.return_value.delete.side_effect = [RuntimeError("write failed"), None]
    desired = {"dash-b": GrafanaPermission.View}
    dashboards.filter.return_value.values_list.return_value = ["dash-a", "dash-b"]
    with pytest.raises(RuntimeError, match="write failed"):
        api.sync_dashboard_permission(10, 42, GrafanaRole.Anonymous, desired)
    api.sync_dashboard_permission(10, 42, GrafanaRole.Anonymous, desired)
    assert permissions.filter.call_args_list[0] == permissions.filter.call_args_list[1]
    assert permissions.filter.return_value.delete.call_count == 2


def test_proxy_collects_org_candidates_and_expands_folder_permissions(monkeypatch):
    monkeypatch.setattr(grafana, "get_or_create_org", lambda name: {"id": 10})
    monkeypatch.setattr(grafana, "get_request_tenant_id", lambda: "tenant-a")
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
    framework.filter_visible_resource_ids.side_effect = [
        SimpleNamespace(all_granted=False, visible_ids=["10|dash-a"]),
        SimpleNamespace(all_granted=False, visible_ids=["folder:10|7"]),
    ]
    framework.skip_check = False
    monkeypatch.setattr(grafana, "Permission", Mock(return_value=framework))
    request = SimpleNamespace(user=SimpleNamespace(username="alice", is_superuser=False))
    allowed, role, acl = grafana.DashboardPermission.has_permission(request, None, "2", force_check=True)
    assert allowed
    assert role == GrafanaRole.Anonymous
    assert acl == {"dash-a": GrafanaPermission.View, "dash-b": GrafanaPermission.Edit}
    for call in framework.filter_visible_resource_ids.call_args_list:
        _, resource_type, resource_ids = call.args
        assert resource_type == "grafana_dashboard"
        assert set(resource_ids) == {"10|dash-a", "folder:10|7"}
        assert call.kwargs == {"bk_biz_id": 2}


def test_empty_desired_acl_keeps_v3_noop_behavior(monkeypatch):
    roles, permissions, dashboards = Mock(), Mock(), Mock()
    roles.filter.return_value.first.return_value = SimpleNamespace(id=99)
    dashboards.filter.return_value.values_list.return_value = ["dash-a"]
    monkeypatch.setattr(api.Role, "objects", roles)
    monkeypatch.setattr(api.Permission, "objects", permissions)
    monkeypatch.setattr(api.Dashboard, "objects", dashboards)
    monkeypatch.setattr(api, "_get_user_dashboard_actions", Mock(return_value=({"dash-a": ["dashboards:read"]}, False)))
    api.sync_dashboard_permission(10, 42, GrafanaRole.Anonymous, {})
    roles.filter.assert_not_called()
    permissions.filter.assert_not_called()
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
