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


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_backend_without_login_keeps_original_identity(settings, mocker, configured):
    from bkmonitor.utils.user import get_backend_username

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_ADMIN_USERNAME = configured
    settings.COMMON_USERNAME = "legacy"
    lookup = mocker.patch.object(api.bk_login, "batch_lookup_virtual_user")
    assert get_backend_username(bk_tenant_id="system") == "legacy"
    lookup.assert_not_called()


def test_configured_single_tenant_datalink(settings, mocker):
    import json

    from api.bk_login.default import BatchLookupVirtualUserResource
    from api.bkdata.default import GetDataLink
    from bkmonitor.utils.user import _single_tenant_admin_username

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_ADMIN_USERNAME = "  service-login  "
    _single_tenant_admin_username.cache_clear()
    lookup = mocker.patch.object(
        api.bk_login, "batch_lookup_virtual_user", return_value=[{"bk_username": "virtual-id"}]
    )
    assert "/api/bk-user/" in BatchLookupVirtualUserResource().base_url or settings.BK_USER_API_BASE_URL
    resource = GetDataLink()
    mocker.patch.object(resource, "report_api_request_count_metric")
    response = mocker.Mock()
    response.json.return_value = {"code": 0, "data": {}}
    send = mocker.patch.object(resource.session, "get", return_value=response)
    resource.request(bk_tenant_id="system", namespace="sample", kind="resulttables", name="sample")
    lookup.assert_called_once_with(
        bk_tenant_id="default", lookups="service-login", lookup_field="login_name", bk_username="admin"
    )
    args = send.call_args.kwargs
    assert "/v4/namespaces/" in args["url"]
    assert args["headers"]["X-Bk-Tenant-Id"] == "system"
    assert (
        json.loads(args["headers"]["x-bkapi-authorization"])["bk_username"]
        == args["params"]["bk_username"]
        == "virtual-id"
    )


def test_query_token_does_not_require_admin_lookup(settings, mocker):
    from api.bkdata.default import QueryDataResource

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_ADMIN_USERNAME = "unavailable"
    settings.BKDATA_DATA_TOKEN = "test-token"
    settings.COMMON_USERNAME = "legacy"
    mocker.patch("api.bkdata.default.get_request_username", return_value=None)
    mocker.patch("api.bkdata.default.get_local_username", return_value=None)
    lookup = mocker.patch.object(api.bk_login, "batch_lookup_virtual_user")
    params = QueryDataResource().full_request_data({"sql": "SELECT 1"})
    assert params["bk_username"] == "legacy"
    assert params["bkdata_authentication_method"] == "token"
    assert params["bkdata_data_token"] == "test-token"
    lookup.assert_not_called()
