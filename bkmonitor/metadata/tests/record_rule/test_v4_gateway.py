"""RecordRule V4 独立网关的请求路由与协议回归。"""

import json

import pytest
import requests

from api.bkdata import default as bkdata
from core.drf_resource import api
from core.errors.api import BKAPIError


@pytest.fixture(
    params=[
        (bkdata.ApplyRecordRuleFlow, bkdata.ApplyDataLink, "apply_record_rule_flow"),
        (bkdata.GetRecordRuleFlow, bkdata.GetDataLink, "get_record_rule_flow"),
        (bkdata.DeleteRecordRuleFlow, bkdata.DeleteDataLink, "delete_record_rule_flow"),
    ],
    ids=["apply", "get", "delete"],
)
def flow_api(request, settings, mocker):
    resource_class, original_class, api_name = request.param
    resource = resource_class()
    resource.bk_username = "gateway-test-user"
    settings.APP_CODE = "gateway-test-app"
    settings.SECRET_KEY = "gateway-test-secret"
    settings.SAAS_APP_CODE = "gateway-test-saas"
    settings.BK_DATA_PROJECT_MAINTAINER = "gateway-test-user"
    mocker.patch.object(resource, "report_api_request_count_metric")
    mocker.patch.object(resource, "report_api_failure_metric")
    response = mocker.Mock()
    response.json.return_value = {"code": 0, "data": {"status": "ok"}}
    http_request = mocker.patch.object(
        resource.session, "get" if resource.method == "GET" else "request", return_value=response
    )
    params = {"bk_tenant_id": "gateway-test-tenant"}
    if resource.method == "POST":
        params["config"] = [
            {
                "kind": "Flow",
                "metadata": {"name": "test-flow", "annotations": {"task_stopped": "true"}},
            }
        ]
    else:
        params.update(namespace="bkbase", kind="flows", name="test-flow")
    assert isinstance(getattr(api.bkdata, api_name), resource_class)
    return resource, original_class(), params, http_request, response


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("gateway", ["", "https://new.example.com/custom", "https://new.example.com/custom/"])
def test_record_rule_flow_request_uses_selected_gateway(flow_api, settings, mocker, multi_tenant, gateway):
    resource, original, params, http_request, _ = flow_api
    settings.BKDATA_RECORD_RULE_API_BASE_URL = gateway
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    original_gateway = "https://original.example.com/api/bk-base/prod/"
    mocker.patch.object(bkdata.BkDataAPIGWResource, "base_url", original_gateway)

    assert resource.request(params) == {"status": "ok"}

    if resource.method == "POST":
        path = "v4/apply/"
    else:
        tenant_path = "tenants/gateway-test-tenant/" if multi_tenant else ""
        path = f"v4/{tenant_path}namespaces/bkbase/flows/test-flow/"
    http_request.assert_called_once()
    sent = http_request.call_args.kwargs
    assert sent["url"] == f"{(gateway or original_gateway).rstrip('/')}/{path}"
    assert original.get_request_url(params) == original_gateway + path
    assert sent["headers"]["X-Bk-Tenant-Id"] == "gateway-test-tenant"
    assert json.loads(sent["headers"]["x-bkapi-authorization"]) == {
        "bk_app_code": "gateway-test-app",
        "bk_app_secret": "gateway-test-secret",
        "bk_username": "gateway-test-user",
    }
    request_data = sent["params" if resource.method == "GET" else "json"]
    expected_data = {**params, "bk_app_code": "gateway-test-saas", "bk_username": "gateway-test-user"}
    if resource.method == "POST":
        expected_data.pop("bk_tenant_id")
    assert request_data == expected_data


@pytest.mark.parametrize("error_type", ["api", "network"])
def test_record_rule_flow_failure_does_not_retry_on_original_gateway(flow_api, settings, error_type):
    resource, _, params, http_request, response = flow_api
    settings.BKDATA_RECORD_RULE_API_BASE_URL = "https://new.example.com/custom/"
    if error_type == "api":
        response.json.return_value = {"result": False, "code": 50000, "message": "gateway unavailable"}
        expected_error = BKAPIError
    else:
        http_request.side_effect = requests.ConnectionError("gateway unavailable")
        expected_error = requests.ConnectionError

    with pytest.raises(expected_error):
        resource.request(params)

    http_request.assert_called_once()
    assert http_request.call_args.kwargs["url"].startswith("https://new.example.com/custom/v4/")
