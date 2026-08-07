from http import HTTPStatus
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import V4RateLimitError, V4ResponseError, V4TimeoutError, V4TransportError


@override_settings(APP_CODE="bk_log_search", SECRET_KEY="secret")
class V4ClientTest(SimpleTestCase):
    def setUp(self):
        self.client = V4Client(
            V4Options(
                app_code="bk_log_search",
                app_secret="secret",
                gateway_url="https://iam.example/",
                system_id="bk_log_search",
                timeout_seconds=1,
                batch_chunk_size=100,
                auth_path="api/v1/open/rbac/authorization/systems/{system_id}/auth/",
                auth_by_resources_path="api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/",
                apply_url_path="api/v1/open/application/permission-apply-urls/",
            ),
            username="admin",
            bk_tenant_id="tenant-1",
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_timeout_is_mapped_to_v4_timeout_error(self, request_mock):
        request_mock.side_effect = requests.Timeout("timeout")

        with self.assertRaises(V4TimeoutError):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_missing_gateway_is_reported_before_http_request(self, request_mock):
        self.client.options = V4Options(
            app_code="bk_log_search",
            app_secret="secret",
            gateway_url="",
            system_id="bk_log_search",
            timeout_seconds=1,
            batch_chunk_size=100,
            auth_path="api/v1/open/rbac/authorization/systems/{system_id}/auth/",
            auth_by_resources_path="api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/",
            apply_url_path="api/v1/open/application/permission-apply-urls/",
        )

        with self.assertLogs("iam.v4.client", level="ERROR") as logs:
            with self.assertRaisesRegex(V4TransportError, "BKAPP_IAM_V4_API_BASE_URL"):
                self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

        self.assertEqual(len(logs.output), 1)
        request_mock.assert_not_called()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_rate_limit_is_mapped_to_v4_rate_limit_error(self, request_mock):
        response = Mock(status_code=HTTPStatus.TOO_MANY_REQUESTS, content=b'{"error":{"code":"RATE_LIMIT"}}')
        response.json.return_value = {"error": {"code": "RATE_LIMIT", "message": "too many requests"}}
        request_mock.return_value = response

        with self.assertRaises(V4RateLimitError):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_missing_allowed_field_is_invalid_response(self, request_mock):
        response = Mock(status_code=200, content=b"{}")
        response.json.return_value = {"data": {}}
        request_mock.return_value = response

        with self.assertRaises(V4ResponseError):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_apply_url_requires_non_empty_url(self, request_mock):
        response = Mock(status_code=200, content=b"{}")
        response.json.return_value = {"data": {}}
        request_mock.return_value = response

        with self.assertRaises(V4ResponseError):
            self.client.generate_perm_apply_url(permissions=[])
