from unittest.mock import patch

from django.test import SimpleTestCase

from apps.log_search.exceptions import DorisQueryDataNotReadyException
from apps.log_unifyquery.handler.chart import UnifyQueryChartHandler


class TestUnifyQueryChartHandler(SimpleTestCase):
    def _build_handler(self):
        handler = UnifyQueryChartHandler.__new__(UnifyQueryChartHandler)
        handler.base_dict = {}
        handler.sql = ""
        return handler

    def test_get_chart_data_raises_when_doris_storage_is_not_ready(self):
        handler = self._build_handler()
        result = {
            "list": [],
            "status": {
                "code": "QUERY_RAW_PARTIAL",
                "message": "结果表没有配置存储，请先配置入库",
            },
            "result_table_options": {"result_table|5": {"from": 0}},
        }

        with (
            patch.object(handler, "check_support_sql_and_grep"),
            patch("apps.log_unifyquery.handler.chart.UnifyQueryApi.query_ts_raw", return_value=result),
        ):
            with self.assertRaises(DorisQueryDataNotReadyException) as context:
                handler.get_chart_data()

        self.assertEqual(
            context.exception.message,
            "存储集群接入中，数据暂未准备完成，请稍后重试",
        )

    def test_generate_sql_raises_when_doris_storage_is_not_ready(self):
        handler = self._build_handler()
        result = {
            "status": {
                "code": "QUERY_RAW_PARTIAL",
                "message": "结果表没有配置存储，请先配置入库",
            },
            "result_table_options": {
                "result_table|5": {"from": 0},
            },
        }

        with (
            patch.object(handler, "check_support_sql_and_grep"),
            patch("apps.log_unifyquery.handler.chart.UnifyQueryApi.query_ts_raw", return_value=result),
        ):
            with self.assertRaises(DorisQueryDataNotReadyException):
                handler.generate_sql()

    def test_get_chart_data_reads_schema_from_the_matching_result_table_option(self):
        handler = self._build_handler()
        result = {
            "list": [{"field": "value"}],
            "result_table_options": {
                "result_table|5": {"from": 0},
                "result_table|31": {"result_schema": [{"field_alias": "field"}]},
            },
        }

        with (
            patch.object(handler, "check_support_sql_and_grep"),
            patch("apps.log_unifyquery.handler.chart.UnifyQueryApi.query_ts_raw", return_value=result),
        ):
            chart_data = handler.get_chart_data()

        self.assertEqual(chart_data["result_schema"], [{"field_alias": "field"}])
        self.assertEqual(chart_data["select_fields_order"], ["field"])

    def test_generate_sql_reads_sql_from_the_matching_result_table_option(self):
        handler = self._build_handler()
        result = {
            "result_table_options": {
                "result_table|5": {"from": 0},
                "result_table|31": {"sql": "SELECT * FROM result_table"},
            },
        }

        with (
            patch.object(handler, "check_support_sql_and_grep"),
            patch("apps.log_unifyquery.handler.chart.UnifyQueryApi.query_ts_raw", return_value=result),
        ):
            data = handler.generate_sql()

        self.assertEqual(data["additional_where_clause"], "SELECT * FROM result_table")

    def test_export_chart_data_returns_empty_data_when_doris_storage_is_not_ready(self):
        handler = self._build_handler()
        result = {
            "list": [],
            "status": {
                "code": "QUERY_RAW_PARTIAL",
                "message": "结果表没有配置存储，请先配置入库",
            },
        }

        with (
            patch("apps.log_unifyquery.handler.chart.UnifyQueryApi.query_ts_raw_with_scroll", return_value=result),
        ):
            with self.assertRaises(StopIteration):
                next(handler.export_chart_data())

        self.assertEqual(result["list"], [])
        self.assertEqual(result["total"], 0)
        self.assertTrue(result["done"])

    def test_export_chart_data_reads_schema_from_the_matching_result_table_option(self):
        handler = self._build_handler()
        result = {
            "list": [{"field": "value"}],
            "done": True,
            "result_table_options": {
                "result_table|5": {"from": 0},
                "result_table|31": {"result_schema": [{"field_alias": "field"}]},
            },
        }

        with patch("apps.log_unifyquery.handler.chart.UnifyQueryApi.query_ts_raw_with_scroll", return_value=result):
            export_data = next(handler.export_chart_data())

        self.assertEqual(export_data, "field\r\nvalue\r\n")
