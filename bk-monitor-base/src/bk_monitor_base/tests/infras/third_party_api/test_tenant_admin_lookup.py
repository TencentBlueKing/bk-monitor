from unittest.mock import patch

import pytest

from bk_monitor_base.config.blueking import BlueKingConfig
from bk_monitor_base.infras.third_party_api.user import api


def test_tenant_admin_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证运维环境变量用于各租户的登录名查询。"""
    monkeypatch.setenv("BK_ADMIN_USERNAME", "custom-login")
    monkeypatch.setattr(api.get_config(), "blueking", BlueKingConfig(enable_multi_tenancy=True))
    with patch.object(api, "request_user_api") as lookup:
        for tenant in ("tenant-a", "tenant-b"):
            lookup.return_value = {"data": [{"bk_username": tenant}]}
            assert api.get_tenant_admin_username.__wrapped__(tenant) == tenant
            lookup.assert_called_with(
                bk_tenant_id=tenant,
                method="GET",
                path="api/v3/open/tenant/virtual-users/-/lookup/",
                username="admin",
                params={"lookup_field": "login_name", "lookups": "custom-login"},
            )


def test_default_admin_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """未注入配置时保持原有登录名及单租户返回值。"""
    monkeypatch.delenv("BK_ADMIN_USERNAME", raising=False)
    blueking = BlueKingConfig(enable_multi_tenancy=False)
    assert blueking.bk_admin_username == "bk_admin"
    monkeypatch.setattr(api.get_config(), "blueking", blueking)
    assert api.get_tenant_admin_username.__wrapped__("system") == "admin"
