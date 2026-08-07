from django.test import SimpleTestCase
from unittest.mock import patch

from apps.iam.handlers.scope import (
    build_iam_path,
    filter_items_by_space_ownership,
    filter_nested_items_by_action_permission,
    filter_nested_items_by_space_ownership,
    resolve_collection_bk_biz_id,
    resolve_es_source_bk_biz_id,
    resolve_indices_bk_biz_id,
    resolve_request_bk_biz_id,
    resource_belongs_to_space,
)


class ScopeOwnershipHelpersTest(SimpleTestCase):
    def test_resolve_indices_from_space_uid(self):
        self.assertEqual(resolve_indices_bk_biz_id(space_uid="bkcc__2"), "2")

    def test_resolve_indices_from_index_set_object(self):
        index_set = type("IndexSet", (), {"space_uid": "bkcc__8"})()
        self.assertEqual(resolve_indices_bk_biz_id(index_set=index_set), "8")

    def test_resolve_indices_from_bk_biz_id_fallback(self):
        self.assertEqual(resolve_indices_bk_biz_id(bk_biz_id=9), "9")
        self.assertIsNone(resolve_indices_bk_biz_id())

    def test_resolve_indices_exception_path_returns_none(self):
        with patch("apps.iam.handlers.scope.space_uid_to_bk_biz_id", side_effect=RuntimeError("boom")):
            self.assertIsNone(resolve_indices_bk_biz_id(space_uid="bkcc__2"))

    def test_resolve_collection_from_model_like_object(self):
        collector = type("Collector", (), {"bk_biz_id": 5})()
        self.assertEqual(resolve_collection_bk_biz_id(collector=collector), "5")
        self.assertIsNone(resolve_collection_bk_biz_id(bk_biz_id=""))

    def test_resolve_es_source_from_cluster_info(self):
        cluster_info = {"cluster_config": {"custom_option": {"bk_biz_id": 7}}}
        self.assertEqual(resolve_es_source_bk_biz_id(cluster_info=cluster_info), "7")
        self.assertEqual(resolve_es_source_bk_biz_id(cluster_info={"bk_biz_id": 4}), "4")
        self.assertIsNone(resolve_es_source_bk_biz_id(cluster_info={"cluster_config": {"custom_option": {}}}))

    def test_resource_belongs_to_space_and_platform_exemption(self):
        self.assertTrue(resource_belongs_to_space(resource_bk_biz_id="2", expected_bk_biz_id=2))
        self.assertFalse(resource_belongs_to_space(resource_bk_biz_id="3", expected_bk_biz_id=2))
        self.assertTrue(resource_belongs_to_space(resource_bk_biz_id="0", expected_bk_biz_id=2, allow_platform=True))
        self.assertFalse(resource_belongs_to_space(resource_bk_biz_id="0", expected_bk_biz_id=2, allow_platform=False))
        self.assertFalse(resource_belongs_to_space(resource_bk_biz_id=None, expected_bk_biz_id=2))
        self.assertTrue(resource_belongs_to_space(resource_bk_biz_id="8", expected_bk_biz_ids=["2", "8"]))

    def test_filter_items_by_space_ownership_drops_cross_space(self):
        items = [
            {"id": 1, "bk_biz_id": 2},
            {"id": 2, "bk_biz_id": 3},
            {"id": 3, "bk_biz_id": 0},
        ]
        filtered = filter_items_by_space_ownership(
            items,
            expected_bk_biz_id=2,
            resolve_bk_biz_id=lambda item: resolve_collection_bk_biz_id(bk_biz_id=item["bk_biz_id"]),
            allow_platform=True,
        )
        self.assertEqual([item["id"] for item in filtered], [1, 3])

    def test_build_iam_path(self):
        self.assertEqual(build_iam_path(2), "/space,2/")

    def test_resolve_request_bk_biz_id_edge_cases(self):
        self.assertEqual(
            resolve_request_bk_biz_id(type("Req", (), {"query_params": {"bk_biz_id": 2}})()),
            "2",
        )
        with patch("apps.iam.handlers.scope.space_uid_to_bk_biz_id", return_value=-5000001):
            self.assertEqual(
                resolve_request_bk_biz_id(type("Req", (), {"query_params": {"space_uid": "bkci__demo"}})()),
                "-5000001",
            )
        self.assertIsNone(resolve_request_bk_biz_id(None))
        self.assertIsNone(resolve_request_bk_biz_id(type("Req", (), {})()))
        self.assertIsNone(resolve_request_bk_biz_id(type("Req", (), {"query_params": {}})()))
        with patch("apps.iam.handlers.scope.space_uid_to_bk_biz_id", side_effect=RuntimeError("boom")):
            request = type("Req", (), {"query_params": {"space_uid": "bkci__x"}})()
            self.assertIsNone(resolve_request_bk_biz_id(request))

    def test_resource_belongs_to_space_requires_expected_ids(self):
        self.assertFalse(resource_belongs_to_space(resource_bk_biz_id="2"))

    def test_filter_nested_items_by_space_ownership_keeps_authorized_children(self):
        result_list = [
            {
                "index_set_id": 1,
                "space_uid": "bkcc__9",
                "children": [
                    {"index_set_id": 11, "space_uid": "bkcc__2"},
                    {"index_set_id": 12, "space_uid": "bkcc__3"},
                ],
            }
        ]
        filtered = filter_nested_items_by_space_ownership(
            result_list,
            expected_bk_biz_id=2,
            resolve_bk_biz_id=lambda item: resolve_indices_bk_biz_id(space_uid=item.get("space_uid", "")),
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["index_set_id"], 1)
        self.assertEqual([child["index_set_id"] for child in filtered[0]["children"]], [11])

    def test_filter_nested_items_by_action_permission(self):
        result_list = [
            {
                "index_set_id": 1,
                "children": [
                    {"index_set_id": 11},
                    {"index_set_id": 12},
                ],
            },
            {"index_set_id": 2},
            {"index_set_id": None},
        ]
        permission_result = {
            "1": {"search_log": True},
            "11": {"search_log": True},
            "12": {"search_log": False},
            "2": {"search_log": False},
        }
        filtered = filter_nested_items_by_action_permission(
            result_list,
            permission_result,
            id_field="index_set_id",
            action_id="search_log",
        )
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["index_set_id"], 1)
        self.assertEqual([child["index_set_id"] for child in filtered[0]["children"]], [11])
        self.assertTrue(filtered[0]["permission"]["search_log"])
        self.assertIsNone(filtered[1]["index_set_id"])

    def test_filter_nested_items_keeps_group_when_parent_denied_child_allowed(self):
        result_list = [
            {
                "index_set_id": 1,
                "is_group": True,
                "children": [
                    {"index_set_id": 11},
                    {"index_set_id": 12},
                ],
            }
        ]
        permission_result = {
            "1": {"search_log": False},
            "11": {"search_log": True},
            "12": {"search_log": False},
        }
        filtered = filter_nested_items_by_action_permission(
            result_list,
            permission_result,
            id_field="index_set_id",
            action_id="search_log",
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["index_set_id"], 1)
        self.assertFalse(filtered[0]["permission"]["search_log"])
        self.assertEqual([child["index_set_id"] for child in filtered[0]["children"]], [11])
        self.assertTrue(filtered[0]["children"][0]["permission"]["search_log"])
