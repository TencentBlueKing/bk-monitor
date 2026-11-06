import json

import pytest

from api.bkdata import default as bkdata
from core.errors.common import UserInfoMissing


@pytest.mark.parametrize("resource_class", [bkdata.ApplyDataLink, bkdata.GetDataLink])
@pytest.mark.parametrize("multi_tenant", [True, False])
@pytest.mark.parametrize("caller_params", [{}, {"bk_username": "caller-supplied"}], ids=["background", "explicit-user"])
def test_datalink_request_identity(resource_class, multi_tenant, caller_params, settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    settings.BK_DATA_PROJECT_MAINTAINER = "project-maintainer"
    lookup = mocker.patch.object(bkdata, "get_admin_username", return_value="tenant-user")
    mocker.patch("core.drf_resource.contrib.api.make_userinfo", return_value={"bk_username": "context-user"})
    resource = resource_class()
    mocker.patch.object(resource, "report_api_request_count_metric")
    response = mocker.Mock()
    response.json.return_value = {"code": 0, "data": {}}
    is_get = resource.method == "GET"
    send = mocker.patch.object(resource.session, "get" if is_get else "request", return_value=response)
    params = {"kind": "resulttables", "namespace": "bkmonitor", "name": "sample"} if is_get else {"config": []}

    resource.request(bk_tenant_id="tenant-a", **caller_params, **params)

    expected = "tenant-user" if multi_tenant else "project-maintainer"
    sent = send.call_args.kwargs
    assert sent["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
    assert json.loads(sent["headers"]["x-bkapi-authorization"])["bk_username"] == expected
    assert sent["params" if is_get else "json"]["bk_username"] == expected
    if multi_tenant:
        lookup.assert_called_once_with("tenant-a")
    else:
        lookup.assert_not_called()


def test_datalink_missing_tenant_user_stops_before_apply(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    mocker.patch.object(bkdata, "get_admin_username", return_value=None)
    resource = bkdata.ApplyDataLink()
    send = mocker.patch.object(resource.session, "request")

    with pytest.raises(UserInfoMissing):
        resource.request(bk_tenant_id="tenant-a", bk_username="caller-supplied", config=[])

    send.assert_not_called()
