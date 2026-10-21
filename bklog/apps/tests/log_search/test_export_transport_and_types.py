"""真实 DataAPI 滚动请求与跨存储时间字段兼容回归。"""

import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import APIException, ValidationError

from apps.generic import custom_exception_handler
from apps.log_search.constants import ExportSearchType
from apps.log_search.export.api import create_export_job
from apps.log_search.export.models import ExportJob
from apps.log_search.export.planner import build_handler
from apps.log_search.export.query import apply_time_range, snapshot_time_fields
from apps.log_search.export.worker import _write_rows
from apps.log_search.models import LogIndexSet, Scenario, Space
from apps.log_unifyquery.handler.base import UnifyQueryHandler


class ScrollTransportTests(TestCase):
    def setUp(self):
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_id="2",
            space_name="biz",
            bk_tenant_id="system",
        )

    def run_streams(self, *, interleave):
        dataset = list(range(5))
        cursors, calls = {}, []

        class Handler:
            base_dict = {"query_list": [], "start_time": "1784890800000", "end_time": "1784890801000", "bk_biz_id": 2}
            export_result_window = 2
            export_scroll_batch = UnifyQueryHandler.export_scroll_batch

            def project_export_rows(self, result):
                return result["list"]

        handler = Handler()
        frozen = copy.deepcopy(handler.base_dict)
        output = {}

        def request(session, method, url, data=None, **kwargs):
            body = json.loads(data)
            source = session.headers.get("Bk-Query-Source", "")
            name = source.partition(":")[2]
            # UQ 按来源 Name + 查询体定位会话；本例查询体完全相同，只保留 Name 作为键。
            if body.get("clear_cache"):
                cursors[name] = 0
            offset = cursors.setdefault(name, 0)
            batch = dataset[offset : offset + body["limit"]]
            cursors[name] = offset + len(batch)
            calls.append((source, bool(body.get("clear_cache")), batch))
            if interleave and name == "execution-a" and offset == 0:
                output["b"] = _write_rows(handler, directory / "b.jsonl", session_id="execution-b")
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"list": batch, "done": cursors[name] >= len(dataset)}).encode()
            return response

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            # 仅模拟 HTTP，不跳过 Handler、DataAPI、before_request 或 header 提取。
            with (
                patch("apps.api.modules.unify_query.add_esb_info_before_request", side_effect=lambda params: params),
                patch("apps.api.modules.unify_query.get_request", return_value=None),
                patch("requests.Session.request", request),
            ):
                output["a"] = _write_rows(handler, directory / "a.jsonl", session_id="execution-a")
                if not interleave:
                    output["b"] = _write_rows(handler, directory / "b.jsonl", session_id="execution-b")
            for name in ("a", "b"):
                self.assertEqual(
                    [json.loads(line) for line in (directory / f"{name}.jsonl").read_text().splitlines()], dataset
                )
                self.assertEqual(output[name][0], len(dataset))
        self.assertEqual(handler.base_dict, frozen)
        self.assertEqual(len(calls), 6)
        for name in ("execution-a", "execution-b"):
            own = [call for call in calls if call[0] == f"backend:{name}"]
            self.assertEqual([call[1] for call in own], [True, False, False])
            self.assertEqual([row for call in own for row in call[2]], dataset)

    def test_every_page_and_reexecution_keeps_its_source_header(self):
        self.run_streams(interleave=False)

    def test_identical_concurrent_jobs_keep_independent_http_cursors(self):
        self.run_streams(interleave=True)


class TimeTypeCompatibilityTests(SimpleTestCase):
    def snapshot(self, logical, result, *, search_type=ExportSearchType.INDEX_SET, data_source="bklog"):
        handler = SimpleNamespace(
            base_dict={
                "query_list": [{"data_source": data_source, "table_id": "rt"}],
                "bk_biz_id": 2,
                "start_time": "1784890800000",
                "end_time": "1784890801000",
            },
            index_info_list=[{"index_set_id": 1}],
        )
        with (
            patch("apps.log_search.export.query.UnifyQueryHandler.init_time_field", return_value=logical),
            patch("apps.log_search.export.query.UnifyQueryApi.query_field_map", return_value=result) as field_map,
        ):
            fields = snapshot_time_fields(handler, search_type)
        self.assertEqual(field_map.call_args.args[0]["data_source"], data_source)
        return fields

    def assert_millisecond_bounds(self, fields):
        params = {"query_list": [{}]}
        apply_time_range(params, fields, 1784890800937, 1784890801875)
        self.assertEqual(
            [item["value"][0] for item in params["query_list"][0]["conditions"]["field_list"]],
            ["1784890800937", "1784890801875"],
        )

    def test_doris_native_bigint_and_datetime_types(self):
        for physical in ("BIGINT", "bigint", "DATETIME", "datetime(3)"):
            with self.subTest(physical=physical):
                fields = self.snapshot(
                    ("dtEventTimeStamp", "date", "millisecond"),
                    {"data": [{"field_name": "dtEventTimeStamp", "field_type": physical}]},
                )
                self.assertEqual(fields[0]["type"], "date")
                self.assert_millisecond_bounds(fields)

    def test_bkdata_route_and_dict_field_map_use_the_standard_timestamp(self):
        for physical in ("long", "bigint", "date"):
            with self.subTest(physical=physical):
                fields = self.snapshot(
                    ("dtEventTimeStamp", "date", "millisecond"),
                    {"fields": {"dtEventTimeStamp": {"type": physical}}},
                    data_source="bkdata",
                )
                self.assertEqual(fields[0]["type"], "date")
                self.assert_millisecond_bounds(fields)

    def test_logical_date_without_unit_and_physical_long_keeps_milliseconds(self):
        for physical in ("long", "BIGINT"):
            with self.subTest(physical=physical):
                fields = self.snapshot(("ts", "date", None), {"data": [{"field_name": "ts", "field_type": physical}]})
                self.assertEqual(fields, [{"name": "ts", "type": "long", "unit": "millisecond"}])
                self.assert_millisecond_bounds(fields)

    def test_scene_doris_timestamp_uses_the_same_normalization(self):
        fields = self.snapshot(
            None,
            {"data": [{"field_name": "dtEventTimeStamp", "field_type": "BIGINT"}]},
            search_type=ExportSearchType.SCENE,
        )
        self.assertEqual(fields[0]["type"], "date")
        self.assert_millisecond_bounds(fields)

    def test_date_nanos_is_not_downgraded_by_builtin_timestamp_normalization(self):
        fields = self.snapshot(
            ("dtEventTimeStamp", "date", None),
            {"data": [{"field_name": "dtEventTimeStamp", "field_type": "date_nanos"}]},
        )
        self.assertEqual(fields[0]["type"], "date_nanos")
        params = {"query_list": [{}]}
        apply_time_range(params, fields, 1784890800937, 1784890801875)
        self.assertEqual(
            params["query_list"][0]["conditions"]["field_list"][1]["value"], ["2026-07-24T11:00:01.875000000Z"]
        )

    def test_unrecognized_time_type_is_not_silently_treated_as_date(self):
        with self.assertRaises(ValueError):
            self.snapshot(
                ("dtEventTimeStamp", "date", "millisecond"),
                {"data": [{"field_name": "dtEventTimeStamp", "field_type": "binary"}]},
            )

    def test_explicit_integer_time_units_are_not_changed(self):
        for unit in ("second", "millisecond", "microsecond", "nanosecond"):
            handler = SimpleNamespace(base_dict={"query_list": [{}]}, index_info_list=[{"index_set_id": 1}])
            with (
                patch(
                    "apps.log_search.export.query.UnifyQueryHandler.init_time_field", return_value=("ts", "long", unit)
                ),
                patch("apps.log_search.export.query.UnifyQueryApi.query_field_map") as field_map,
            ):
                self.assertEqual(
                    snapshot_time_fields(handler, ExportSearchType.INDEX_SET),
                    [{"name": "ts", "type": "long", "unit": unit}],
                )
                field_map.assert_not_called()


class TimeTypeCreationTests(TestCase):
    def setUp(self):
        Space.objects.create(space_uid="bkcc__2", bk_biz_id=2, space_type_id="bkcc", space_id="2", space_name="biz")
        self.index = LogIndexSet.objects.create(
            index_set_name="index",
            space_uid="bkcc__2",
            category_id="application",
            scenario_id=Scenario.ES,
            time_field="ts",
            time_field_type="date",
        )

    def create(self, physical):
        handler = Mock(
            base_dict={
                "query_list": [{"data_source": "bklog", "table_id": "rt", "field_name": "ts"}],
                "order_by": ["ts"],
            },
            origin_order_by=[["ts", "asc"]],
            is_desensitize=True,
            index_info_list=[{"index_set_id": self.index.pk}],
        )
        handler.pre_get_result.return_value = {"list": [{"ts": 1784890800000}]}
        with (
            patch("apps.log_search.export.api.is_sharded_export_enabled", return_value=True),
            patch("apps.log_search.export.api.UnifyQueryHandler", return_value=handler),
            patch("apps.log_search.export.api.get_request_username", return_value="tester"),
            patch("apps.log_search.export.api.get_request_external_username", return_value=""),
            patch(
                "apps.log_search.export.query.UnifyQueryApi.query_field_map",
                return_value={"data": [{"field_name": "ts", "field_type": physical}]},
                side_effect=physical if isinstance(physical, Exception) else None,
            ),
        ):
            return create_export_job(
                {
                    "space_uid": "bkcc__2",
                    "index_set_id": self.index.pk,
                    "start_time": 1784890800000,
                    "end_time": 1784890802000,
                }
            )

    def test_doris_job_snapshot_survives_database_reload_and_worker_rebuild(self):
        job = self.create("BIGINT")
        job.refresh_from_db()
        self.assertEqual(
            job.search_params["export_time_fields"], [{"name": "ts", "type": "long", "unit": "millisecond"}]
        )
        with patch("apps.log_search.export.planner.UnifyQueryHandler", return_value=Mock()):
            handler = build_handler(job, 1784890800937, 1784890801875)
        self.assertEqual(handler.base_dict["query_list"][0]["conditions"]["field_list"][1]["value"], ["1784890801875"])

    def test_unsupported_type_is_a_readable_validation_error_and_creates_no_job(self):
        with self.assertRaises(ValidationError) as error:
            self.create("binary")
        self.assertIn("ts", str(error.exception))
        response = custom_exception_handler(error.exception, {"request": Mock()})
        body = json.loads(response.content)
        self.assertFalse(body["result"])
        self.assertIn("无法确认导出时间字段 ts 的实际类型", body["message"])
        self.assertFalse(ExportJob.objects.exists())

    def test_internal_field_map_value_error_is_logged_but_not_returned(self):
        marker = "INTERNAL_METADATA_DETAIL:/srv/internal/metadata.py:123"
        with (
            patch("apps.log_search.export.api.logger.exception") as log_error,
            self.assertRaises(APIException) as error,
        ):
            self.create(ValueError(marker))
        self.assertNotIsInstance(error.exception, ValidationError)
        self.assertEqual(error.exception.status_code, 500)
        log_error.assert_called_once()
        self.assertIsInstance(error.exception.__cause__, ValueError)
        response = custom_exception_handler(error.exception, {"request": Mock()})
        body = json.loads(response.content)
        self.assertFalse(body["result"])
        self.assertIn("获取导出时间字段失败，请稍后重试", body["message"])
        self.assertNotIn(marker, response.content.decode())
        self.assertFalse(ExportJob.objects.exists())
