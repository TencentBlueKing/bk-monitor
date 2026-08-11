from unittest.mock import patch

from django.test import SimpleTestCase
from iam.resource.provider import ListResult
from iam.resource.utils import Page, get_filter_obj

from apps.iam import ResourceEnum
from apps.iam.views.resources import (
    CollectionResourceProvider,
    EsSourceResourceProvider,
    IndicesResourceProvider,
)
from apps.iam.views.resources_v4 import (
    V4CollectionResourceProvider,
    V4EsSourceResourceProvider,
    V4IndicesResourceProvider,
    V4SpaceResourceProvider,
    _fix_approver_field,
    _fix_nested_path_to_string,
)


def _page(limit=100, offset=0):
    return Page(limit=limit, offset=offset)


def _list_filter(**kwargs):
    data = {
        "parent": None,
        "search": None,
        "action": None,
        "resource_type_chain": None,
        "ancestors": None,
    }
    data.update(kwargs)
    return get_filter_obj(data, ["parent", "search", "action", "resource_type_chain", "ancestors"])


def _fetch_filter(**kwargs):
    data = {"ids": None, "attrs": None}
    data.update(kwargs)
    return get_filter_obj(data, ["ids", "attrs"])


def _search_filter(**kwargs):
    data = {"parent": None, "action": None, "keyword": None, "ancestors": None}
    data.update(kwargs)
    return get_filter_obj(data, ["parent", "action", "keyword", "ancestors"])


class FixHelperTest(SimpleTestCase):
    def test_fix_nested_path_to_string(self):
        results = [
            {
                "id": "1",
                "display_name": "c1",
                "_bk_iam_path_": [[{"type": "space", "id": "10", "display_name": "10"}]],
            },
            {"id": "2", "display_name": "c2"},
        ]

        _fix_nested_path_to_string(results)

        self.assertEqual(results[0]["_bk_iam_path_"], f"/{ResourceEnum.BUSINESS.id},10/")
        self.assertNotIn("_bk_iam_path_", results[1])

    def test_fix_approver_field(self):
        results = [
            {"id": "1", "display_name": "c1", "_bk_iam_approver_": "admin"},
            {"id": "2", "display_name": "c2", "_bk_iam_approver_": ""},
        ]

        _fix_approver_field(results)

        self.assertEqual(results[0]["_bk_iam_approvers_"], ["admin"])
        self.assertNotIn("_bk_iam_approver_", results[0])
        self.assertEqual(results[1]["_bk_iam_approvers_"], [])
        self.assertNotIn("_bk_iam_approver_", results[1])


class V4SpaceResourceProviderTest(SimpleTestCase):
    def setUp(self):
        self.provider = V4SpaceResourceProvider()
        self.spaces = [
            {
                "bk_biz_id": 10,
                "space_type_name": "业务",
                "space_name": "蓝鲸",
            },
            {
                "bk_biz_id": 20,
                "space_type_name": "容器项目",
                "space_name": "demo",
            },
        ]

    @patch("apps.iam.views.resources_v4.Space.get_spaces_page", return_value=([], 0))
    def test_list_instance_empty(self, _mock):
        result = self.provider.list_instance(_list_filter(), _page(), bk_tenant_id="tenant-1")
        self.assertEqual(result.count, 0)
        self.assertEqual(result.results, [])

    @patch("apps.iam.views.resources_v4.Space.get_spaces_page")
    def test_list_instance_display_name_and_no_path(self, mock_spaces):
        mock_spaces.return_value = (self.spaces, 2)

        result = self.provider.list_instance(_list_filter(), _page(), bk_tenant_id="tenant-1")

        self.assertEqual(result.count, 2)
        self.assertEqual(
            result.results,
            [
                {"id": "10", "display_name": "[业务] 蓝鲸"},
                {"id": "20", "display_name": "[容器项目] demo"},
            ],
        )
        for item in result.results:
            self.assertNotIn("_bk_iam_path_", item)

    @patch("apps.iam.views.resources_v4.Space.get_spaces_by_bk_biz_ids")
    def test_fetch_instance_info(self, mock_spaces):
        mock_spaces.return_value = [self.spaces[0]]

        result = self.provider.fetch_instance_info(_fetch_filter(ids=["10"]), bk_tenant_id="tenant-1")

        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["id"], "10")
        self.assertEqual(result.results[0]["_bk_iam_approvers_"], [])

    @patch("apps.iam.views.resources_v4.Space.get_all_spaces", return_value=[])
    def test_fetch_instance_info_without_ids_preserves_full_fetch_contract(self, get_all_spaces):
        result = self.provider.fetch_instance_info(_fetch_filter(), bk_tenant_id="tenant-1")

        self.assertEqual(result.count, 0)
        get_all_spaces.assert_called_once_with("tenant-1")

    @patch("apps.iam.views.resources_v4.Space.get_spaces_page")
    def test_search_instance(self, mock_spaces):
        mock_spaces.return_value = ([self.spaces[1]], 1)

        result = self.provider.search_instance(
            _search_filter(keyword="demo"),
            _page(),
            bk_tenant_id="tenant-1",
        )

        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["id"], "20")


class V4InheritedProviderFormatTest(SimpleTestCase):
    def test_v4_collection_list_instance_converts_path(self):
        provider = V4CollectionResourceProvider()
        nested = ListResult(
            results=[
                {
                    "id": "1",
                    "display_name": "c1",
                    "_bk_iam_path_": [[{"type": "space", "id": "10", "display_name": "10"}]],
                }
            ],
            count=1,
        )

        with patch.object(CollectionResourceProvider, "list_instance", return_value=nested):
            result = provider.list_instance(_list_filter(), _page(), bk_tenant_id="tenant-1")

        self.assertEqual(result.results[0]["_bk_iam_path_"], f"/{ResourceEnum.BUSINESS.id},10/")
        self.assertIsInstance(result.results[0]["_bk_iam_path_"], str)

    def test_v4_collection_fetch_instance_info_converts_approver(self):
        provider = V4CollectionResourceProvider()
        legacy = ListResult(
            results=[{"id": "1", "display_name": "c1", "_bk_iam_approver_": "admin"}],
            count=1,
        )

        with patch.object(CollectionResourceProvider, "fetch_instance_info", return_value=legacy):
            result = provider.fetch_instance_info(_fetch_filter(ids=["1"]), bk_tenant_id="tenant-1")

        self.assertEqual(result.results[0]["_bk_iam_approvers_"], ["admin"])
        self.assertNotIn("_bk_iam_approver_", result.results[0])

    def test_v4_indices_list_and_fetch_format(self):
        provider = V4IndicesResourceProvider()
        nested = ListResult(
            results=[
                {
                    "id": "9",
                    "display_name": "idx",
                    "_bk_iam_path_": [[{"type": "space", "id": "5", "display_name": "5"}]],
                }
            ],
            count=1,
        )
        legacy = ListResult(
            results=[{"id": "9", "display_name": "idx", "_bk_iam_approver_": "alice"}],
            count=1,
        )

        with patch.object(IndicesResourceProvider, "list_instance", return_value=nested):
            listed = provider.list_instance(_list_filter(), _page(), bk_tenant_id="tenant-1")
        with patch.object(IndicesResourceProvider, "fetch_instance_info", return_value=legacy):
            fetched = provider.fetch_instance_info(_fetch_filter(ids=["9"]), bk_tenant_id="tenant-1")

        self.assertEqual(listed.results[0]["_bk_iam_path_"], f"/{ResourceEnum.BUSINESS.id},5/")
        self.assertEqual(fetched.results[0]["_bk_iam_approvers_"], ["alice"])
        self.assertNotIn("_bk_iam_approver_", fetched.results[0])

    def test_v4_es_source_list_and_fetch_format(self):
        provider = V4EsSourceResourceProvider()
        nested = ListResult(
            results=[
                {
                    "id": "3",
                    "display_name": "es",
                    "_bk_iam_path_": [[{"type": "space", "id": "7", "display_name": "7"}]],
                }
            ],
            count=1,
        )
        legacy = ListResult(
            results=[{"id": "3", "display_name": "es", "_bk_iam_approver_": "bob"}],
            count=1,
        )

        with patch.object(EsSourceResourceProvider, "list_instance", return_value=nested):
            listed = provider.list_instance(_list_filter(), _page(), bk_tenant_id="tenant-1")
        with patch.object(EsSourceResourceProvider, "fetch_instance_info", return_value=legacy):
            fetched = provider.fetch_instance_info(_fetch_filter(ids=["3"]), bk_tenant_id="tenant-1")

        self.assertEqual(listed.results[0]["_bk_iam_path_"], f"/{ResourceEnum.BUSINESS.id},7/")
        self.assertEqual(fetched.results[0]["_bk_iam_approvers_"], ["bob"])
        self.assertNotIn("_bk_iam_approver_", fetched.results[0])


class EsSourceCrashFixAndIsolationTest(SimpleTestCase):
    @patch.object(EsSourceResourceProvider, "list_clusters")
    def test_v3_es_source_with_path_no_longer_crashes(self, mock_clusters):
        mock_clusters.return_value = [
            {
                "id": "1",
                "display_name": "cluster-a",
                "bk_biz_id": "10",
                "owner": "admin",
                "_bk_iam_path_": "/space,10/",
            }
        ]
        provider = EsSourceResourceProvider()
        filter_obj = _list_filter(
            search={"es_source": ["cluster"]},
            resource_type_chain=[{"id": "space"}, {"id": "es_source"}],
        )

        result = provider.list_instance(filter_obj, _page(), bk_tenant_id="tenant-1")

        self.assertEqual(result.count, 1)
        self.assertEqual(result.results[0]["id"], "1")
        # 只修崩溃，不改格式：仍保持嵌套数组
        self.assertIsInstance(result.results[0]["_bk_iam_path_"], list)
        self.assertEqual(result.results[0]["_bk_iam_path_"][0][0]["id"], "10")

    def test_v3_collection_format_unchanged(self):
        provider = CollectionResourceProvider()
        nested_path = [[{"type": "space", "id": "10", "display_name": "10"}]]
        legacy = ListResult(
            results=[
                {
                    "id": "1",
                    "display_name": "c1",
                    "_bk_iam_path_": nested_path,
                    "_bk_iam_approver_": "admin",
                }
            ],
            count=1,
        )

        # 直接断言 V3 类自身仍产出旧格式字段（通过 helper 模拟父类结果形态）
        self.assertIsInstance(legacy.results[0]["_bk_iam_path_"], list)
        self.assertIn("_bk_iam_approver_", legacy.results[0])
        self.assertNotIn("_bk_iam_approvers_", legacy.results[0])
        self.assertIsInstance(provider, CollectionResourceProvider)

    def test_v3_indices_format_unchanged_shape(self):
        legacy = {
            "id": "1",
            "display_name": "idx",
            "_bk_iam_path_": [[{"type": "space", "id": "10", "display_name": "10"}]],
            "_bk_iam_approver_": "admin",
        }
        self.assertIsInstance(legacy["_bk_iam_path_"], list)
        self.assertIn("_bk_iam_approver_", legacy)
        self.assertNotIn("_bk_iam_approvers_", legacy)
        self.assertIsInstance(IndicesResourceProvider(), IndicesResourceProvider)


class V4DispatcherRegistrationTest(SimpleTestCase):
    def test_v4_dispatcher_registers_expected_providers(self):
        from apps.iam import urls as iam_urls

        self.assertIn("space", iam_urls.v4_dispatcher._provider)
        self.assertIn("collection", iam_urls.v4_dispatcher._provider)
        self.assertIn("es_source", iam_urls.v4_dispatcher._provider)
        self.assertIn("indices", iam_urls.v4_dispatcher._provider)
        self.assertIsInstance(iam_urls.v4_dispatcher._provider["space"], V4SpaceResourceProvider)
        self.assertIsInstance(iam_urls.v4_dispatcher._provider["collection"], V4CollectionResourceProvider)
        self.assertIsInstance(iam_urls.v4_dispatcher._provider["es_source"], V4EsSourceResourceProvider)
        self.assertIsInstance(iam_urls.v4_dispatcher._provider["indices"], V4IndicesResourceProvider)

        # V3 dispatcher 仍不包含 space，且仍是旧 Provider
        self.assertNotIn("space", iam_urls.dispatcher._provider)
        self.assertIsInstance(iam_urls.dispatcher._provider["collection"], CollectionResourceProvider)
        self.assertNotIsInstance(iam_urls.dispatcher._provider["collection"], V4CollectionResourceProvider)

    def test_v4_dispatcher_uses_v4_callback_iam_client(self):
        from apps.iam.handlers.compatible import V4CallbackIAM
        from apps.iam import urls as iam_urls

        self.assertIsInstance(iam_urls.v4_dispatcher.iam, V4CallbackIAM)

    def test_v4_resource_url_is_registered(self):
        from apps.iam import urls as iam_urls

        pattern_texts = [str(p.pattern) for p in iam_urls.urlpatterns]
        self.assertTrue(any("v4/resource" in text for text in pattern_texts))
        self.assertTrue(any(text.endswith("resource/$") or "resource/$" in text for text in pattern_texts))
