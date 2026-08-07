from django.test import SimpleTestCase, override_settings
from unittest.mock import MagicMock, patch

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
    @patch("apps.iam.views.resources_v4.Space.get_all_spaces")
    def test_list_and_search_and_fetch_use_local_space(self, get_all_spaces):
        get_all_spaces.return_value = [
            {
                "bk_biz_id": 2,
                "space_name": "蓝鲸",
                "space_type_name": "业务",
            },
            {
                "bk_biz_id": 3,
                "space_name": "其他",
                "space_type_name": "业务",
            },
        ]
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
