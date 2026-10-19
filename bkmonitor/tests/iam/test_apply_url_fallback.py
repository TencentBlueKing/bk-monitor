"""Application capabilities preserve local UI data and configured fallback URLs."""

from unittest.mock import MagicMock
import pytest
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.backends.v3.client import V3Client
from iam_engine.core.requests import ResourceInstance
from iam_engine.v4.exceptions import V4TransportError


@pytest.mark.parametrize(
    "name,ok,url,fallback,expected",
    [
        ("v4", True, "", "https://fallback.test", ""),
        ("v4", True, "", "", ""),
        ("v4", True, "https://apply.test", "https://fallback.test", "https://apply.test"),
        ("v3", False, "", "https://fallback.test", "https://fallback.test"),
        ("v3", True, "", "https://fallback.test", ""),
        ("v3", False, "", "", ""),
        ("v3", True, "https://apply.test", "https://fallback.test", "https://apply.test"),
    ],
)
def test_application_fallback(name, ok, url, fallback, expected):
    p = build_provider(
        name,
        options={
            "base_url": "https://iam.example.test",
            "credentials": {"app_code": "offline", "app_secret": "offline"},
            "system": {"id": "bk_monitorv3", "name": "Monitor"},
            "fallback_apply_url": fallback,
        } if name == "v3" else None,
    )
    p.resolver = None
    if name == "v3":
        client = V3Client(
            "offline", "offline", "https://iam.example.test", "bk_monitorv3", p.codec, bk_tenant_id="system"
        )
        client.get_apply_url = MagicMock(return_value=(ok, "", url))
    else:
        client = MagicMock()
        client.generate_perm_apply_url.return_value = url
    p._get_client = MagicMock(return_value=client)
    data, result = p.get_apply_data(["view_business"], [ResourceInstance("space", "2", name="Biz")])
    assert result == expected
    assert data["actions"][0]["related_resource_types"][0]["instances"][0][0]["name"] == "Biz"


def test_v4_transport_failure_keeps_local_permission_data():
    p = build_provider(
        "v4",
    )
    p.resolver = None
    client = MagicMock()
    client.generate_perm_apply_url.side_effect = V4TransportError("offline")
    p._get_client = MagicMock(return_value=client)
    data, url = p.get_apply_data(["view_business"], [ResourceInstance("space", "2")])
    assert data["system"] == "bk_monitorv3"
    assert url == ""
