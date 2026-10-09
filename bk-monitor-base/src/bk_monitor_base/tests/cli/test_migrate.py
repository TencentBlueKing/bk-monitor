from typing import Any
from unittest.mock import patch

import pytest

from bk_monitor_base.cli.commands.migrate import makemigrations, migrate


@pytest.mark.parametrize(
    "app_label,migration_name,kwargs,expected_args,expected_kwargs",
    [
        ("myapp", None, {}, ["myapp"], {}),
        ("myapp", "0002_auto", {}, ["myapp", "0002_auto"], {}),
        (None, None, {"fake": True}, ["--fake"], {}),
        ("myapp", None, {"plan": True}, ["myapp", "--plan"], {}),
        (
            "myapp",
            "0003",
            {"database": "test", "fake": True, "prune": True},
            ["myapp", "0003", "--fake", "--prune"],
            {"database": "test"},
        ),
        (None, None, {"skip_checks": True, "noinput": True}, ["--skip-checks", "--no-input"], {}),
    ],
)
def test_migrate_args_kwargs(
    app_label: str | None,
    migration_name: str | None,
    kwargs: dict[str, Any],
    expected_args: list[str],
    expected_kwargs: dict[str, Any],
) -> None:
    with patch("django.core.management.call_command") as mock_call:
        migrate(
            app_label=app_label,
            migration_name=migration_name,
            database=kwargs.get("database"),
            fake=kwargs.get("fake", False),
            fake_initial=kwargs.get("fake_initial", False),
            plan=kwargs.get("plan", False),
            run_syncdb=kwargs.get("run_syncdb", False),
            check=kwargs.get("check", False),
            prune=kwargs.get("prune", False),
            skip_checks=kwargs.get("skip_checks", False),
            noinput=kwargs.get("noinput", False),
        )
        # 检查调用参数
        mock_call.assert_called_once()
        call_args: tuple[Any, ...] = mock_call.call_args[0]
        call_kwargs: dict[str, Any] = mock_call.call_args[1]
        assert call_args[0] == "migrate"
        assert list(call_args[1:]) == expected_args
        for k, v in expected_kwargs.items():
            assert call_kwargs[k] == v


@pytest.mark.parametrize(
    "app_label,kwargs,expected_args,expected_kwargs",
    [
        (None, {}, [], {}),
        (["myapp"], {}, ["myapp"], {}),
        (["app1", "app2"], {}, ["app1", "app2"], {}),
        (None, {"dry_run": True}, ["--dry-run"], {}),
        (["myapp"], {"merge": True}, ["myapp", "--merge"], {}),
        (["myapp"], {"empty": True, "noinput": True}, ["myapp", "--empty", "--no-input"], {}),
        (["myapp"], {"name": "custom_name"}, ["myapp"], {"name": "custom_name"}),
        (
            ["myapp"],
            {"no_header": True, "check": True, "scriptable": True, "update": True},
            ["myapp", "--no-header", "--check", "--scriptable", "--update"],
            {},
        ),
    ],
)
def test_makemigrations_args_kwargs(
    app_label: list[str] | None,
    kwargs: dict[str, Any],
    expected_args: list[str],
    expected_kwargs: dict[str, Any],
) -> None:
    with patch("django.core.management.call_command") as mock_call:
        makemigrations(
            app_label=app_label,
            dry_run=kwargs.get("dry_run", False),
            merge=kwargs.get("merge", False),
            empty=kwargs.get("empty", False),
            noinput=kwargs.get("noinput", False),
            name=kwargs.get("name"),
            no_header=kwargs.get("no_header", False),
            check=kwargs.get("check", False),
            scriptable=kwargs.get("scriptable", False),
            update=kwargs.get("update", False),
        )
        mock_call.assert_called_once()
        call_args: tuple[Any, ...] = mock_call.call_args[0]
        call_kwargs: dict[str, Any] = mock_call.call_args[1]
        assert call_args[0] == "makemigrations"
        assert list(call_args[1:]) == expected_args
        for k, v in expected_kwargs.items():
            assert call_kwargs[k] == v
