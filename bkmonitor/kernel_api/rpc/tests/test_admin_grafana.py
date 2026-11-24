import json

import pytest
from django.db import connections, router
from django.db.utils import ConnectionHandler
from django.utils import timezone

from bk_dataview.models import Dashboard, DashboardVersion, Org
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import grafana
from metadata.models import Space


@pytest.fixture
def target(django_db_blocker, monkeypatch):
    # Grafana 自行建表；用独立的内存库覆盖仪表盘与历史版本的真实 ORM 查询。
    local = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})["default"]
    for model in (Space, Dashboard):
        for alias in {router.db_for_read(model), router.db_for_write(model)}:
            monkeypatch.setattr(connections._connections, alias, local, raising=False)
    with django_db_blocker.unblock():
        try:
            with local.schema_editor() as editor:
                for model in (Space, Org, Dashboard, DashboardVersion):
                    editor.create_model(model)
            Space.objects.bulk_create(
                [Space(space_type_id="bkcc", space_id="2", bk_tenant_id="tenant", space_name="test")]
            )
            org = Org.objects.create(name="2")
            other = Org.objects.create(name="3")
            for pk, org_id, folder in ((10, org.id, 0), (11, org.id, 1), (12, other.id, 0)):
                Dashboard.objects.create(
                    id=pk,
                    title="CPU",
                    uid=f"host-{pk}",
                    version=4,
                    org_id=org_id,
                    is_folder=folder,
                    data=json.dumps({"refresh": "30s", "token": "hidden"}),
                )
            for version in (1, 3):
                DashboardVersion.objects.create(
                    dashboard_id=10,
                    version=version,
                    created=timezone.now(),
                    created_by=7,
                    message="保存",
                    data=json.dumps({"refresh": "1m", "token": "old"}),
                )
            yield {"bk_tenant_id": "tenant", "bk_biz_id": 2, "dashboard_id": 10}
        finally:
            local.close()


def test_scoped_list_history_and_config(target):
    result = grafana.list_dashboards({**target, "keyword": "host-"})["data"]
    assert [row["id"] for row in result["items"]] == [10]
    assert "data" not in result["items"][0]
    history = grafana.list_versions({**target, "page": 2, "page_size": 1})["data"]
    assert history["total"] == 2
    assert [row["version"] for row in history["items"]] == [1]
    assert "data" not in history["items"][0]
    for params, number, refresh in ((target, 4, "30s"), ({**target, "version": 3}, 3, "1m")):
        data = grafana.get_config(params)["data"]
        assert data["version"] == number
        assert data["config"] == {"refresh": refresh, "token": "[REDACTED]"}
        assert data["redacted_paths"] == ["/token"]


@pytest.mark.parametrize(
    "overrides", [{"bk_tenant_id": "other"}, {"dashboard_id": 12}, {"dashboard_id": 11}, {"version": 2}]
)
def test_unavailable_target_never_falls_back_to_current(target, overrides):
    with pytest.raises(CustomException):
        grafana.get_config({**target, **overrides})


def test_user_query_filters_dashboard_before_history_and_count(target, monkeypatch):
    from unittest.mock import Mock
    from bk_dataview.permissions import GrafanaRole
    from bkmonitor.iam import ActionEnum
    from kernel_api.rpc.functions.admin import user_query
    from monitor_web.grafana.permissions import DashboardPermission

    user = Mock(username="u", bk_tenant_id=target["bk_tenant_id"])
    user.is_allowed_by_biz.side_effect = lambda biz, action: action == ActionEnum.VIEW_BUSINESS
    monkeypatch.setattr(user_query, "Permission", lambda **kw: user)
    acl = Mock(return_value=(GrafanaRole.Anonymous, {}))
    monkeypatch.setattr(DashboardPermission, "get_visible_dashboards", acl)
    params = {"bk_tenant_id": target["bk_tenant_id"], "username": "u", "space_uid": "bkcc__2"}

    def call(op, query):
        return user_query.user_query({**params, "operation": "grafana." + op, "query": query})["data"]

    assert call("list", {})["result"]["total"] == 0
    for op in ["config", "version_list"]:
        assert not call(op, {"dashboard_id": 10})["allowed"]
    acl.return_value = (GrafanaRole.Anonymous, {"host-10": 1})
    assert call("list", {})["result"]["total"] == 1
    assert call("version_list", {"dashboard_id": 10})["result"]["total"] == 2
    assert call("config", {"dashboard_id": 10, "version": 1})["result"]["version"] == 1
    assert not call("config", {"dashboard_id": 12})["allowed"]
    acl.assert_called_with("u", "2", force_check=True, bk_tenant_id=target["bk_tenant_id"])


def test_tenant_list_returns_business_and_excludes_foreign_orgs(target):
    p = {"bk_tenant_id": target["bk_tenant_id"], "page_size": 1}
    rows = grafana.list_dashboards(p)["data"]
    assert rows["total"] == 1 and rows["items"][0]["bk_biz_id"] == 2
    Space.objects.bulk_create(
        [Space(space_type_id="bkcc", space_id="3", bk_tenant_id=p["bk_tenant_id"], space_name="second")]
    )
    page = grafana.list_dashboards({**p, "page": 2})["data"]
    assert page["total"] == 2 and len(page["items"]) == 1
    assert grafana.list_dashboards({"bk_tenant_id": "other"})["data"]["total"] == 0
