from django.test import SimpleTestCase

from apps.iam.backends.v4.client import V4Client
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

    def test_apply_url_payload_contains_url(self):
        url = self.APPLY_URL["data"]["url"]
        self.assertIn("permission/apply", url)

    def test_documented_not_found_error(self):
        payload = {
            "error": {
                "code": "NOT_FOUND",
                "message": "system(__codex_probe__) not exists",
            }
        }
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
