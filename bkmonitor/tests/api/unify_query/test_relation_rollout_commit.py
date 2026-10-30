"""Exercise the production save hook with a real isolated SQLite transaction."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import django
import pytest
from django.conf import settings
from django.apps import apps
from django.db import connections, models, transaction
from django.db.utils import ConnectionHandler

if not settings.configured:
    settings.configure(
        SECRET_KEY="offline",
        INSTALLED_APPS=[],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        USE_I18N=False,
    )
    django.setup()


def test_configuration_publication_runs_only_after_commit():
    if not apps.apps_ready:
        django.setup()
    alias = "relation_rollout_probe"
    isolated = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})
    connection = isolated["default"]
    connection.alias = alias
    connections[alias] = connection
    path = Path(__file__).parents[3] / "bkmonitor/models/config.py"
    tree = ast.parse(path.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GlobalConfig")
    meta = next(node for node in cls.body if isinstance(node, ast.ClassDef) and node.name == "Meta")
    meta.body.append(ast.parse('app_label = "rollout_test"').body[0])
    schedule = Mock()
    namespace = {
        "__name__": __name__,
        "models": models,
        "transaction": transaction,
        "JsonField": models.JSONField,
        "_": lambda value: value,
        "_schedule_relation_schema_refresh": schedule,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), "exec"), namespace)
    model = namespace["GlobalConfig"]
    with connection.schema_editor() as schema:
        schema.create_model(model)
    try:
        with transaction.atomic(using=alias):
            model.objects.using(alias).create(key="RELATION_V1BETA3_BIZ_ID_WHITE_LIST", value=[2])
            schedule.assert_not_called()
        schedule.assert_called_once()
        schedule.reset_mock()
        with pytest.raises(RuntimeError):
            with transaction.atomic(using=alias):
                row = model.objects.using(alias).get(key="RELATION_V1BETA3_BIZ_ID_WHITE_LIST")
                row.value = []
                row.save()
                raise RuntimeError("rollback")
        schedule.assert_not_called()
        assert model.objects.using(alias).get(key="RELATION_V1BETA3_BIZ_ID_WHITE_LIST").value == [2]
        model.objects.using(alias).create(key="unrelated", value=1)
        schedule.assert_not_called()
    finally:
        with connection.schema_editor() as schema:
            schema.delete_model(model)
        connection.close()
        del connections[alias]


@pytest.mark.parametrize("result, retries", [(None, 1), (False, 1), (True, 0)])
def test_busy_or_failed_config_publication_is_retried(monkeypatch, result, retries):
    import sys

    path = Path(__file__).parents[3] / "metadata/task/tasks.py"
    tree = ast.parse(path.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "refresh_entity_definition_to_redis"
    )
    function.decorator_list = []
    monkeypatch.setitem(
        sys.modules, "metadata.task.entity_relation", SimpleNamespace(refresh_entity_definition_to_redis=lambda: result)
    )
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    task = SimpleNamespace(retry=Mock(side_effect=RuntimeError("retry")))
    if retries:
        with pytest.raises(RuntimeError, match="retry"):
            namespace[function.name](task, config_change=True)
    else:
        namespace[function.name](task, config_change=True)
    assert task.retry.call_count == retries
