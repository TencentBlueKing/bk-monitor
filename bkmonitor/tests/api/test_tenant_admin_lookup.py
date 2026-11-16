import pytest

from bkmonitor.utils.user import get_admin_username
from core.drf_resource import api


@pytest.mark.parametrize("tenant", ["tenant-a", "tenant-b"])
def test_tenant_admin_lookup(tenant, settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.BK_ADMIN_USERNAME = "custom-login"
    lookup = mocker.patch.object(api.bk_login, "batch_lookup_virtual_user", return_value=[{"bk_username": tenant}])
    assert get_admin_username.__wrapped__(tenant) == tenant
    lookup.assert_called_once_with(
        bk_tenant_id=tenant, lookup_field="login_name", lookups="custom-login", bk_username="admin"
    )


def test_single_tenant_admin(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.COMMON_USERNAME = "single-user"
    assert get_admin_username.__wrapped__("system") == "single-user"
