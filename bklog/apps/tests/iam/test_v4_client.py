import json
from http import HTTPStatus
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import (
    V4ClientError,
    V4RateLimitError,
    V4ResponseError,
    V4TimeoutError,
    V4TransportError,
)


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
    def test_missing_tenant_is_rejected_before_http_request(self, request_mock):
        self.client.bk_tenant_id = "  "

        with self.assertRaisesRegex(V4TransportError, "non-empty bk_tenant_id"):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

        request_mock.assert_not_called()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_request_headers_use_explicit_client_credentials_and_tenant(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b'{"data":{"allowed":true}}')
        response.json.return_value = {"data": {"allowed": True}}
        request_mock.return_value = response

        self.assertTrue(self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection"))

        headers = request_mock.call_args.kwargs["headers"]
        self.assertEqual(
            json.loads(headers["X-Bkapi-Authorization"]),
            {
                "bk_app_code": "bk_log_search",
                "bk_app_secret": "secret",
                "bk_username": "admin",
            },
        )
        self.assertEqual(headers["X-Bk-Tenant-Id"], "tenant-1")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_direct_auth_sends_resource_when_provided(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"auth")
        response.json.return_value = {"data": {"allowed": True}}
        request_mock.return_value = response
        resource = {"id": "1", "attributes": {"_bk_iam_path_": "/space,10/"}}

        self.assertTrue(
            self.client.direct_auth(
                subject={"type": "user", "id": "admin"},
                action_id="view_collection",
                resource=resource,
            )
        )

        self.assertEqual(request_mock.call_args.kwargs["json"]["resource"], resource)

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_auth_sends_resources_and_parses_results(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"batch")
        response.json.return_value = {
            "data": [
                {"resource_id": "1", "allowed": True},
                {"resource_id": "2", "allowed": False},
            ]
        }
        request_mock.return_value = response
        resources = [{"id": "1"}, {"id": "2"}]

        result = self.client.direct_auth_by_resources(
            subject={"type": "user", "id": "admin"},
            action_id="view_collection",
            resources=resources,
        )

        self.assertEqual(result, {"1": True, "2": False})
        self.assertEqual(request_mock.call_args.kwargs["json"]["resources"], resources)

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

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_transport_error_is_mapped_to_v4_transport_error(self, request_mock):
        request_mock.side_effect = requests.ConnectionError("connection refused")

        with self.assertRaisesRegex(V4TransportError, "connection refused"):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_non_success_response_uses_structured_error_message(self, request_mock):
        response = Mock(status_code=HTTPStatus.BAD_REQUEST, content=b'{"error":{"message":"action not found"}}')
        response.json.return_value = {"error": {"message": "action not found"}}
        request_mock.return_value = response

        with self.assertRaisesRegex(V4ClientError, "action not found"):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="missing")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_invalid_json_response_is_rejected(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"not-json", text="not-json")
        response.json.side_effect = ValueError("invalid json")
        request_mock.return_value = response

        with self.assertRaisesRegex(V4ResponseError, "not valid JSON"):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    def test_batch_response_rejects_duplicate_resource(self):
        with self.assertRaisesRegex(V4ResponseError, "duplicate"):
            self.client._extract_resource_results(
                [
                    {"resource_id": "1", "allowed": True},
                    {"resource_id": "1", "allowed": False},
                ],
                expected_resource_ids=["1"],
            )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_no_content_response_is_not_treated_as_json(self, request_mock):
        request_mock.return_value = Mock(status_code=HTTPStatus.NO_CONTENT, content=b"")

        self.assertIsNone(self.client._request("POST", "/empty"))

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_success_response_with_error_body_is_rejected(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"error")
        response.json.return_value = {"error": {"message": "permission model unavailable"}}
        request_mock.return_value = response

        with self.assertRaisesRegex(V4ClientError, "permission model unavailable"):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_success_response_without_data_is_rejected(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"missing-data")
        response.json.return_value = {"request_id": "request-1"}
        request_mock.return_value = response

        with self.assertRaisesRegex(V4ResponseError, "missing data field"):
            self.client.direct_auth(subject={"type": "user", "id": "admin"}, action_id="view_collection")

    def test_apply_url_response_must_be_an_object(self):
        with patch.object(self.client, "_request", return_value=[]) as request_mock:
            with self.assertRaisesRegex(V4ResponseError, "must be an object"):
                self.client.generate_perm_apply_url(permissions=[])

        request_mock.assert_called_once()

    def test_allowed_value_must_be_boolean(self):
        with self.assertRaisesRegex(V4ResponseError, "must be boolean"):
            self.client._extract_allowed({"allowed": 1})

    def test_batch_response_must_be_a_list(self):
        with self.assertRaisesRegex(V4ResponseError, "must be a list"):
            self.client._extract_resource_results({}, expected_resource_ids=[])

    def test_batch_item_must_be_an_object(self):
        with self.assertRaisesRegex(V4ResponseError, "must be an object"):
            self.client._extract_resource_results(["invalid"], expected_resource_ids=[])

    def test_batch_item_requires_resource_id_and_boolean_allowed(self):
        with self.assertRaisesRegex(V4ResponseError, "missing resource_id/allowed"):
            self.client._extract_resource_results(
                [{"resource_id": "1", "allowed": "yes"}],
                expected_resource_ids=["1"],
            )

    def test_plain_text_error_reason_is_preserved(self):
        response = Mock(text="gateway unavailable")
        response.json.side_effect = ValueError("not json")

        self.assertEqual(self.client._extract_error_reason(response), "gateway unavailable")

    def test_top_level_error_message_is_preserved(self):
        response = Mock(text="")
        response.json.return_value = {"message": "invalid request"}

        self.assertEqual(self.client._extract_error_reason(response), "invalid request")

    def test_non_object_error_payload_falls_back_to_response_text(self):
        response = Mock(text="upstream failed")
        response.json.return_value = ["unexpected"]

        self.assertEqual(self.client._extract_error_reason(response), "upstream failed")
