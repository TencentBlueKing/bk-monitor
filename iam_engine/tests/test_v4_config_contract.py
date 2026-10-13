from types import SimpleNamespace

import pytest

from iam_engine.settings import load_iam_settings
from iam_engine.v4 import config as shared_config
from iam_engine.v4 import gateway
from bkmonitor.iam.backends.v4.config import V4Options as MonitorOptions


@pytest.mark.parametrize(
    "timeout,chunk,workers", [("10", "100", "4"), ("bad", "bad", "bad"), ("0", "0", "0"), ("1.5", "1000", "1000")]
)
def test_both_products_normalize_the_same_options(monkeypatch, timeout, chunk, workers):
    values = load_iam_settings(
        {"BK_IAM_V4_TIMEOUT": timeout, "BK_IAM_V4_BATCH_CHUNK_SIZE": chunk, "BK_IAM_V4_BATCH_MAX_WORKERS": workers}
    )
    settings = SimpleNamespace(**values, APP_CODE="app", SECRET_KEY="offline", BK_IAM_SYSTEM_ID="bk_monitorv3")
    monkeypatch.setattr(shared_config, "settings", settings)
    monkeypatch.setattr(gateway, "settings", settings)
    bklog = shared_config.V4Options.from_settings()
    monitor = MonitorOptions.from_dict(
        {
            "base_url": "https://example.test/",
            "system": {"id": "bk_monitorv3", "name": "Monitor"},
            "credentials": {"app_code": "app", "app_secret": "offline"},
            "timeout": timeout,
            "chunk_size": chunk,
            "max_workers": workers,
        }
    )
    assert (bklog.timeout_seconds, bklog.batch_chunk_size, bklog.batch_max_workers) == (
        monitor.timeout,
        monitor.chunk_size,
        monitor.max_workers,
    )
    assert bklog.system_id == "bk_monitorv3"
    assert bklog.gateway_url == ""
