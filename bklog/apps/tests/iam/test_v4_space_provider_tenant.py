import json
from unittest.mock import MagicMock, Mock, patch

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from iam.resource.provider import ListResult

from apps.iam.iam_engine.core.types import AuthorizedResourceScope
from apps.iam.views.resources_v4 import V4ResourceApiDispatcher, V4SpaceResourceProvider


class AuthorizedResourceScopeTypeTest(SimpleTestCase):
    def test_empty_factory(self):
        scope = AuthorizedResourceScope.empty("space", provider_name="v4")
        self.assertTrue(scope.ok)
        self.assertFalse(scope.is_wildcard)
        self.assertEqual(scope.ids, frozenset())


class V4SpaceProviderTenantTest(SimpleTestCase):
    @override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="system")
    def test_require_tenant_id_rejects_empty_in_multi_tenant_mode(self):
        with self.assertRaisesRegex(ValueError, "bk_tenant_id is required"):
            V4SpaceResourceProvider._require_tenant_id({"bk_tenant_id": ""})

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    def test_require_tenant_id_falls_back_when_multi_tenant_disabled(self):
        self.assertEqual(V4SpaceResourceProvider._require_tenant_id({}), "system")

    @override_settings(ENABLE_MULTI_TENANT_MODE=True, BK_APP_TENANT_ID="system")
    def test_v4_dispatcher_requires_tenant_header(self):
        dispatcher = V4ResourceApiDispatcher(iam=None, system="bk_log_search")

        class _Request:
            META = {}

            def get_full_path(self):
                return "/iam/v4/resource/"

        with self.assertRaisesRegex(ValueError, "X-Bk-Tenant-Id is required"):
            dispatcher._get_options(_Request())

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    def test_v4_dispatcher_falls_back_tenant_when_multi_tenant_disabled(self):
        dispatcher = V4ResourceApiDispatcher(iam=None, system="bk_log_search")

        class _Request:
            META = {}

        options = dispatcher._get_options(_Request())
        self.assertEqual(options["bk_tenant_id"], "system")

    def test_list_instance_by_policy_remains_empty_stub(self):
        provider = V4SpaceResourceProvider()
        result = provider.list_instance_by_policy(filter=None, page=None)
        self.assertEqual(result.count, 0)
        self.assertEqual(result.results, [])

    @override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_APP_TENANT_ID="system")
    @patch("apps.iam.views.resources_v4.Space.get_spaces_by_bk_biz_ids")
    @patch("apps.iam.views.resources_v4.Space.get_spaces_page")
    def test_list_and_search_and_fetch_use_tenant_scoped_queries(self, get_spaces_page, get_spaces_by_ids):
        space_2 = {"bk_biz_id": 2, "space_name": "蓝鲸", "space_type_name": "业务"}
        space_3 = {"bk_biz_id": 3, "space_name": "其他", "space_type_name": "业务"}
        get_spaces_page.side_effect = [([space_2], 1), ([space_3], 1)]
        get_spaces_by_ids.return_value = [space_2]
        provider = V4SpaceResourceProvider()
        page = MagicMock(slice_from=0, slice_to=10)

        list_filter = MagicMock(search={"space": ["蓝鲸"]})
        listed = provider.list_instance(list_filter, page, bk_tenant_id="system")
        self.assertEqual(listed.count, 1)
        self.assertEqual(listed.results[0]["id"], "2")

        search_filter = MagicMock(keyword="其他")
        searched = provider.search_instance(search_filter, page, bk_tenant_id="system")
        self.assertEqual(searched.count, 1)
        self.assertEqual(searched.results[0]["id"], "3")

        fetch_filter = MagicMock(ids=["2"])
        fetched = provider.fetch_instance_info(fetch_filter, bk_tenant_id="system")
        self.assertEqual(fetched.count, 1)
        self.assertEqual(fetched.results[0]["_bk_iam_approvers_"], [])
        self.assertEqual(get_spaces_page.call_args_list[0].kwargs["keywords"], ["蓝鲸"])
        self.assertEqual(get_spaces_page.call_args_list[1].kwargs["keywords"], ["其他"])
        get_spaces_by_ids.assert_called_once_with("system", ["2"])


class V4ResourceDispatcherPaginationTest(SimpleTestCase):
    def setUp(self):
        self.iam = Mock()
        self.iam.is_basic_auth_allowed.return_value = True
        self.dispatcher = V4ResourceApiDispatcher(self.iam, system="bklog_test")
        self.provider = Mock()
        self.dispatcher._provider["space"] = self.provider
        self.request_factory = RequestFactory()

    def dispatch_response(self, method, *, page_marker=...):
        body = {"method": method, "type": "space", "filter": {}}
        if method == "search_instance":
            body["filter"] = {"keyword": "ab"}
        if page_marker is not ...:
            body["page"] = page_marker
        request = self.request_factory.post(
            "/api/v1/iam/v4/resource/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION="Basic test",
            HTTP_X_REQUEST_ID="pagination-test",
        )
        return self.dispatcher._dispatch(request)

    def dispatch(self, method, *, page_marker=...):
        return json.loads(self.dispatch_response(method, page_marker=page_marker).content)

    def test_invalid_page_returns_native_400_without_calling_provider(self):
        invalid_pages = {
            "missing": ...,
            "null": None,
            "list": [],
            "documented_empty": {},
            "limit_zero": {"limit": 0, "offset": 0},
            "limit_negative": {"limit": -1, "offset": 0},
            "offset_negative": {"limit": 1, "offset": -1},
            "limit_non_numeric": {"limit": "x", "offset": 0},
            "offset_non_numeric": {"limit": 1, "offset": "x"},
            "limit_float": {"limit": 1.5, "offset": 0},
            "offset_float": {"limit": 1, "offset": 0.5},
            "limit_boolean": {"limit": True, "offset": 0},
            "offset_boolean": {"limit": 1, "offset": False},
        }

        for name, page in invalid_pages.items():
            with self.subTest(name=name):
                self.provider.reset_mock()

                response = self.dispatch_response("list_instance", page_marker=page)
                payload = json.loads(response.content)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(payload["error"]["code"], "INVALID_ARGUMENT")
                self.provider.list_instance.assert_not_called()

    def test_all_paginated_methods_validate_before_provider_call(self):
        method_to_provider_method = {
            "list_attr_value": "list_attr_value",
            "list_instance": "list_instance",
            "list_instance_by_policy": "list_instance_by_policy",
            "search_instance": "search_instance",
            "fetch_instance_list": "fetch_instance_list",
        }

        for method, provider_method in method_to_provider_method.items():
            with self.subTest(method=method):
                self.provider.reset_mock()

                response = self.dispatch_response(method, page_marker={"limit": 0, "offset": 0})
                payload = json.loads(response.content)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(payload["error"]["code"], "INVALID_ARGUMENT")
                getattr(self.provider, provider_method).assert_not_called()

    def test_valid_page_reaches_provider(self):
        self.provider.list_instance.return_value = ListResult(results=[], count=0)

        response = self.dispatch_response("list_instance", page_marker={"limit": 10, "offset": 0})
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-Id"], "pagination-test")
        self.assertEqual(payload, {"data": {"count": 0, "results": []}})
        self.provider.list_instance.assert_called_once()

    def test_numeric_string_page_preserves_sdk_compatibility(self):
        self.provider.list_instance.return_value = ListResult(results=[], count=0)

        payload = self.dispatch("list_instance", page_marker={"limit": "10", "offset": "0"})

        self.assertEqual(payload, {"data": {"count": 0, "results": []}})
        self.provider.list_instance.assert_called_once()

    def test_documented_page_page_size_is_normalized_to_sdk_pagination(self):
        self.provider.list_instance.return_value = ListResult(results=[], count=0)

        response = self.dispatch_response("list_instance", page_marker={"page": 2, "page_size": 10})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"data": {"count": 0, "results": []}})
        page = self.provider.list_instance.call_args.args[1]
        self.assertEqual(page.slice_from, 10)
        self.assertEqual(page.slice_to, 20)

    def test_invalid_documented_page_page_size_returns_native_400(self):
        invalid_pages = [
            ({"page": 0, "page_size": 10}, "page.page must be an integer greater than 0"),
            ({"page": 1, "page_size": 0}, "page.page_size must be an integer greater than 0"),
        ]

        for page, message in invalid_pages:
            with self.subTest(page=page):
                self.provider.reset_mock()
                response = self.dispatch_response("list_instance", page_marker=page)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    json.loads(response.content),
                    {"error": {"code": "INVALID_ARGUMENT", "message": message}},
                )
        self.provider.list_instance.assert_not_called()

    def test_non_paginated_method_does_not_require_page(self):
        self.provider.fetch_instance_info.return_value = ListResult(results=[], count=0)

        payload = self.dispatch("fetch_instance_info")

        self.assertEqual(payload, {"data": []})
        self.provider.fetch_instance_info.assert_called_once()

    def test_auth_failure_returns_native_401_and_echoes_request_id(self):
        self.iam.is_basic_auth_allowed.return_value = False

        response = self.dispatch_response("list_instance", page_marker={"limit": 10, "offset": 0})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["X-Request-Id"], "pagination-test")
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "UNAUTHENTICATED", "message": "basic auth failed"}},
        )
        self.provider.list_instance.assert_not_called()

    def test_invalid_json_returns_native_400(self):
        request = self.request_factory.post(
            "/api/v1/iam/v4/resource/",
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION="Basic test",
            HTTP_X_REQUEST_ID="invalid-json-test",
        )

        response = self.dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["X-Request-Id"], "invalid-json-test")
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "INVALID_ARGUMENT", "message": "request body is not a valid json"}},
        )

    def test_unknown_resource_returns_native_404(self):
        request = self.request_factory.post(
            "/api/v1/iam/v4/resource/",
            data=json.dumps(
                {
                    "method": "list_instance",
                    "type": "unknown",
                    "filter": {},
                    "page": {"limit": 10, "offset": 0},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION="Basic test",
            HTTP_X_REQUEST_ID="unknown-resource-test",
        )

        response = self.dispatcher._dispatch(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "NOT_FOUND", "message": "unsupported resource type: unknown"}},
        )

    def test_provider_exception_returns_sanitized_native_500(self):
        self.provider.list_instance.side_effect = RuntimeError("sensitive provider detail")

        response = self.dispatch_response("list_instance", page_marker={"limit": 10, "offset": 0})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "INTERNAL", "message": "internal server error"}},
        )
        self.assertNotIn("sensitive provider detail", response.content.decode())

    @patch("apps.iam.views.resources.ResourceApiDispatcher._dispatch")
    def test_malformed_legacy_response_returns_native_500(self, legacy_dispatch):
        legacy_dispatch.return_value = HttpResponse("not-json", headers={"X-Request-Id": "malformed-response-test"})

        response = self.dispatcher._dispatch(Mock())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["X-Request-Id"], "malformed-response-test")
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "INTERNAL", "message": "internal server error"}},
        )

    @patch("apps.iam.views.resources.ResourceApiDispatcher._dispatch")
    def test_invalid_legacy_error_code_returns_native_500(self, legacy_dispatch):
        legacy_dispatch.return_value = JsonResponse(
            {"code": "invalid", "result": False, "message": "sensitive legacy detail", "data": None}
        )

        response = self.dispatcher._dispatch(Mock())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "INTERNAL", "message": "internal server error"}},
        )
