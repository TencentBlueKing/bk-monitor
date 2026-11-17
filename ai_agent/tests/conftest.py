"""最小宿主设置；所有平台资源和认证请求由测试显式替换。"""

import sys
from pathlib import Path

from django.conf import settings
from django.test import override_settings
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bkmonitor"))
if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="synthetic-test-only", INSTALLED_APPS=[])


@pytest.fixture(autouse=True)
def isolated_cache():
    from django.core.cache import cache

    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "ai-agent-unit-tests",
            }
        }
    ):
        cache.clear()
        yield
        cache.clear()
