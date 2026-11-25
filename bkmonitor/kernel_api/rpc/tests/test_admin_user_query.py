from unittest.mock import Mock

import pytest
from django.db import connections, router
from django.db.utils import ConnectionHandler

from apm.models import ApmApplication
from bkmonitor.iam import ActionEnum
from core.drf_resource.exceptions import CustomException
from iam_engine.provider.requests import VisibleResult
from kernel_api.rpc.functions.admin import user_query as endpoint
from metadata.models import Space
from rum.models import RumApplication


@pytest.fixture
def user_data(monkeypatch, django_db_blocker):
    local = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})["default"]
    models = (Space, ApmApplication, RumApplication)
    for alias in {"default", *(router.db_for_read(m) for m in models), *(router.db_for_write(m) for m in models)}:
        monkeypatch.setattr(connections._connections, alias, local, raising=False)
    with django_db_blocker.unblock():
        try:
            with local.schema_editor() as editor:
                for model in models:
                    editor.create_model(model)
            for pk, tenant, kind, key in [
                (1, "ops", "bkcc", "2"),
                (12, "ops", "bkci", "project"),
                (13, "other", "bkcc", "3"),
            ]:
                Space.objects.bulk_create(
                    [Space(id=pk, bk_tenant_id=tenant, space_type_id=kind, space_id=key, space_name=key)]
                )
            for model in (ApmApplication, RumApplication):
                model.objects.bulk_create(
                    [
                        model(id=i, app_name=f"app{i}", app_alias="应用", bk_tenant_id="ops", bk_biz_id=biz)
                        for i, biz in [(1, -12), (2, -12), (3, 2)]
                    ]
                )
            permission = Mock(bk_tenant_id="ops", username="alice")
            permission.is_allowed_by_biz.return_value = True
            permission.filter_visible_resource_ids.side_effect = lambda action, resource_type, ids, *, bk_biz_id: (
                VisibleResult(visible_ids=tuple(str(i) for i in ids if i == 2))
            )
            constructor = Mock(return_value=permission)
            monkeypatch.setattr(endpoint, "Permission", constructor)
            yield permission, constructor
        finally:
            local.close()


def call(name, query, **scope):
    return endpoint.user_query(
        {"username": "alice", "bk_tenant_id": "ops", "operation": name, "query": query, **scope}
    )["data"]


@pytest.mark.parametrize("name,key", [("apm.application_list", "application_id"), ("rum.application_list", "id")])
def test_application_visibility_precedes_count_and_page(user_data, name, key):
    permission, ctor = user_data
    data = call(name, {"page_size": 1}, space_uid="bkci__project")
    assert data["allowed"] and data["result"]["total"] == 1
    row = data["result"]["items"][0]
    assert row[key] == 2 and row["bk_biz_id"] == -12
    assert "token" not in row and "apm_token" not in row
    assert call(name, {"page": 2, "page_size": 1}, bk_biz_id=-12)["result"]["items"] == []
    ctor.assert_called_with(username="alice", bk_tenant_id="ops")
    assert permission.skip_check is False


def test_instance_and_tenant_boundaries(user_data):
    p, _ = user_data
    assert (
        call("apm.application_detail", {"application_id": 2}, bk_biz_id=-12)["result"]["application"]["app_name"]
        == "app2"
    )
    for op, query in [
        ("apm.service_list", {"application_id": 1}),
        ("apm.topo", {"application_id": 3}),
        ("rum.config_list", {"app_name": "app1"}),
        ("rum.datasource_list", {"app_name": "app3"}),
    ]:
        assert call(op, query, bk_biz_id=-12) == {"allowed": False, "result": None}
    p.filter_visible_resource_ids.reset_mock()
    for scope in [{"bk_biz_id": 3}, {"bk_biz_id": 2, "space_uid": "bkci__project"}]:
        assert not call("apm.application_detail", {"application_id": 2}, **scope)["allowed"]
    p.filter_visible_resource_ids.assert_not_called()
    with pytest.raises(CustomException):
        call("apm.application_detail", {"application_id": 2})
    with pytest.raises(CustomException):
        call("record_rule_v4.apply", {"id": 1}, bk_biz_id=2)
    with pytest.raises(CustomException):
        call("custom_report.list", {"bk_biz_ids": [2]}, bk_biz_id=-12)


@pytest.mark.parametrize(
    "name,query,action",
    [
        ("alarm_strategy.detail", {"strategy_id": 4}, ActionEnum.VIEW_RULE),
        ("alarm_config.user_group_detail", {"id": 4}, ActionEnum.VIEW_NOTIFY_TEAM),
        ("alarm_config.assignment_detail", {"id": 4}, ActionEnum.VIEW_RULE),
        ("alarm_config.shield_detail", {"id": 4}, ActionEnum.VIEW_DOWNTIME),
        ("collect_plugin.version_list", {"plugin_id": "x"}, ActionEnum.VIEW_PLUGIN),
        ("collect_config.version_list", {"id": 1}, ActionEnum.VIEW_COLLECTION),
        ("record_rule_v4.config", {"id": 1}, ActionEnum.VIEW_RECORDING_RULE),
        ("custom_report.detail", {"report_type": "custom_event", "group_id": 1}, ActionEnum.VIEW_CUSTOM_EVENT),
        ("custom_report.metric_list", {"group_id": 1}, ActionEnum.VIEW_CUSTOM_METRIC),
        ("uptime_check.task_detail", {"task_id": 1}, ActionEnum.VIEW_SYNTHETIC),
    ],
)
def test_permission_denial_precedes_config_access(user_data, monkeypatch, name, query, action):
    p, _ = user_data
    p.is_allowed_by_biz.return_value = False
    dispatch = Mock(side_effect=AssertionError("未授权不应读取资源"))
    monkeypatch.setattr(endpoint.KernelRPCRegistry, "execute", dispatch)
    assert not call(name, query, bk_biz_id=2)["allowed"]
    p.is_allowed_by_biz.assert_called_with(2, action)
    dispatch.assert_not_called()
