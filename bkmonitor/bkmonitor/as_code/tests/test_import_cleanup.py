from unittest.mock import Mock

import pytest
from django.db import connections, router

from bkmonitor.as_code import parse
from bkmonitor.models import ActionConfig, AlertAssignGroup, AlertAssignRule, StrategyModel, UserGroup

pytestmark = pytest.mark.django_db(databases="__all__")

BK_BIZ_ID = 2
APP = "cleanup-test"
MODELS = {
    "rule": StrategyModel,
    "notice": UserGroup,
    "action": ActionConfig,
    "assign_group": AlertAssignGroup,
}
LONG_PATH = "nested/" + "x" * max(model._meta.get_field("path").max_length for model in MODELS.values()) + ".yaml"


@pytest.fixture
def non_strict_mysql():
    """仅调整测试连接，复现 MySQL 非严格模式对超长 path 的截断。"""
    aliases = {router.db_for_write(model) for model in MODELS.values()}
    if any(connections[alias].vendor != "mysql" for alias in aliases):
        pytest.skip("requires MySQL path truncation")
    modes = {}
    try:
        for alias in aliases:
            with connections[alias].cursor() as cursor:
                cursor.execute("SELECT @@SESSION.sql_mode")
                modes[alias] = cursor.fetchone()[0]
                mode = ",".join(
                    value
                    for value in modes[alias].split(",")
                    if value not in {"STRICT_TRANS_TABLES", "STRICT_ALL_TABLES"}
                )
                cursor.execute("SET SESSION sql_mode = %s", [mode])
        yield
    finally:
        for alias, mode in modes.items():
            with connections[alias].cursor() as cursor:
                cursor.execute("SET SESSION sql_mode = %s", [mode])


def make_record(obj, path=LONG_PATH):
    return {
        "obj": obj,
        "path": path,
        "hash": "new-hash",
        "snippet": "",
        "schema_error": None,
        "parse_error": None,
        "validate_error": None,
    }


@pytest.mark.parametrize("incremental", [False, True])
@pytest.mark.parametrize("referenced", [False, True])
@pytest.mark.filterwarnings("ignore:.*Data truncated for column 'path'.*")
def test_import_cleanup_preserves_saved_and_unchanged_resources(monkeypatch, non_strict_mysql, incremental, referenced):
    resources = {}
    configs = {}
    for kind, model in MODELS.items():
        resources[kind] = {}
        path_limit = model._meta.get_field("path").max_length
        for key, path, app, bk_biz_id in [
            ("saved", "", APP, BK_BIZ_ID),
            ("unchanged", "unchanged.yaml", APP, BK_BIZ_ID),
            ("removed", LONG_PATH[:path_limit], APP, BK_BIZ_ID),
            ("other_app", "removed.yaml", "other-app", BK_BIZ_ID),
            ("other_biz", "removed.yaml", APP, BK_BIZ_ID + 1),
        ]:
            extra = {"plugin_id": "1", "execute_config": {}} if kind == "action" else {}
            resources[kind][key] = model.objects.create(
                bk_biz_id=bk_biz_id, name=f"{kind}-{key}", app=app, path=path, hash="old-hash", **extra
            )
        configs[f"{kind}/{LONG_PATH}"] = "{}"
        configs[f"{kind}/unchanged.yaml"] = "{}"

    # 转换阶段只返回需要保存的记录；hash 未变化的记录不会返回。
    strategy = Mock(id=resources["rule"]["saved"].pk)
    monkeypatch.setattr(parse, "convert_rules", Mock(return_value=[make_record(strategy)]))
    for kind, converter in [("notice", "convert_notices"), ("action", "convert_actions")]:
        serializer = Mock(instance=resources[kind]["saved"])
        monkeypatch.setattr(parse, converter, Mock(return_value=[make_record(serializer)]))

    assign_serializer = Mock(spec=parse.BatchSaveAssignRulesSlz)
    assign_serializer.save.return_value = {"assign_group_id": resources["assign_group"]["saved"].pk}
    monkeypatch.setattr(parse, "convert_assign_groups", Mock(return_value=[make_record(assign_serializer)]))
    monkeypatch.setattr(parse, "convert_duty_rules", Mock(return_value=[]))
    for function in ["get_user_group_strategies", "get_action_config_strategy_dict"]:
        monkeypatch.setattr(parse, function, lambda ids: dict.fromkeys(ids, []) if referenced else {})
    monkeypatch.setattr(parse, "get_user_group_assign_rules", lambda ids: {})
    monkeypatch.setattr(parse, "get_action_config_rules", lambda ids, bk_biz_id: {})

    for group in resources["assign_group"].values():
        AlertAssignRule.objects.create(assign_group_id=group.pk, bk_biz_id=group.bk_biz_id)

    assert parse.import_code_config(BK_BIZ_ID, APP, configs, incremental=incremental) is None

    for kind, model in MODELS.items():
        path_limit = model._meta.get_field("path").max_length
        saved = resources[kind]["saved"]
        saved.refresh_from_db()
        assert saved.path == LONG_PATH[:path_limit]
        assert saved.app == APP
        assert saved.hash == "new-hash"
        for key in ["unchanged", "other_app", "other_biz"]:
            row = resources[kind][key]
            original = (row.path, row.app, row.hash)
            row.refresh_from_db()
            assert (row.path, row.app, row.hash) == original

        removed = resources[kind]["removed"]
        if incremental:
            removed.refresh_from_db()
            assert removed.app == APP
            assert removed.path == LONG_PATH[:path_limit]
        elif referenced and kind in {"notice", "action"}:
            removed.refresh_from_db()
            assert (removed.app, removed.path, removed.hash, removed.snippet) == ("", "", "", "")
        else:
            assert not model.objects.filter(pk=removed.pk).exists()

    for key, group in resources["assign_group"].items():
        assert AlertAssignRule.objects.filter(assign_group_id=group.pk).exists() == (incremental or key != "removed")
