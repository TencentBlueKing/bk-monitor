"""Run BKLog's real Django IAM suite with only in-memory local dependencies.

This is a test harness, not deployment configuration. Outbound sockets and HTTP
are blocked before loading any settings. Only IAM fixture tables are created.
"""

import os
from importlib import import_module
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock, patch


def forbidden(*args, **kwargs):
    raise RuntimeError("Offline verification forbids outbound connections")


def main():
    root = Path(__file__).resolve().parents[2]
    os.chdir(root / "bklog")
    sys.path[:0] = [str(root / "bklog"), str(root)]
    if (root / "bklog/config/local_settings.py").exists():
        raise RuntimeError("Refusing to load personal settings in offline verification")
    os.environ.update(
        {
            "DJANGO_SETTINGS_MODULE": "settings",
            "BKPAAS_ENVIRONMENT": "dev",
            "BK_ENV": "development",
            "APP_ID": "offline-log",
            "APP_TOKEN": "offline-only",
            "BK_PAAS_HOST": "https://paas.example.test",
            "BKPAAS_URL": "https://paas.example.test",
            "BKAPP_APIGW_CLOSE": "on",
            "BK_API_URL_TMPL": "https://api.example.test/{api_name}/",
            "BKAPP_IAM_PERMISSION_MODE": "v3",
            "BKAPP_IAM_V4_API_BASE_URL": "https://iam.example.test/dev",
            "BKPAAS_MAJOR_VERSION": "3",
            "BKPAAS_APP_ID": "offline-log",
            "BKPAAS_APP_SECRET": "offline-only",
        }
    )
    import django
    import requests
    from django.conf import settings

    with (
        patch.object(socket.socket, "connect", forbidden),
        patch.object(requests.sessions.Session, "request", forbidden),
        patch("django_redis.get_redis_connection", return_value=Mock()),
    ):
        settings.DATABASES = {
            name: {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
            for name in set(settings.DATABASES) | {"default"}
        }
        settings.CACHES = {
            name: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
            for name in set(settings.CACHES) | {"default"}
        }
        settings.LOGGING = {}
        settings.AUTO_UPDATE_COMPONENT_MODELS = False
        settings.APIGW_ENABLED = False
        settings.DEBUG = True
        django.setup()
        # Do not run migrations or post_migrate: those register models in real IAM.
        from django.db import connection
        from django.apps import apps
        from apps.log_search.models import GlobalConfig
        from apps.feature_toggle.models import FeatureToggle
        from apps.log_search.models import Space, SpaceType

        with connection.schema_editor() as editor:
            for model in (GlobalConfig, FeatureToggle, SpaceType, Space):
                editor.create_model(model)
        # Seed the same IAM mode row as the standard Django test database, without
        # running full migrations or post_migrate hooks that could contact IAM.
        import_module("apps.feature_toggle.migrations.0011_init_iam_permission_toggle").forwards_func(apps, None)
        print("Offline BKLog startup: real Django apps, in-memory IAM fixture tables and initial mode data")
        names = sys.argv[1:] or ["apps.tests.iam"]
        suite = unittest.TestSuite()
        for name in names:
            suite.addTests(
                unittest.defaultTestLoader.discover("apps/tests/iam", top_level_dir=".")
                if name == "apps.tests.iam"
                else unittest.defaultTestLoader.loadTestsFromName(name)
            )
        return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
