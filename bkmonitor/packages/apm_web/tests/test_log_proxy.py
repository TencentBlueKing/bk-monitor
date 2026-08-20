"""APM 日志平台代理测试。"""

import json
from collections.abc import Iterator
from unittest import mock

import pytest
import requests
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.test import RequestFactory, override_settings

from apm_web.log_proxy.views import BkLogForwardingView, LOG_STREAM_CHUNK_SIZE


def build_upstream_response(
    *,
    content: bytes = b"",
    content_type: str = "application/json",
    json_data: dict | None = None,
    status_code: int = 200,
) -> mock.Mock:
    response: mock.Mock = mock.Mock(spec=requests.Response)
    response.content = content
    response.headers = {"Content-Type": content_type}
    response.json.return_value = json_data
    response.status_code = status_code
    return response


def test_construct_response_streams_ndjson_and_closes_upstream() -> None:
    upstream_response: mock.Mock = build_upstream_response(
        content_type="application/x-ndjson; charset=utf-8",
        status_code=206,
    )
    chunks: list[bytes] = [b'{"event":"meta"}\n', b'{"event":"done"}\n']
    upstream_response.headers.update(
        {
            "Cache-Control": "no-cache",
            "Content-Encoding": "gzip",
            "Content-Length": "1024",
            "X-Accel-Buffering": "no",
        }
    )
    upstream_response.iter_content.return_value = iter(chunks)

    response = BkLogForwardingView._construct_response(upstream_response)

    assert isinstance(response, StreamingHttpResponse)
    assert response.status_code == 206
    assert response["Content-Type"] == "application/x-ndjson; charset=utf-8"
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"
    assert "Content-Encoding" not in response
    assert "Content-Length" not in response
    assert b"".join(response.streaming_content) == b"".join(chunks)
    upstream_response.iter_content.assert_called_once_with(chunk_size=LOG_STREAM_CHUNK_SIZE)
    upstream_response.close.assert_called()


def test_closing_streaming_response_closes_unconsumed_upstream() -> None:
    upstream_response: mock.Mock = build_upstream_response(content_type="application/x-ndjson")

    response = BkLogForwardingView._construct_response(upstream_response)
    with mock.patch("django.http.response.signals.request_finished.send"):
        response.close()

    upstream_response.iter_content.assert_not_called()
    upstream_response.close.assert_called_once_with()


def test_streaming_response_closes_upstream_when_read_fails() -> None:
    upstream_response: mock.Mock = build_upstream_response(content_type="application/x-ndjson")

    def broken_chunks() -> Iterator[bytes]:
        yield b'{"event":"meta"}\n'
        raise requests.ConnectionError("broken stream")

    upstream_response.iter_content.return_value = broken_chunks()

    response = BkLogForwardingView._construct_response(upstream_response)

    with pytest.raises(requests.ConnectionError, match="broken stream"):
        b"".join(response.streaming_content)
    upstream_response.close.assert_called()


def test_construct_response_keeps_json_error_response() -> None:
    payload: dict[str, object] = {"data": None, "message": "search failed", "result": False}
    upstream_response: mock.Mock = build_upstream_response(json_data=payload, status_code=400)

    response = BkLogForwardingView._construct_response(upstream_response)

    assert isinstance(response, JsonResponse)
    assert not response.streaming
    assert response.status_code == 400
    assert json.loads(response.content) == payload
    upstream_response.json.assert_called_once_with()
    upstream_response.iter_content.assert_not_called()
    upstream_response.close.assert_called_once_with()


def test_construct_response_closes_upstream_when_json_read_fails() -> None:
    upstream_response: mock.Mock = build_upstream_response()
    upstream_response.json.side_effect = requests.ConnectionError("broken json response")

    with pytest.raises(requests.ConnectionError, match="broken json response"):
        BkLogForwardingView._construct_response(upstream_response)

    upstream_response.close.assert_called_once_with()


def test_construct_response_keeps_attachment_response() -> None:
    upstream_response: mock.Mock = build_upstream_response(
        content=b"exported logs",
        content_type="application/octet-stream",
    )
    upstream_response.headers["Content-Disposition"] = 'attachment; filename="logs.txt"'

    response = BkLogForwardingView._construct_response(upstream_response)

    assert isinstance(response, HttpResponse)
    assert not response.streaming
    assert response.content == b"exported logs"
    assert response["Content-Type"] == "application/octet-stream"
    assert response["Content-Disposition"] == 'attachment; filename="logs.txt"'
    upstream_response.json.assert_not_called()
    upstream_response.iter_content.assert_not_called()
    upstream_response.close.assert_called_once_with()


def test_construct_response_closes_upstream_when_attachment_read_fails() -> None:
    upstream_response: mock.Mock = build_upstream_response(content_type="application/octet-stream")
    upstream_response.headers["Content-Disposition"] = 'attachment; filename="logs.txt"'

    with mock.patch.object(type(upstream_response), "content", new_callable=mock.PropertyMock, create=True) as content:
        content.side_effect = requests.ConnectionError("broken attachment response")
        with pytest.raises(requests.ConnectionError, match="broken attachment response"):
            BkLogForwardingView._construct_response(upstream_response)

    upstream_response.close.assert_called_once_with()


@override_settings(BKLOGSEARCH_INNER_HOST="https://bklog.example/", APP_CODE="bk_monitor")
@pytest.mark.parametrize("query_string", ["", "?stream=true"])
def test_dispatch_supports_json_response_and_enables_upstream_streaming(query_string: str) -> None:
    upstream_response: mock.Mock = build_upstream_response(json_data={"data": [], "result": True})
    request = RequestFactory().post(
        f"/apm_log_forward/bklog/api/v1/search/index_set/291/search/{query_string}",
        data={"keyword": "error"},
        content_type="application/json",
    )

    with mock.patch("apm_web.log_proxy.views.requests.request", return_value=upstream_response) as request_mock:
        response = BkLogForwardingView().dispatch(request)

    assert isinstance(response, JsonResponse)
    assert json.loads(response.content) == {"data": [], "result": True}
    request_kwargs: dict[str, object] = request_mock.call_args.kwargs
    assert request_kwargs["url"] == "https://bklog.example/api/v1/search/index_set/291/search/"
    assert request_kwargs["params"] == ({"stream": "true"} if query_string else {})
    assert request_kwargs["stream"] is True
    assert request_kwargs["headers"]["X-SOURCE-APP-CODE"] == "bk_monitor"


@override_settings(BKLOGSEARCH_INNER_HOST="https://bklog.example/", APP_CODE="bk_monitor")
def test_dispatch_forwards_ndjson_response_as_stream() -> None:
    upstream_response: mock.Mock = build_upstream_response(content_type="application/x-ndjson; charset=utf-8")
    chunks: list[bytes] = [b'{"event":"meta","total":1}\n', b'{"event":"done"}\n']
    upstream_response.iter_content.return_value = iter(chunks)
    request = RequestFactory().post(
        "/apm_log_forward/bklog/api/v1/search/index_set/291/search/?stream=true",
        data={"keyword": "error"},
        content_type="application/json",
    )

    with mock.patch("apm_web.log_proxy.views.requests.request", return_value=upstream_response):
        response = BkLogForwardingView().dispatch(request)

    assert isinstance(response, StreamingHttpResponse)
    assert response["Content-Type"] == "application/x-ndjson; charset=utf-8"
    assert b"".join(response.streaming_content) == b"".join(chunks)
    upstream_response.close.assert_called()
