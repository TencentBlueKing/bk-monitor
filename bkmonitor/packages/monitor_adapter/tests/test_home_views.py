import json
from unittest import mock

from django.test import RequestFactory

from monitor_adapter.home.views import external_callback


def test_external_callback_dispatches_valid_payload_without_logger_error():
    params = {"token": "test-token", "approval_result": "approved"}
    request = RequestFactory().post(
        "/external_callback/",
        data=json.dumps(params),
        content_type="application/json",
    )

    with mock.patch("monitor_adapter.home.views.CallbackResource") as callback_resource:
        callback_resource.return_value.request.return_value = {"result": True}

        response = external_callback(request)

    assert response.status_code == 200
    assert json.loads(response.content) == {"result": True}
    callback_resource.return_value.request.assert_called_once_with(params)
