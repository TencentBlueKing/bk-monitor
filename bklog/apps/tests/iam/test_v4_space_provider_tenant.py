import json
from unittest.mock import MagicMock, Mock, patch

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

    def dispatch(self, method, *, page_marker=...):
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
        response = self.dispatcher._dispatch(request)
        return json.loads(response.content)

    def test_invalid_page_returns_422_without_calling_provider(self):
        invalid_pages = {
            "missing": ...,
            "null": None,
            "list": [],
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

                payload = self.dispatch("list_instance", page_marker=page)

                self.assertEqual(payload["code"], 422)
                self.assertFalse(payload["result"])
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

                payload = self.dispatch(method, page_marker={"limit": 0, "offset": 0})

                self.assertEqual(payload["code"], 422)
                getattr(self.provider, provider_method).assert_not_called()

    def test_valid_page_reaches_provider(self):
        self.provider.list_instance.return_value = ListResult(results=[], count=0)

        payload = self.dispatch("list_instance", page_marker={"limit": 10, "offset": 0})

        self.assertEqual(payload["code"], 0)
        self.provider.list_instance.assert_called_once()

    def test_numeric_string_page_preserves_sdk_compatibility(self):
        self.provider.list_instance.return_value = ListResult(results=[], count=0)

        payload = self.dispatch("list_instance", page_marker={"limit": "10", "offset": "0"})

        self.assertEqual(payload["code"], 0)
        self.provider.list_instance.assert_called_once()

    def test_non_paginated_method_does_not_require_page(self):
        self.provider.fetch_instance_info.return_value = ListResult(results=[], count=0)

        payload = self.dispatch("fetch_instance_info")

        self.assertEqual(payload["code"], 0)
        self.provider.fetch_instance_info.assert_called_once()
