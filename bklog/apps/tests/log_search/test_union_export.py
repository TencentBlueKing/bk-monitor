import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler, UnionSearchHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_search.views.search_views import SearchViewSet
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnionSearchExportTests(TestCase):
    index_set_ids = [1001, 1002]
    sensitive_value = "sensitive-export-sample"

    def setUp(self):
        self.mock_logs = None
        for index_set_id in self.index_set_ids:
            LogIndexSet.objects.create(
                index_set_id=index_set_id,
                index_set_name=f"union-export-{index_set_id}",
                space_uid="bkcc__2",
                scenario_id="es",
                storage_cluster_id=1,
                time_field="dtEventTimeStamp",
                time_field_type="date",
                time_field_unit="millisecond",
            )
            LogIndexSetData.objects.create(
                index_set_id=index_set_id,
                bk_biz_id=2,
                result_table_id=f"2_bklog.union_export_{index_set_id}",
                apply_status="normal",
                scenario_id="es",
                storage_cluster_id=1,
                time_field="dtEventTimeStamp",
            )
            DesensitizeConfig.objects.create(index_set_id=index_set_id, text_fields=[])
            DesensitizeFieldConfig.objects.create(
                index_set_id=index_set_id,
                field_name="message",
                operator="text_replace",
                params={"template_string": "[FILTERED]"},
                match_pattern=".*",
                sort_index=0,
            )

        self.params = {
            "bk_biz_id": 2,
            "index_set_ids": self.index_set_ids,
            "keyword": self.sensitive_value,
            "start_time": "2026-11-01 10:00:00",
            "end_time": "2026-11-01 10:30:00",
            "addition": [],
            "begin": 0,
            "size": 10,
        }
        self.enterContext(patch.object(UnifyQueryHandler, "init_base_dict", return_value={}))
        self.enterContext(patch("apps.log_unifyquery.handler.base.FeatureToggleObject.toggle", return_value=None))
        self.enterContext(
            patch("apps.log_unifyquery.handler.base.UnifyQueryApi.query_ts_raw", side_effect=self.query_ts_raw)
        )

    def query_ts_raw(self, params):
        logs = self.mock_logs
        if logs is None:
            logs = [
                {
                    "dtEventTimeStamp": 1793498400000,
                    "message": self.sensitive_value,
                    "__index": "union-export-index",
                    "__doc_id": "union-export-document",
                }
            ]
        result_logs = []
        for log in logs:
            log = copy.deepcopy(log)
            if params["highlight"]["enable"]:
                log["__highlight"] = {"message": [f"<mark>{self.sensitive_value}</mark>"]}
            result_logs.append(log)
        return {"total": len(result_logs), "took": 1, "list": result_logs}

    @staticmethod
    def _set_time_field(index_set_id, time_field, time_field_unit="millisecond"):
        LogIndexSet.objects.filter(index_set_id=index_set_id).update(
            time_field=time_field, time_field_unit=time_field_unit
        )
        LogIndexSetData.objects.filter(index_set_id=index_set_id).update(time_field=time_field)

    def _make_log(self, time_values):
        return {
            **time_values,
            "message": self.sensitive_value,
            "__index": "union-export-index",
            "__doc_id": "union-export-document",
        }

    def _nested_time_params(self, index_set_ids):
        return {
            **self.params,
            "index_set_ids": index_set_ids,
            "union_configs": [
                {"index_set_id": index_set_id, "begin": 0, "is_desensitize": True}
                for index_set_id in index_set_ids
            ],
        }

    def test_export_without_selected_fields_keeps_sensitive_content_masked(self):
        for export_params in ({}, {"export_fields": []}):
            with self.subTest(export_params=export_params):
                request = SimpleNamespace(method="POST", data={**self.params, **export_params})
                view = SearchViewSet()
                view.request = request

                response = view.union_search_export(request)
                content = b"".join(response.streaming_content).decode()

                rows = [json.loads(line) for line in content.splitlines()]
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(row["message"] == "[FILTERED]" for row in rows))
                self.assertTrue(all("__highlight" not in row for row in rows))
                self.assertNotIn(self.sensitive_value, content)

    def test_regular_union_search_keeps_highlight(self):
        DesensitizeConfig.objects.filter(index_set_id__in=self.index_set_ids).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id__in=self.index_set_ids).delete()
        params = {
            **self.params,
            "union_configs": [
                {"index_set_id": index_set_id, "begin": 0, "is_desensitize": True}
                for index_set_id in self.index_set_ids
            ],
        }
        with patch.object(UnionSearchHandler, "_save_union_search_history"):
            result = UnionSearchHandler(params).unifyquery_union_search()

        self.assertEqual(len(result["list"]), 2)
        self.assertTrue(all(log["message"] == f"<mark>{self.sensitive_value}</mark>" for log in result["list"]))

    def test_nested_time_field_default_sort(self):
        self._set_time_field(1001, "event.time")
        self.mock_logs = [
            self._make_log({"event.time": 1700}),
            self._make_log({"event.time": 1800}),
        ]
        params = self._nested_time_params([1001])

        with patch.object(UnionSearchHandler, "_save_union_search_history"):
            result = UnionSearchHandler(params).unifyquery_union_search()

        self.assertEqual(len(result["list"]), 2)
        self.assertEqual([row["event"]["time"] for row in result["list"]], [1800, 1700])
        self.assertEqual([row["message"] for row in result["list"]], ["[FILTERED]", "[FILTERED]"])
        self.assertNotIn("event.time", result["list"][0])

    def test_nested_time_field_unit_normalization(self):
        self._set_time_field(1001, "event.time", "millisecond")
        self._set_time_field(1002, "event.ts", "second")
        self.mock_logs = [self._make_log({"event.time": 1700, "event.ts": 2})]
        params = self._nested_time_params([1001, 1002])

        with patch.object(UnionSearchHandler, "_save_union_search_history"):
            result = UnionSearchHandler(params).unifyquery_union_search()

        self.assertEqual(len(result["list"]), 2)
        row_by_id = {row["__index_set_id__"]: row for row in result["list"]}
        self.assertEqual(row_by_id[1001]["unionSearchTimeStamp"], 1700)
        self.assertEqual(row_by_id[1002]["unionSearchTimeStamp"], 2000)
        self.assertEqual(
            [(row["__index_set_id__"], row["unionSearchTimeStamp"]) for row in result["list"]],
            [(1002, 2000), (1001, 1700)],
        )

    def test_nested_time_field_export(self):
        self._set_time_field(1001, "event.time")
        self.mock_logs = [
            self._make_log({"event.time": 1700}),
            self._make_log({"event.time": 1800}),
        ]
        params = self._nested_time_params([1001])

        result = UnionSearchHandler(params).unifyquery_union_search(is_export=True)

        self.assertEqual(len(result["origin_log_list"]), 2)
        self.assertEqual([row["event"]["time"] for row in result["origin_log_list"]], [1800, 1700])

    def test_legacy_union_search_nested_time_field_default_sort(self):
        self._set_time_field(1001, "event.time")
        rows = [
            {"__index_set_id__": 1001, "event": {"time": 1700}, "message": "[FILTERED]"},
            {"__index_set_id__": 1001, "event": {"time": 1800}, "message": "[FILTERED]"},
        ]
        search_result = {
            "list": copy.deepcopy(rows),
            "origin_log_list": copy.deepcopy(rows),
            "total": 2,
            "took": 1,
            "fields": {},
        }
        params = self._nested_time_params([1001])

        self.enterContext(patch.object(SearchHandler, "__init__", return_value=None))
        self.enterContext(patch.object(SearchHandler, "search", return_value=search_result))
        self.enterContext(patch.object(UnionSearchHandler, "_save_union_search_history"))
        result = UnionSearchHandler(params).union_search()

        self.assertEqual(len(result["list"]), 2)
        self.assertEqual([row["event"]["time"] for row in result["list"]], [1800, 1700])
