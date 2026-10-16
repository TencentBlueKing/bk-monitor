"""BKLog callback route regression against the shared V4 protocol."""

import base64
import json
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.iam.views.resources import SpaceResourceProvider
from apps.iam.views.resources_v4 import build_resource_dispatcher
from iam_engine.core.types import AuthorizedResourceScope


class AuthorizedResourceScopeTypeTest(SimpleTestCase):
    def test_empty_factory(self):
        scope = AuthorizedResourceScope.empty("space", provider_name="v4")
        self.assertTrue(scope.ok)
        self.assertFalse(scope.is_wildcard)
        self.assertEqual(scope.ids, frozenset())


@override_settings(
    APP_CODE="callback-bklog",
    SECRET_KEY="dummy-secret",
    BK_IAM_PERMISSION_MODE="v4",
    BK_IAM_V4_SYSTEM_ID="bklog_test",
    BK_IAM_V4_APIGATEWAY_URL="https://v4.example.test/",
    BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS=0,
    BK_APP_TENANT_ID="system",
    ENABLE_MULTI_TENANT_MODE=False,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "iam-v4-callback-tests",
        }
    },
)
class V4CallbackEntryTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.dispatcher = build_resource_dispatcher()
        self.provider = self.dispatcher._provider["space"].provider
        self.token = patch("iam_engine.v4.client.V4Client.retrieve_system_auth_token", return_value="test-token")
        self.retrieve = self.token.start()
        self.addCleanup(self.token.stop)

    def request(self, body=None, **headers):
        values = {
            "HTTP_AUTHORIZATION": "Basic " + base64.b64encode(b"bk_iam:test-token").decode(),
            "HTTP_X_REQUEST_ID": "bklog-callback-test",
        }
        values.update(headers)
        body = (
            body
            if body is not None
            else {"type": "space", "method": "list_instance", "page": {"page": 1, "page_size": 10}}
        )
        response = self.dispatcher.as_view()(
            RequestFactory().post("/", json.dumps(body), content_type="application/json", **values)
        )
        return response, json.loads(response.content)

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    def test_missing_tenant_rejected_before_token_or_resource_lookup(self):
        self.provider.list_instance = Mock()
        for value in (None, "", "   "):
            headers = {} if value is None else {"HTTP_X_BK_TENANT_ID": value}
            self.assertEqual(self.request(**headers)[0].status_code, 400)
        self.retrieve.assert_not_called()
        self.provider.list_instance.assert_not_called()

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    def test_native_local_query_receives_requested_tenant_and_documented_page(self):
        with patch(
            "apps.iam.views.resources.Space.get_spaces_page",
            return_value=([{"bk_biz_id": -5423, "space_type_name": "项目", "space_name": "demo"}], 1),
        ) as query:
            response, payload = self.request(
                {
                    "type": "space",
                    "method": "list_instance",
                    "filter": {"keyword": "demo"},
                    "page": {"page": 2, "page_size": 10},
                },
                HTTP_X_BK_TENANT_ID="tenant-a",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload, {"data": {"count": 1, "results": [{"id": "neg_5423", "display_name": "[项目] demo"}]}}
        )
        self.assertEqual(response["X-Request-Id"], "bklog-callback-test")
        query.assert_called_once_with("tenant-a", offset=10, limit=10, keywords=["demo"])

    def test_native_fetch_decodes_space_ids_and_empty_ids_do_not_query(self):
        with patch(
            "apps.iam.views.resources.Space.get_spaces_by_bk_biz_ids",
            return_value=[{"bk_biz_id": -5423, "space_type_name": "项目", "space_name": "demo"}],
        ) as query:
            response, payload = self.request(
                {"type": "space", "method": "fetch_instance_info", "filter": {"ids": ["neg_5423"]}}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload["data"][0]["id"], "neg_5423")
            query.assert_called_once_with("system", ["-5423"])
            query.reset_mock()
            response, payload = self.request({"type": "space", "method": "fetch_instance_info", "filter": {"ids": []}})
            self.assertEqual(payload, {"data": []})
            query.assert_not_called()

    @override_settings(BK_IAM_PERMISSION_MODE="v3")
    def test_default_v3_does_not_call_v4_even_when_url_is_present(self):
        self.provider.list_instance = Mock()
        response, _ = self.request()
        self.assertEqual(response.status_code, 503)
        self.retrieve.assert_not_called()
        self.provider.list_instance.assert_not_called()

    @override_settings(BK_IAM_PERMISSION_MODE="union")
    def test_union_uses_v4_callback_without_v3_token(self):
        with patch("apps.iam.views.resources.Space.get_spaces_page", return_value=([], 0)):
            with patch("iam.IAM.get_token", side_effect=AssertionError("V3 callback fallback")):
                self.assertEqual(self.request()[0].status_code, 200)
        self.retrieve.assert_called_once_with("bklog_test")

    def test_invalid_mode_is_rejected_without_fallback(self):
        self.provider.list_instance = Mock()
        with override_settings(BK_IAM_PERMISSION_MODE="invalid"):
            self.assertEqual(self.request()[0].status_code, 503)
        self.retrieve.assert_not_called()
        self.provider.list_instance.assert_not_called()

    def test_unknown_methods_are_not_successful_empty_results(self):
        self.provider.list_instance = Mock()
        for method in ("unknown", "list_instance_by_policy", "search_instance", "fetch_instance_list"):
            response, payload = self.request({"method": method, "type": "space"})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(payload["error"]["code"], "NOT_FOUND")
        self.provider.list_instance.assert_not_called()

    def test_invalid_pagination_and_ids_never_query(self):
        self.provider.list_instance = Mock()
        self.provider.fetch_instance_info = Mock()
        for page in (
            None,
            {},
            [],
            {"page": 0, "page_size": 10},
            {"page": 1, "page_size": 1001},
            {"page": True, "page_size": 10},
            {"limit": 10, "offset": -1},
        ):
            self.assertEqual(
                self.request({"method": "list_instance", "type": "space", "page": page})[0].status_code, 400
            )
        for ids in (None, [1], ["1"] * 1001):
            self.assertEqual(
                self.request({"method": "fetch_instance_info", "type": "space", "filter": {"ids": ids}})[0].status_code,
                400,
            )
        self.provider.list_instance.assert_not_called()
        self.provider.fetch_instance_info.assert_not_called()

    def test_bad_auth_is_native_401_without_sdk_secret_logging(self):
        self.provider.list_instance = Mock()
        for header in ("", "Basic @@@", "Basic YWJj", "Basic " + base64.b64encode(b"bk_iam:wrong").decode()):
            self.assertEqual(self.request(HTTP_AUTHORIZATION=header)[0].status_code, 401)
        self.provider.list_instance.assert_not_called()

    def test_provider_failure_is_sanitized_and_request_id_echoed(self):
        self.provider.list_instance = Mock(side_effect=RuntimeError("secret upstream payload"))
        response, payload = self.request()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload, {"error": {"code": "INTERNAL", "message": "internal server error"}})
        self.assertEqual(response["X-Request-Id"], "bklog-callback-test")

    def test_callback_token_requests_actual_v4_url_with_tenant_and_credentials(self):
        self.retrieve.side_effect = None
        self.token.stop()
        response = Mock(status_code=200, content=b"json", text="dummy")
        response.json.return_value = {"data": {"auth_token": "test-token"}}
        with patch("requests.request", return_value=response) as send:
            with patch("apps.iam.views.resources.Space.get_spaces_page", return_value=([], 0)):
                self.assertEqual(self.request(HTTP_X_BK_TENANT_ID="tenant-a")[0].status_code, 200)
        call = send.call_args.kwargs
        self.assertEqual(call["url"], "https://v4.example.test/api/v1/open/rbac/model/systems/bklog_test/auth-token/")
        self.assertEqual(call["headers"]["X-Bk-Tenant-Id"], "tenant-a")
        auth = json.loads(call["headers"]["X-Bkapi-Authorization"])
        self.assertEqual(auth["bk_app_code"], "callback-bklog")


class NativeSpaceTenantTest(SimpleTestCase):
    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    def test_native_provider_requires_tenant(self):
        with self.assertRaisesRegex(ValueError, "bk_tenant_id is required"):
            SpaceResourceProvider._require_tenant_id({})

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    def test_native_single_tenant_fallback(self):
        self.assertEqual(SpaceResourceProvider._require_tenant_id({}), "system")

    def test_unsupported_methods_are_explicit(self):
        provider = SpaceResourceProvider()
        with self.assertRaises(NotImplementedError):
            provider.list_instance_by_policy(None, None)
