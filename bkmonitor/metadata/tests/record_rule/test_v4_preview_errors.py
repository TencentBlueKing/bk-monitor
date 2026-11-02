"""API、独立 MCP 与 Unified MCP 的预解析业务错误协议保持一致。"""

from types import SimpleNamespace

import pytest
from django.urls import include, path, resolve
from rest_framework.test import APIRequestFactory

from core.drf_resource.routers import ResourceRouter
from kernel_api.resource import recording_rule_mcp, unified_mcp
from kernel_api.views.v4.recording_rule import RecordingRuleViewSet
from kernel_api.views.v4.recording_rule_mcp import RecordingRuleMCPViewSet
from kernel_api.views.v4.unified_mcp import UnifiedMCPViewSet
from metadata import models
from metadata.tests.record_rule.test_v4_operator import (
    TENANT_ID,
    external_api as _external_api,
    v4_base_data as _v4_base_data,
)
from metadata.tests.record_rule.test_v4_public_api import group, public_context as _public_context

external_api = _external_api
v4_base_data = _v4_base_data
public_context = _public_context

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def preview_http(public_context, mocker):
    user = SimpleNamespace(username="alice", tenant_id=TENANT_ID)
    request_context = SimpleNamespace(user=user, unified_mcp_permission_checked=True)
    mocker.patch.object(recording_rule_mcp, "get_request", return_value=request_context)
    mocker.patch.object(recording_rule_mcp, "_principal", return_value=user)
    mocker.patch.object(recording_rule_mcp, "Permission")
    mocker.patch.object(unified_mcp, "get_request", return_value=request_context)
    router = ResourceRouter()
    router.register("recording_rule", RecordingRuleViewSet)
    router.register("recording_rule_mcp", RecordingRuleMCPViewSet)
    router.register("unified_mcp", UnifiedMCPViewSet)
    urlconf = (path("api/v4/", include(router.urls)),)

    def preview(entry, params):
        if entry == "unified":
            url = "/api/v4/unified_mcp/execute_tool/"
            body = {
                "tool_name": "preview_recording_rule",
                "tool_args": {**params, "bk_biz_id": str(params["bk_biz_id"])},
            }
        else:
            url = f"/api/v4/{'recording_rule' if entry == 'api' else 'recording_rule_mcp'}/preview_config/"
            body = params
        match = resolve(url, urlconf=urlconf)
        return match.func(APIRequestFactory().post(url, body, format="json"), **match.kwargs)

    return preview


@pytest.mark.parametrize("entry", ["api", "mcp", "unified"])
@pytest.mark.parametrize(
    "case,code,error_path",
    [
        ("yaml", "INVALID_CONFIG", "config"),
        ("rules", "INVALID_CONFIG", "config"),
        ("space", "INVALID_SPACE", "space_uid"),
        ("missing_rule", "RULE_NOT_FOUND", "id"),
        ("query", "RESOLVE_FAILED", "config.rules[0]"),
        ("source", "RESOLVE_FAILED", "config.rules[0]"),
    ],
)
def test_standard_preview_errors(preview_http, public_context, entry, case, code, error_path):
    params = {"bk_biz_id": 2, "config": group()}
    if case == "yaml":
        params["config"] = "rules: ["
    elif case == "rules":
        params["config"]["rules"] = []
    elif case == "space":
        params["space_uid"] = "bkcc__3"
    elif case == "missing_rule":
        params["id"] = 987654
    elif case == "query":
        public_context.check_promql.side_effect = RuntimeError("query unavailable")
    elif case == "source":
        models.ResultTableConfig.objects.filter(bk_tenant_id=TENANT_ID).delete()
    response = preview_http(entry, params)
    assert response.status_code == 200
    assert response.data["result"] is False
    assert response.data["code"] == 3300004
    error = response.data["data"]["errors"][0]
    assert error["code"] == code and error["path"] == error_path
    assert error["message"]
    assert not models.RecordRuleV4.objects.exists()
    public_context.apply_data_link.assert_not_called()


@pytest.mark.parametrize("entry", ["api", "mcp", "unified"])
def test_limit_failure_is_structured_without_losing_parsed_records(preview_http, settings, entry):
    settings.RECORD_RULE_V4_CONFIG = {"max_sources": 20, "max_rules": 1}
    config = group()
    config["rules"].append({"record": "cpu_sum", "expr": "sum(system_cpu_usage)"})
    response = preview_http(entry, {"bk_biz_id": 2, "config": config})
    assert response.status_code == 200
    data = response.data["data"] if entry == "unified" else response.data
    assert len(data["records"]) == 2
    check = data["deployment_check"]
    assert not check["can_apply"]
    assert check["errors"] == [
        {
            "code": "RULE_LIMIT_EXCEEDED",
            "message": "group rule 数量 2 超过上限 1（max_rules）",
            "path": "config.rules",
            "actual": 2,
            "limit": 1,
        }
    ]


def test_preview_error_passthrough_does_not_expose_other_exception_data():
    from core.drf_resource.exceptions import CustomException
    from kernel_api.exceptions import api_exception_handler

    response = api_exception_handler(
        CustomException("upstream error", data={"errors": [{"upstream": "private"}], "raw_response": "private"}), {}
    )
    assert not response.data.get("data")
