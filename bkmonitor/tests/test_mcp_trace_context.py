"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework.response import Response

from bkmonitor.middlewares.request_middlewares import RequestProvider
from bkmonitor.utils.local import local
from bkmonitor.utils.request import ensure_mcp_trace_context
from kernel_api.adapters import ApiRenderer

TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture(autouse=True)
def clean_request_local():
    local.clear()
    yield
    local.clear()


def make_mcp_request(traceparent=None):
    headers = {"HTTP_X_BKAPI_MCP_SERVER_NAME": "bkmonitorv3-prod-metrics-query"}
    if traceparent:
        headers["HTTP_TRACEPARENT"] = traceparent
    request = RequestFactory().post("/api/v4/metrics/list_time_series_groups/", **headers)
    local.current_request = request
    return request


def test_mcp_trace_context_reuses_incoming_traceparent():
    traceparent = "00-11111111111111111111111111111111-2222222222222222-01"
    request = make_mcp_request(traceparent)

    trace_id = ensure_mcp_trace_context(request)

    assert trace_id == "11111111111111111111111111111111"
    assert request.META["HTTP_TRACEPARENT"] == traceparent


def test_mcp_trace_context_generates_traceparent_when_missing():
    request = make_mcp_request()

    trace_id = ensure_mcp_trace_context(request)

    assert TRACE_ID_RE.match(trace_id)
    assert request.META["HTTP_TRACEPARENT"].startswith(f"00-{trace_id}-")


def test_api_renderer_adds_trace_id_only_for_mcp_request():
    mcp_request = make_mcp_request("00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01")
    normal_request = RequestFactory().post("/api/v4/metrics/list_time_series_groups/")

    mcp_result = ApiRenderer().get_result({"ok": 1}, {"response": Response(status=200), "request": mcp_request})
    normal_result = ApiRenderer().get_result({"ok": 1}, {"response": Response(status=200), "request": normal_request})

    assert mcp_result["trace_id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert mcp_result["data"] == {"ok": 1}
    assert "trace_id" not in normal_result
    assert normal_result["data"] == {"ok": 1}


def test_request_provider_adds_mcp_trace_headers(monkeypatch):
    monkeypatch.setattr("bkmonitor.middlewares.request_middlewares.push_event", lambda request: None)
    request = make_mcp_request("00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01")
    ensure_mcp_trace_context(request)

    response = RequestProvider().process_response(request, HttpResponse())

    assert response["X-Bk-Trace-Id"] == "cccccccccccccccccccccccccccccccc"
    assert response["X-Bkapi-Trace-Id"] == "cccccccccccccccccccccccccccccccc"
    assert response["Traceparent"] == "00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01"
