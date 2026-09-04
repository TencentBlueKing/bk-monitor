from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.response import Response

from apps.iam.handlers.actions import ActionEnum
from apps.log_search.views.search_views import SearchViewSet


class SearchIndexSetListPermissionAnnotateTest(SimpleTestCase):
    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.permission.Permission")
    @patch("apps.log_search.views.search_views.IndexSetHandler")
    def test_list_annotates_permission_without_removing_rows(self, handler_cls, permission_cls):
        handler_cls.return_value.get_user_index_set.return_value = [
            {
                "index_set_id": 1,
                "bk_biz_id": 2,
                "space_uid": "bkcc__2",
                "children": [
                    {"index_set_id": 11, "bk_biz_id": 2, "space_uid": "bkcc__2"},
                    {"index_set_id": 12, "bk_biz_id": 2, "space_uid": "bkcc__2"},
                ],
            },
            {"index_set_id": 2, "bk_biz_id": 2, "space_uid": "bkcc__2"},
        ]
        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.SEARCH_LOG.id: True},
            "11": {ActionEnum.SEARCH_LOG.id: True},
            "12": {ActionEnum.SEARCH_LOG.id: False},
            "2": {ActionEnum.SEARCH_LOG.id: False},
        }

        view = SearchViewSet()
        view.request = SimpleNamespace()
        view.format_kwarg = None
        view.params_valid = MagicMock(return_value={"space_uid": "bkcc__2", "is_group": True})

        response = view.list(view.request)
        self.assertIsInstance(response, Response)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["index_set_id"], 1)
        self.assertEqual([child["index_set_id"] for child in response.data[0]["children"]], [11, 12])
        self.assertTrue(response.data[0]["permission"][ActionEnum.SEARCH_LOG.id])
        self.assertFalse(response.data[0]["children"][1]["permission"][ActionEnum.SEARCH_LOG.id])
        self.assertFalse(response.data[1]["permission"][ActionEnum.SEARCH_LOG.id])

    @override_settings(IGNORE_IAM_PERMISSION=False)
    @patch("apps.iam.handlers.permission.Permission")
    @patch("apps.log_search.views.search_views.IndexSetHandler")
    def test_list_skips_items_without_index_set_id(self, handler_cls, permission_cls):
        handler_cls.return_value.get_user_index_set.return_value = [
            {"index_set_id": None, "bk_biz_id": 2, "space_uid": "bkcc__2"},
            {"index_set_id": 1, "bk_biz_id": 2, "space_uid": "bkcc__2"},
        ]
        permission_cls.return_value.batch_is_allowed.return_value = {
            "1": {ActionEnum.SEARCH_LOG.id: True},
            "None": {ActionEnum.SEARCH_LOG.id: False},
        }

        view = SearchViewSet()
        view.request = SimpleNamespace()
        view.format_kwarg = None
        view.params_valid = MagicMock(return_value={"space_uid": "bkcc__2", "is_group": False})

        response = view.list(view.request)
        self.assertEqual(len(response.data), 2)
        self.assertNotIn("permission", response.data[0])
        self.assertTrue(response.data[1]["permission"][ActionEnum.SEARCH_LOG.id])
