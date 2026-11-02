"""
保存索引集显示字段时，校验存储路由与排序字段。
"""

from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.log_search.exceptions import BaseSearchSortListException, PreCheckSortFieldException
from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE
from apps.log_databus.models import CollectorConfig
from apps.log_search.handlers.search.mapping_handlers import MappingHandlers
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.views.search_views import SearchViewSet
from apps.log_search.models import (
    TAG_TYPE_INNER,
    IndexSetFieldsConfig,
    IndexSetTag,
    LogIndexSet,
    LogIndexSetData,
    Scenario,
)

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
    """保存入口共用排序字段校验，联合索引集保持原行为。"""

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

    @patch.object(SearchViewSet, "_verify_sort_list_item")
    @patch("apps.log_search.views.search_views.IndexSetFieldsConfigHandler")
    def test_update_config_single_validates_sort_fields(self, mock_config_handler, mock_verify):
        mock_config_handler.return_value.create_or_update.return_value = {}
        view, request = _build_view("update_config", self._payload())

        view.update_config(request)

        mock_verify.assert_called_once_with(INDEX_SET_ID, SORT_LIST)

    @patch.object(SearchViewSet, "_verify_sort_list_item")
    @patch("apps.log_search.views.search_views.IndexSetFieldsConfigHandler")
    def test_create_config_single_validates_sort_fields(self, mock_config_handler, mock_verify):
        mock_config_handler.return_value.create_or_update.return_value = {}
        payload = self._payload()
        payload.pop("config_id")
        view, request = _build_view("create_config", payload)

        view.create_config(request)

        mock_verify.assert_called_once_with(INDEX_SET_ID, SORT_LIST)

    @patch.object(SearchViewSet, "_verify_sort_list_item")
    @patch("apps.log_search.views.search_views.IndexSetFieldsConfigHandler")
    def test_union_config_does_not_validate_single_index(self, mock_config_handler, mock_verify):
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

        mock_verify.assert_not_called()


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


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TestDorisFieldsConfig(TestCase):
    def setUp(self):
        super().setUp()
        self.index_set = LogIndexSet.objects.create(
            index_set_id=INDEX_SET_ID,
            index_set_name="native_doris",
            space_uid="bkcc__2",
            scenario_id=Scenario.LOG,
            storage_cluster_id=77,
        )
        self.collector = CollectorConfig.objects.create(
            table_id="2_bklog.native_doris",
            bk_biz_id=2,
            collector_config_name="native_doris",
            collector_scenario_id="log",
            category_id="other_rt",
            storage_cluster_type=DORIS_CLUSTER_TYPE,
        )
        LogIndexSetData.objects.create(
            index_set_id=INDEX_SET_ID,
            result_table_id=self.collector.table_id,
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
            apply_status=LogIndexSetData.Status.NORMAL,
        )
        self.query_field_map = self.enterContext(
            patch("apps.log_unifyquery.handler.mapping.UnifyQueryApi.query_field_map")
        )
        self.query_field_map.return_value = {
            "data": [
                {"field_name": "dtEventTimeStamp", "field_type": "bigint", "is_agg": False},
                {"field_name": "gseIndex", "field_type": "bigint", "is_agg": False},
                {"field_name": "serverIp", "field_type": "string", "is_agg": False},
                {"field_name": "log", "field_type": "string", "is_analyzed": True},
                {"field_name": "payload", "field_type": "variant"},
                {"field_name": "dtEventTime", "field_type": "datetime"},
            ]
        }
        self.esquery = self.enterContext(
            patch(
                "apps.log_search.views.search_views.SearchHandlerEsquery",
                side_effect=AssertionError("unexpected ESQuery"),
            )
        )
        self.es_mapping = self.enterContext(
            patch("apps.api.BkLogApi.mapping", side_effect=AssertionError("unexpected ES mapping"))
        )
        self.enterContext(patch("apps.log_search.handlers.index_set.user_operation_record.delay"))

    def _save(self, action, **extra):
        payload = TestIndexSetFieldsConfigViewCheck._payload(**extra)
        if action == "create_config":
            payload.pop("config_id")
        view, request = _build_view(action, payload)
        return getattr(view, action)(request)

    def test_create_and_update_native_doris_without_snapshot(self):
        self.assertIsNone(self.index_set.fields_snapshot)
        self._save("create_config")
        config = IndexSetFieldsConfig.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(config.sort_list, SORT_LIST)
        self._save("update_config", config_id=config.pk, display_fields=["log"])
        config.refresh_from_db()
        self.assertEqual(config.display_fields, ["log"])
        self.assertEqual(self.query_field_map.call_count, 2)
        params = self.query_field_map.call_args.args[0]
        self.assertEqual(params["bk_biz_id"], 2)
        self.assertEqual(params["data_source"], settings.UNIFY_QUERY_DATA_SOURCE)
        self.assertEqual(params["table_id"], f"bklog_index_set_{INDEX_SET_ID}")
        self.assertLess(int(params["start_time"]), int(params["end_time"]))
        self.esquery.assert_not_called()
        self.es_mapping.assert_not_called()

    def test_mixed_group_uses_unify_query_when_enabled(self):
        child = LogIndexSet.objects.create(index_set_name="doris_child", space_uid="bkcc__2", scenario_id=Scenario.LOG)
        LogIndexSetData.objects.filter(index_set_id=INDEX_SET_ID).update(index_set_id=child.index_set_id)
        self.index_set.is_group = True
        self.index_set.save(update_fields=["is_group"])
        LogIndexSetData.objects.create(
            index_set_id=INDEX_SET_ID,
            result_table_id=str(child.index_set_id),
            type="index_set",
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
        )
        es_child = LogIndexSet.objects.create(index_set_name="es_child", space_uid="bkcc__2", scenario_id=Scenario.LOG)
        LogIndexSetData.objects.create(
            index_set_id=es_child.index_set_id,
            result_table_id="2_bklog.es",
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
            apply_status=LogIndexSetData.Status.NORMAL,
        )
        LogIndexSetData.objects.create(
            index_set_id=INDEX_SET_ID,
            result_table_id=str(es_child.index_set_id),
            type="index_set",
            scenario_id=Scenario.LOG,
            bk_biz_id=2,
        )
        self._save("create_config")
        self.query_field_map.assert_called_once()
        self.esquery.assert_not_called()

    def test_manual_doris_tag_uses_unify_query(self):
        self.collector.storage_cluster_type = STORAGE_CLUSTER_TYPE
        self.collector.save(update_fields=["storage_cluster_type"])
        self.index_set.tag_ids = [str(IndexSetTag.get_tag_id("Doris", tag_type=TAG_TYPE_INNER))]
        self.index_set.save(update_fields=["tag_ids"])
        self._save("create_config")
        self.query_field_map.assert_called_once()
        self.esquery.assert_not_called()

    def test_es_with_unify_query_enabled_uses_unify_query_fields(self):
        self.collector.storage_cluster_type = STORAGE_CLUSTER_TYPE
        self.collector.save(update_fields=["storage_cluster_type"])
        self.query_field_map.return_value["data"][0]["is_agg"] = True
        self._save("create_config", sort_list=[["dtEventTimeStamp", "desc"]])
        self.query_field_map.assert_called_once()
        self.esquery.assert_not_called()

    def test_invalid_sort_fields_are_rejected_without_saving(self):
        for field in ["not_exists", "log", "payload", "dtEventTime"]:
            with self.subTest(field=field), self.assertRaises(PreCheckSortFieldException):
                self._save("create_config", sort_list=[[field, "desc"]])
        self.assertFalse(IndexSetFieldsConfig.objects.filter(index_set_id=INDEX_SET_ID).exists())

    def test_update_invalid_sort_field_preserves_config(self):
        self._save("create_config")
        config = IndexSetFieldsConfig.objects.get(index_set_id=INDEX_SET_ID)
        with self.assertRaises(PreCheckSortFieldException):
            self._save("update_config", config_id=config.pk, sort_list=[["not_exists", "desc"]])
        config.refresh_from_db()
        self.assertEqual(config.sort_list, SORT_LIST)

    def test_empty_fields_can_use_existing_snapshot(self):
        self.index_set.fields_snapshot = {"fields": [{"field_name": "gseIndex", "es_doc_values": True}]}
        self.index_set.save(update_fields=["fields_snapshot"])
        self.query_field_map.return_value = {"data": []}
        self._save("create_config", sort_list=[["gseIndex", "desc"]])

    def test_empty_fields_without_snapshot_rejects_sort(self):
        self.query_field_map.return_value = {"data": []}
        with self.assertRaises(PreCheckSortFieldException):
            self._save("create_config")

    def test_unify_query_failure_does_not_fall_back_to_es(self):
        self.query_field_map.side_effect = RuntimeError("field_map failed")
        with self.assertRaisesRegex(RuntimeError, "field_map failed"):
            self._save("create_config")
        self.esquery.assert_not_called()
        self.es_mapping.assert_not_called()
        self.assertFalse(IndexSetFieldsConfig.objects.filter(index_set_id=INDEX_SET_ID).exists())

    def test_empty_sort_list_can_be_saved(self):
        self._save("create_config", sort_list=[])
        config = IndexSetFieldsConfig.objects.get(index_set_id=INDEX_SET_ID)
        self.assertEqual(config.sort_list, [])
        self.esquery.assert_not_called()
