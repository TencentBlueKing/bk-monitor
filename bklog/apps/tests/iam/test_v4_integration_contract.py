from http import HTTPStatus
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.config import V4Options
from apps.iam.backends.v4.exceptions import V4ResponseError


class V4IntegrationContractTest(SimpleTestCase):
    """记录来自 iWiki 4029395141 的 IAM V4 契约样例，用于评审和回归测试。"""

    DIRECT_AUTH_ALLOW = {
        "data": {"allowed": True},
        "request_id": "809e3179-2a2d-4b63-8465-c01899476cc9",
    }
    DIRECT_AUTH_DENY = {
        "data": {"allowed": False},
        "request_id": "809e3179-2a2d-4b63-8465-c01899476cc9",
    }
    DIRECT_AUTH_INVALID = {"error": {"code": "INVALID_REQUEST", "message": " action(execute_job) not found"}}
    AUTH_BY_RESOURCES = {
        "data": [
            {"resource_id": "28", "allowed": True},
            {"resource_id": "29", "allowed": False},
        ],
        "request_id": "4e40b6b6-ba84-4256-adfb-8593981e6405",
    }
    APPLY_URL = {"data": {"url": "https://bkiam.woa.com/permission/apply?cache_id=<cache_id>&system_id=bk_log_search"}}

    def setUp(self):
        self.client = V4Client(
            V4Options(
                app_code="bk_log_search",
                app_secret="secret",
                gateway_url="https://bkiam.example/",
                system_id="bk_log_search",
                timeout_seconds=1,
                batch_chunk_size=20,
                auth_path="api/v1/open/rbac/authorization/systems/{system_id}/auth/",
                auth_by_resources_path="api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/",
                apply_url_path="api/v1/open/application/permission-apply-urls/",
            ),
            username="admin",
            bk_tenant_id="tenant-1",
        )

    def test_direct_auth_allow_shape(self):
        allowed = V4Client._extract_allowed(self.DIRECT_AUTH_ALLOW["data"])
        self.assertTrue(allowed)

    def test_direct_auth_deny_shape(self):
        allowed = V4Client._extract_allowed(self.DIRECT_AUTH_DENY["data"])
        self.assertFalse(allowed)

    def test_auth_by_resources_shape(self):
        results = V4Client._extract_resource_results(
            self.AUTH_BY_RESOURCES["data"],
            expected_resource_ids=["28", "29"],
        )
        self.assertEqual(results, {"28": True, "29": False})

    def test_missing_batch_item_is_error_not_deny(self):
        with self.assertRaises(V4ResponseError):
            V4Client._extract_resource_results(
                [{"resource_id": "28", "allowed": True}],
                expected_resource_ids=["28", "29"],
            )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_apply_url_response_is_parsed_by_client(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"apply-url")
        response.json.return_value = self.APPLY_URL
        request_mock.return_value = response

        url = self.client.generate_perm_apply_url(permissions=[])

        self.assertEqual(url, self.APPLY_URL["data"]["url"])

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_apply_url_response_without_url_is_rejected(self, request_mock):
        response = Mock(status_code=HTTPStatus.OK, content=b"missing-url")
        response.json.return_value = {"data": {}}
        request_mock.return_value = response

        with self.assertRaisesRegex(V4ResponseError, "missing url"):
            self.client.generate_perm_apply_url(permissions=[])

    def test_documented_not_found_error(self):
        response = Mock(text="")
        response.json.return_value = {
            "error": {
                "code": "NOT_FOUND",
                "message": "system(__codex_probe__) not exists",
            }
        }

        self.assertEqual(
            self.client._extract_error_reason(response),
            "system(__codex_probe__) not exists",
        )
