"""最小宿主设置；所有平台资源和认证请求由测试显式替换。"""

import sys
from pathlib import Path

from django.conf import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bkmonitor"))
if not settings.configured:
    settings.configure(DEFAULT_CHARSET="utf-8", SECRET_KEY="synthetic-test-only", INSTALLED_APPS=[])
