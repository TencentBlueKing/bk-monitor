import os
import subprocess
import sys
from pathlib import Path


def test_redis_management_urls_import_under_production_web_settings():
    project_root = Path(__file__).resolve().parents[4]
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "settings",
        "DJANGO_CONF_MODULE": "conf.web.production.community",
        "BKAPP_SECRET_KEY": "test",
        "BK_PAAS_HOST": "http://example.com",
        "APP_ID": "test",
        "APP_TOKEN": "test",
        "BKPAAS_MAJOR_VERSION": "3",
    }
    env["PYTHONPATH"] = os.pathsep.join(path for path in (str(project_root.parent), env.get("PYTHONPATH", "")) if path)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import django; django.setup(); import monitor_web.redis_management.urls",
        ],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
