"""Run strategy adapters with real Django, an in-memory database and a cold RPC registry.

Run this file with the repository's Python environment. Optional arguments select
pytest node paths relative to bkmonitor; by default all affected adapter tests run.
Roundtrip tests retain real serializers, Resources and ORM. No configured database
or private credential is required.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_TESTS = [
    "kernel_api/rpc/tests/test_bkm_cli_strategy_management.py",
    "kernel_api/rpc/tests/test_bkm_cli_inspect_strategy_config.py",
    "kernel_api/rpc/tests/test_bkm_cli_strategy_standard_roundtrip.py",
    "bkmonitor/strategy/tests/test_audit_operator.py",
    "kernel_api/rpc/tests/test_bkm_cli_unify_query.py",
]


def main() -> int:
    repo = Path(__file__).resolve().parents[4]
    os.chdir(repo / "bkmonitor")
    sys.path[:0] = [
        str(repo / "bkmonitor"),
        str(repo / "bkmonitor" / "packages"),
        str(repo),
        str(repo / "bk-monitor-base" / "src"),
    ]
    os.environ.update(
        DJANGO_SETTINGS_MODULE="settings",
        DJANGO_CONF_MODULE="conf.api.development.community",
        APP_ID="strategy-adapter-tests",
        APP_TOKEN="synthetic-token",
        BK_PAAS_HOST="http://example.test",
        USE_DYNAMIC_SETTINGS="0",
        BKM_UNITTEST="1",
        BKAPP_DEPLOY_PLATFORM="community",
        BK_MONITOR_APP_CODE="bk_monitorv3",
        BK_MONITOR_APP_SECRET="synthetic-secret",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )

    import django
    import pytest
    from django.conf import settings

    settings.SECRET_KEY = "synthetic-secret"
    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    settings.DATABASE_ROUTERS = []
    settings.CACHES = {name: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"} for name in settings.CACHES}
    django.setup()

    from kernel_api.rpc import KernelRPCRegistry
    from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

    KernelRPCRegistry.ensure_loaded()
    assert BkmCliOpRegistry.resolve("manage-strategy-config").func_name == "bkm_cli.manage_strategy_config"
    assert BkmCliOpRegistry.resolve("query-unify-query").func_name == "bkm_cli.query_unify_query"
    print("REAL_KERNEL_RPC_COLD_LOAD_OK", flush=True)

    from blueapps.account.models import User
    from django.db import connection, transaction

    from bkmonitor.models import (
        ActionConfig,
        AlgorithmModel,
        DetectModel,
        ItemModel,
        QueryConfigModel,
        StrategyActionConfigRelation,
        StrategyHistoryModel,
        StrategyLabel,
        StrategyModel,
        UserGroup,
    )
    from bkmonitor.models.fta.action import ActionPlugin
    from bkmonitor.models.issue import StrategyIssueConfig

    with connection.schema_editor() as editor:
        for model in (
            User,
            StrategyModel,
            ItemModel,
            DetectModel,
            AlgorithmModel,
            QueryConfigModel,
            StrategyLabel,
            StrategyActionConfigRelation,
            ActionConfig,
            StrategyIssueConfig,
            StrategyHistoryModel,
            UserGroup,
            ActionPlugin,
        ):
            editor.create_model(model)

    class IsolatedOrm:
        @pytest.fixture(autouse=True)
        def isolate_orm(self, request):
            if request.node.get_closest_marker("django_db"):
                with transaction.atomic():
                    yield
                    transaction.set_rollback(True)
            else:
                yield

    return pytest.main(
        [
            "--noconftest",
            "-c",
            os.devnull,
            "--rootdir",
            str(repo / "bkmonitor"),
            "-p",
            "no:cacheprovider",
            "-o",
            "markers=django_db: isolated real database test",
            "-q",
            *(sys.argv[1:] or DEFAULT_TESTS),
        ],
        plugins=[IsolatedOrm()],
    )


if __name__ == "__main__":
    raise SystemExit(main())
