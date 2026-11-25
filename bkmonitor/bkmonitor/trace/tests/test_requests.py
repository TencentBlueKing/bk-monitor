"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is
distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
"""

import json
from io import BytesIO

import pytest
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse

from bkmonitor.trace.requests import requests_response_hook


@pytest.mark.parametrize(
    ("code", "stream", "expected_status"),
    [(0, False, StatusCode.OK), (91, False, StatusCode.ERROR), (91, True, StatusCode.UNSET)],
)
def test_requests_span_enrichment(monkeypatch, code, stream, expected_status):
    def send(adapter, request, **kwargs):
        raw = HTTPResponse(
            body=BytesIO(json.dumps({"code": code, "message": "fixture response", "errors": "fixture"}).encode()),
            headers={"x-bkapi-request-id": "fixture-request-id"},
            status=200,
            preload_content=False,
        )
        return adapter.build_response(request, raw)

    monkeypatch.setattr(HTTPAdapter, "send", send)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    instrumentor = RequestsInstrumentor()
    instrumentor.instrument(tracer_provider=provider, response_hook=requests_response_hook)
    try:
        with Session() as session:
            session.trust_env = False
            with session.post(
                "https://api.example.com",
                json={"metric": "fixture"},
                headers={"x-bkapi-authorization": '{"bk_username": "fixture-user", "bk_app_secret": "fixture-secret"}'},
                stream=stream,
            ) as response:
                assert response._content_consumed == (not stream)
                assert response.json()["code"] == code
        (span,) = exporter.get_finished_spans()
        assert span.status.status_code == expected_status
        assert "fixture-secret" not in str(span.attributes)
        if stream:
            assert "http.response.code" not in span.attributes
        else:
            assert span.attributes["http.response.code"] == code
            assert span.attributes["http.response.message"] == "fixture response"
            assert span.attributes["http.response.errors"] == "fixture"
            assert span.attributes["request_id"] == "fixture-request-id"
            assert span.attributes["user.username"] == "fixture-user"
            assert json.loads(span.attributes["request.body"]) == {"metric": "fixture"}
    finally:
        instrumentor.uninstrument()
        provider.shutdown()
