from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import connections, router
from django.db.utils import ConnectionHandler
from django.utils import timezone

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import alarm_config as config


@pytest.fixture
def records(django_db_blocker, monkeypatch, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    monkeypatch.setattr(
        config.SpaceApi,
        "list_spaces",
        lambda bk_tenant_id: [SimpleNamespace(bk_biz_id=-12 if bk_tenant_id == "ops" else 2)],
    )
    db = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})["default"]
    models = [model.model for model in config.RESOURCES.values()] + [
        config.DutyArrange,
        config.DutyRule,
        config.AlertAssignRule,
        config.StrategyActionConfigRelation,
        config.StrategyModel,
    ]
    aliases = {
        "default",
        *(router.db_for_read(model) for model in models),
        *(router.db_for_write(model) for model in models),
    }
    for alias in aliases:
        monkeypatch.setattr(connections._connections, alias, db, raising=False)
    with django_db_blocker.unblock():
        try:
            with db.schema_editor() as editor:
                for model in models:
                    editor.create_model(model)
            now = timezone.now()
            for pk, biz in [(1, -12), (2, -12), (3, 2)]:
                common = dict(id=pk, bk_biz_id=biz)
                config.UserGroup.objects.bulk_create(
                    [config.UserGroup(**common, name=f"group-{pk}", need_duty=pk == 2)]
                )
                config.AlertAssignGroup.objects.bulk_create(
                    [config.AlertAssignGroup(**common, name="assign", priority=pk)]
                )
                config.Shield.objects.bulk_create(
                    [
                        config.Shield(
                            **common,
                            description="network",
                            category="scope",
                            scope_type="biz",
                            begin_time=now,
                            end_time=now + timedelta(days=1 if pk == 1 else -1),
                            failure_time=now,
                            is_enabled=pk != 3,
                        )
                    ]
                )
                config.ActionConfig.objects.bulk_create(
                    [
                        config.ActionConfig(
                            **common,
                            name="callback",
                            plugin_id="4",
                            execute_config={"headers": [{"key": "Authorization", "value": "private"}]},
                        )
                    ]
                )
                config.DutyArrange.objects.bulk_create(
                    [config.DutyArrange(id=pk, user_group_id=pk, users=[{"id": "ops"}])]
                )
                config.AlertAssignRule.objects.bulk_create(
                    [config.AlertAssignRule(id=pk, bk_biz_id=biz, assign_group_id=pk, user_groups=[pk])]
                )
                config.StrategyModel.objects.bulk_create([config.StrategyModel(**common, name=f"strategy-{pk}")])
                config.StrategyActionConfigRelation.objects.bulk_create(
                    [config.StrategyActionConfigRelation(id=pk, config_id=1, strategy_id=pk)]
                )
            for pk, biz in [(4, 0), (5, 2)]:
                config.DutyRule.objects.bulk_create([config.DutyRule(id=pk, bk_biz_id=biz, name="rotation")])
                config.DutyArrange.objects.bulk_create([config.DutyArrange(id=pk, duty_rule_id=pk)])
            config.UserGroup.objects.filter(id=2).update(duty_rules=[4, 5])
            yield {"bk_tenant_id": "ops", "bk_biz_id": -12}
        finally:
            db.close()


@pytest.mark.parametrize(
    ("kind", "filters", "expected"),
    [
        ("user_group", {"need_duty": False, "keyword": "group"}, 1),
        ("assignment", {"priority": 2}, 2),
        ("shield", {"category": "scope", "status": 2}, 2),
        ("action", {"plugin_id": "4", "keyword": "callback"}, 2),
    ],
)
def test_list_and_detail(records, kind, filters, expected):
    result = config.list_configs(kind, {**records, **filters, "page_size": 1})["data"]
    assert [row["id"] for row in result["items"]] == [expected]
    assert config.get_config(kind, {**records, "id": expected})["data"]["config"]["id"] == expected
    with pytest.raises(CustomException):
        config.get_config(kind, {**records, "id": 3})
    assert config.list_configs(kind, {**records, "bk_biz_id": 2})["data"]["total"] == 0


def test_redaction_and_paged_relations(records):
    action = config.get_config("action", {**records, "id": 1})["data"]["config"]
    assert action["execute_config"]["headers"] == [{"key": "Authorization", "value": "[REDACTED]"}]
    assert "execute_config" not in config.list_configs("action", records)["data"]["items"][0]
    binding = config.related("action", {**records, "id": 1, "page": 2, "page_size": 1})["data"]
    assert binding["total"] == 2 and [r["strategy_id"] for r in binding["items"]] == [2]
    assert config.related("assignment", {**records, "id": 2})["data"]["items"][0]["user_groups"] == [2]
    assert config.related("user_group", {**records, "id": 1})["data"]["items"][0]["users"] == [{"id": "ops"}]
    duties = config.related("user_group", {**records, "id": 2})["data"]["items"]
    assert [(r["id"], r["user_group_id"]) for r in duties] == [(2, 2), (4, None)]
    for kind in ("assignment", "user_group", "action"):
        with pytest.raises(CustomException):
            config.related(kind, {**records, "id": 3})
    assert config.list_configs("shield", {"status": 3})["data"]["items"][0]["id"] == 3


def test_removed_configs_are_hidden_from_lists_details_and_children(records):
    config.AlertAssignGroup.objects.filter(id=2).update(is_deleted=True)
    assert config.list_configs("assignment", {**records, "id": 2})["data"]["total"] == 0
    for query in (config.get_config, config.related):
        with pytest.raises(CustomException):
            query("assignment", {**records, "id": 2})


def test_user_scoped_public_groups_and_foreign_children(records):
    from kernel_api.rpc.functions.admin.common import ResourceNotFound

    config.UserGroup.objects.bulk_create([config.UserGroup(id=20, name="公共轮值", bk_biz_id=0)])
    user_scope = config.list_configs("user_group", records, include_public=True)["data"]
    assert {row["bk_biz_id"] for row in user_scope["items"]} == {-12, 0}
    assert config.get_config("user_group", {**records, "id": 20}, include_public=True)["data"]["config"]["id"] == 20
    with pytest.raises(ResourceNotFound):
        config.related("user_group", {**records, "id": 3}, include_public=True)
