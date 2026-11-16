import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.handlers.search.search_handlers_esquery import UnionSearchHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_search.views.search_views import SearchViewSet
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class UnionSearchExportTests(TestCase):
    index_set_ids = [1001, 1002]
    sensitive_value = "sensitive-export-sample"

    def setUp(self):
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
        log = {
            "dtEventTimeStamp": 1793498400000,
            "message": self.sensitive_value,
            "__index": "union-export-index",
            "__doc_id": "union-export-document",
        }
        if params["highlight"]["enable"]:
            log["__highlight"] = {"message": [f"<mark>{self.sensitive_value}</mark>"]}
        return {"total": 1, "took": 1, "list": [log]}

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
