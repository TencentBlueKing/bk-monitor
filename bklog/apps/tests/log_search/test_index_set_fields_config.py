"""
保存索引集显示字段（/search/index_set/config、/search/index_set/update_config）的校验链路。

覆盖：
- single 索引集不再以默认参数构造 SearchHandlerEsquery：Doris 及 ES/Doris 混合存储的索引集
  在 esquery 侧取不到字段，构造阶段的预查询会误报「索引集对应的物理索引不存在」
- union 索引集不触发单索引集校验
- 排序字段校验不因跳过预查询而失效
"""

from unittest.mock import patch

from django.test import TestCase
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.log_search.exceptions import BaseSearchSortListException
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.views.search_views import SearchViewSet

INDEX_SET_ID = 30476
DISPLAY_FIELDS = ["dtEventTimeStamp", "serverIp"]
SORT_LIST = [["dtEventTimeStamp", "desc"], ["gseIndex", "desc"]]


def _build_view(action, payload):
    raw_request = APIRequestFactory().post(f"/api/v1/search/index_set/{action}/", data=payload, format="json")
    request = Request(raw_request, parsers=[JSONParser()])
    view = SearchViewSet(format_kwarg=None)
    view.request = request
    view.kwargs = {}
    view.action = action
    return view, request


class TestIndexSetFieldsConfigViewCheck(TestCase):
    """single 索引集保存显示字段时跳过 esquery 预查询。"""

    @staticmethod
    def _payload(**extra):
        payload = {
            "name": "默认字段",
            "display_fields": DISPLAY_FIELDS,
            "sort_list": SORT_LIST,
            "config_id": 37078,
            "index_set_id": INDEX_SET_ID,
            "index_set_ids": [],
            "index_set_type": "single",
        }
        payload.update(extra)
        return payload

    @patch("apps.log_search.views.search_views.IndexSetFieldsConfigHandler")
    @patch("apps.log_search.views.search_views.SearchHandlerEsquery")
    def test_update_config_single_skips_pre_check(self, mock_esquery, mock_config_handler):
        mock_config_handler.return_value.create_or_update.return_value = {}
        view, request = _build_view("update_config", self._payload())

        view.update_config(request)

        mock_esquery.assert_called_once()
        args, kwargs = mock_esquery.call_args
        self.assertEqual(args[0], INDEX_SET_ID)
        self.assertIs(kwargs.get("pre_check_enable"), False)
        mock_esquery.return_value.verify_sort_list_item.assert_called_once_with(SORT_LIST)

    @patch("apps.log_search.views.search_views.IndexSetFieldsConfigHandler")
    @patch("apps.log_search.views.search_views.SearchHandlerEsquery")
    def test_create_config_single_skips_pre_check(self, mock_esquery, mock_config_handler):
        mock_config_handler.return_value.create_or_update.return_value = {}
        payload = self._payload()
        payload.pop("config_id")
        view, request = _build_view("create_config", payload)

        view.create_config(request)

        mock_esquery.assert_called_once()
        _, kwargs = mock_esquery.call_args
        self.assertIs(kwargs.get("pre_check_enable"), False)

    @patch("apps.log_search.views.search_views.IndexSetFieldsConfigHandler")
    @patch("apps.log_search.views.search_views.SearchHandlerEsquery")
    def test_union_config_does_not_build_esquery_handler(self, mock_esquery, mock_config_handler):
        mock_config_handler.return_value.create_or_update.return_value = {}
        payload = {
            "name": "默认字段",
            "display_fields": DISPLAY_FIELDS,
            "sort_list": SORT_LIST,
            "config_id": 37078,
            "index_set_ids": [1, 2],
            "index_set_type": "union",
        }
        view, request = _build_view("update_config", payload)

        view.update_config(request)

        mock_esquery.assert_not_called()


class TestVerifySortListItemStillWorks(TestCase):
    """排序字段校验不因跳过预查询而失效。"""

    @staticmethod
    def _handler():
        handler = SearchHandler.__new__(SearchHandler)
        handler.origin_indices = "2_bklog.demo"
        handler.index_set_id = INDEX_SET_ID
        handler.origin_scenario_id = "log"
        handler.storage_cluster_id = 1
        handler.time_field = "dtEventTimeStamp"
        handler.search_dict = {}
        handler.time_zone = "Asia/Shanghai"
        handler.mapping_handler_class = MappingHandlers
        return handler

    @patch.object(
        MappingHandlers,
        "get_all_fields_by_index_id",
        return_value=([{"field_name": "gseIndex", "es_doc_values": True}], []),
    )
    def test_valid_sort_list_passes(self, _mock_fields):
        self._handler().verify_sort_list_item([["gseIndex", "desc"]])

    @patch.object(
        MappingHandlers,
        "get_all_fields_by_index_id",
        return_value=([{"field_name": "gseIndex", "es_doc_values": True}], []),
    )
    def test_unknown_sort_field_rejected(self, _mock_fields):
        with self.assertRaises(BaseSearchSortListException):
            self._handler().verify_sort_list_item([["not_exists", "desc"]])

    @patch.object(
        MappingHandlers,
        "get_all_fields_by_index_id",
        return_value=([{"field_name": "log", "es_doc_values": False}], []),
    )
    def test_sort_field_without_doc_values_rejected(self, _mock_fields):
        with self.assertRaises(BaseSearchSortListException):
            self._handler().verify_sort_list_item([["log", "desc"]])
