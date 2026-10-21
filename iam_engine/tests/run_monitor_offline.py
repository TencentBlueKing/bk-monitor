"""Run the repository's pytest tests with real Monitor settings, no services.

Use a separate Python process from the repository root. Never deploy these
overrides. All DB aliases are in-memory SQLite and outbound sockets are blocked.
"""

import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch


def forbidden(*args, **kwargs):
    raise RuntimeError("Offline verification forbids outbound connections")


def main():
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--role", choices=["web", "api", "worker"], default="web")
    parser.add_argument("--startup-only", action="store_true")
    options, tests = parser.parse_known_args()
    if options.startup_only:
        # Use the application's existing Django-test bootstrap branch: worker
        # cache-node registration belongs to post_migrate, which we never run.
        sys.argv.append("test")
    root = Path(__file__).resolve().parents[2]
    os.chdir(root / "bkmonitor")
    sys.path[:0] = [
        str(root),
        str(root / "bkmonitor"),
        str(root / "bkmonitor/packages"),
        str(root / "bk-monitor-base/src"),
    ]
    # Dummy credentials only; do not load a developer's local_settings.py.
    if (root / "bkmonitor/local_settings.py").exists():
        raise RuntimeError("Refusing to load personal local settings in offline verification")
    os.environ.update(
        {
            "DJANGO_CONF_MODULE": f"conf.{options.role}.development.community",
            "BKAPP_DEPLOY_PLATFORM": "community",
            "DJANGO_SETTINGS_MODULE": "settings",
            "USE_DYNAMIC_SETTINGS": "0",
            "BK_MONITOR_APP_CODE": "offline-monitor",
            "BK_MONITOR_APP_SECRET": "offline-only",
            "BKPAAS_APP_ID": "offline-monitor",
            "BKPAAS_APP_SECRET": "offline-only",
            "APP_ID": "offline-monitor",
            "APP_TOKEN": "offline-only",
            "BKPAAS_MAJOR_VERSION": "3",
            "BK_PAAS_HOST": "https://paas.example.test",
            "BKPAAS_URL": "https://paas.example.test",
            "BK_PAAS2_URL": "https://paas.example.test",
            "BK_COMPONENT_API_URL": "https://api.example.test",
            "BKAPP_IAM_PERMISSION_MODE": "v3",
            "BKAPP_IAM_V4_API_BASE_URL": "https://iam.example.test/dev",
            "BK_IAM_LIVE": "0",
        }
    )
    import pytest
    import importlib
    import requests
    import django
    from django.conf import settings

    with (
        patch.object(socket.socket, "connect", forbidden),
        patch.object(requests.sessions.Session, "request", forbidden),
    ):
        # The shared callback URLConf imports backend modules as well as Web.
        # Reuse real worker defaults only for absent settings, not app/DB overrides.
        for role in ("worker", "api"):
            role_defaults = importlib.import_module("config.role." + role)
            for name in dir(role_defaults):
                if name.isupper() and not hasattr(settings, name):
                    setattr(settings, name, getattr(role_defaults, name))
        settings.DATABASES = {
            name: {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
            for name in set(settings.DATABASES) | {"default", "monitor_api"}
        }
        settings.CACHES = {
            name: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
            for name in set(settings.CACHES) | {"default", "login_db"}
        }
        settings.LOGGING = {}
        for name in ("CELERY", "SERVICE", "QUEUE", "CACHE", "LOG"):
            setattr(settings, "REDIS_" + name + "_CONF", {"host": "localhost", "port": 6379, "db": 0, "password": ""})
        from config.tools.rabbitmq import get_rabbitmq_settings

        (
            settings.RABBITMQ_HOST,
            settings.RABBITMQ_PORT,
            settings.RABBITMQ_VHOST,
            settings.RABBITMQ_USER,
            settings.RABBITMQ_PASS,
            _,
        ) = get_rabbitmq_settings(settings.APP_CODE, backend=True)
        # API/Worker use the SaaS identity normally supplied by GlobalConfig.
        # Keep this harness independent of real DB credentials in every role.
        settings.SAAS_APP_CODE = "offline-saas"
        settings.SAAS_SECRET_KEY = "offline-only"
        django.setup()
        from bkmonitor.iam.permission import Permission

        permission = Permission(username="offline_user", bk_tenant_id="system")
        print(
            "Offline Monitor startup:",
            settings.ROLE,
            list(permission.providers),
            "actions:",
            len(permission.schema.actions.values()),
        )
        if options.startup_only:
            from celery import current_app

            current_app.finalize()
            assert "bkmonitor.iam.tasks.grant.grant_v4_creator_action" not in current_app.tasks
            print("No asynchronous IAM creator-grant task registered")
            return 0
        tests = tests or ["tests/iam", "-m", "not live"]
        with patch("bkmonitor.utils.common_utils.get_local_ip", return_value="127.0.0.1"):
            return pytest.main(
                [
                    "-c",
                    "/dev/null",
                    "--confcutdir=tests/iam",
                    "--ignore-glob=**/test_live*",
                    "-p",
                    "no:cacheprovider",
                    "-o",
                    "markers=live: explicit real IAM verification",
                    "-q",
                    "--tb=short",
                    *tests,
                ]
            )


if __name__ == "__main__":
    raise SystemExit(main())
