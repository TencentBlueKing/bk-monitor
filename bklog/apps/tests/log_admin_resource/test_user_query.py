from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import connections, router
from django.db.utils import ConnectionHandler

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers import user_query
from apps.log_search.models import Space


@pytest.fixture
def resources(monkeypatch, django_db_blocker):
    models = (Space, user_query.CollectorConfig, user_query.LogIndexSet)
    local = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})["default"]
    for alias in {"default", *(router.db_for_read(m) for m in models), *(router.db_for_write(m) for m in models)}:
        monkeypatch.setattr(connections._connections, alias, local, raising=False)
    with django_db_blocker.unblock():
        try:
            with local.schema_editor() as editor:
                for model in models:
                    editor.create_model(model)
            for biz, uid, tenant in [(-12, "bkci__project", "ops"), (2, "bkcc__2", "ops"), (3, "bkcc__3", "other")]:
                Space.origin_objects.bulk_create([Space(bk_biz_id=biz, space_uid=uid, bk_tenant_id=tenant)])
            for i, biz, uid in [(1, -12, "bkci__project"), (2, -12, "bkci__project"), (3, 2, "bkcc__2")]:
                user_query.CollectorConfig.objects.bulk_create(
                    [
                        user_query.CollectorConfig(
                            collector_config_id=i,
                            bk_biz_id=biz,
                            collector_config_name=f"collector{i}",
                            collector_scenario_id="row",
                        )
                    ]
                )
                user_query.LogIndexSet.objects.bulk_create(
                    [
                        user_query.LogIndexSet(
                            index_set_id=i, index_set_name=f"index{i}", space_uid=uid, scenario_id="log"
                        )
                    ]
                )
            monkeypatch.setattr(user_query, "require_request_tenant_id", lambda: "ops")
            monkeypatch.setattr(
                user_query, "request_tenant_spaces", lambda: Space.origin_objects.filter(bk_tenant_id="ops")
            )
            monkeypatch.setattr(
                user_query, "_evaluate_one", lambda *a, **kw: {"status": "ok", "allowed": True, "warnings": []}
            )
            permission = Mock()
            monkeypatch.setattr(user_query, "Permission", lambda **kw: permission)
            permission.make_engine_batch_request.side_effect = lambda actions, resources: (actions[0].id, resources)

            def decide(request):
                action, resources = request
                mapped = {}
                for (item,) in resources:
                    assert item.attribute["_bk_iam_path_"] == "/space,-12/"
                    assert item.id in ("1", "2")
                    mapped[item.id] = {action: item.id == "2"}
                return SimpleNamespace(items=[], as_allowed_dict=lambda: mapped)

            permission.mode_router.batch_is_allowed.side_effect = decide
            yield permission
        finally:
            local.close()


@pytest.mark.parametrize("kind,key", [("collector", "collector_config_id"), ("index_set", "index_set_id")])
def test_visible_instance_pages_and_detail(resources, kind, key):
    params = {
        "username": "alice",
        "space_uid": "bkci__project",
        "operation": f"bklog.{kind}.list",
        "query": {"page_size": 1},
    }
    data = user_query.read_user_query(params)["result"]
    assert data["total"] == 1 and data["items"][0][key] == 2
    assert user_query.read_user_query({**params, "query": {"page": 2, "page_size": 1}})["result"]["items"] == []
    for i, allowed in [(1, False), (2, True), (3, False)]:
        reply = user_query.read_user_query({**params, "operation": f"bklog.{kind}.detail", "query": {key: i}})
        assert reply["allowed"] is allowed
        if allowed:
            assert reply["result"][kind][key] == 2


def test_scope_required_and_denied_before_instance_queries(resources, monkeypatch):
    params = {"username": "alice", "operation": "bklog.index_set.list", "query": {}}
    with pytest.raises(ValidationError):
        user_query.read_user_query(params)
    for scope in [{"bk_biz_id": 3}, {"bk_biz_id": 2, "space_uid": "bkci__project"}]:
        assert not user_query.read_user_query({**params, **scope})["allowed"]
    monkeypatch.setattr(
        user_query, "_evaluate_one", lambda *a, **kw: {"status": "ok", "allowed": False, "warnings": []}
    )
    assert not user_query.read_user_query({**params, "bk_biz_id": -12})["allowed"]
    resources.mode_router.batch_is_allowed.assert_not_called()


def test_registered_call_and_degraded_batch(resources):
    from apps.log_admin_resource.registry import AdminResourceRegistry

    params = {"username": "alice", "operation": "bklog.collector.list", "bk_biz_id": -12, "query": {"page_size": 1}}
    result = AdminResourceRegistry.call(user_query.NAME, params, app_code="reader")
    assert result["result"]["items"][0]["collector_config_id"] == 2
    resources.mode_router.batch_is_allowed.side_effect = None
    resources.mode_router.batch_is_allowed.return_value = SimpleNamespace(
        items=[SimpleNamespace(decision=SimpleNamespace(degraded=True))]
    )
    with pytest.raises(ValidationError):
        AdminResourceRegistry.call(user_query.NAME, params, app_code="reader")
    with pytest.raises(ValidationError):
        AdminResourceRegistry.call(user_query.NAME, {**params, "bk_tenant_id": "other"}, app_code="reader")
