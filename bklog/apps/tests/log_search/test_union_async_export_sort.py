from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE
from apps.log_databus.models import CollectorConfig
from apps.log_search.exceptions import PreCheckSortFieldException
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_unifyquery.handler.async_export_handlers import UnifyQueryUnionAsyncExportHandlers


class UnionAsyncExportSortTests(TestCase):
    def setUp(self):
        self.index_set_ids = []
        for storage_type in (STORAGE_CLUSTER_TYPE, DORIS_CLUSTER_TYPE):
            table_id = f"2_bklog.union_async_sort_{storage_type}"
            collector = CollectorConfig.objects.create(
                table_id=table_id,
                bk_biz_id=2,
                collector_config_name=f"union_async_sort_{storage_type}",
                collector_scenario_id="log",
                category_id="other_rt",
                storage_cluster_type=storage_type,
            )
            index_set = LogIndexSet.objects.create(
                index_set_name=f"union-async-sort-{storage_type}",
                space_uid="bkcc__2",
                scenario_id="log",
                storage_cluster_id=1,
                collector_config_id=collector.collector_config_id,
            )
            LogIndexSetData.objects.create(
                index_set_id=index_set.index_set_id,
                result_table_id=table_id,
                apply_status="normal",
                scenario_id="log",
                storage_cluster_id=1,
                bk_biz_id=2,
            )
            self.index_set_ids.append(index_set.index_set_id)

        self.enterContext(patch("apps.log_unifyquery.handler.base.FeatureToggleObject.toggle", return_value=None))
        self.enterContext(
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.MultiExecuteFunc.run",
                autospec=True,
                side_effect=self.run_field_queries,
            )
        )
        self.es_mapping = self.enterContext(
            patch("apps.api.BkLogApi.mapping", side_effect=AssertionError("ES mapping must not be called"))
        )
        self.field_map = self.enterContext(
            patch("apps.log_unifyquery.handler.mapping.UnifyQueryApi.query_field_map", side_effect=self.query_field_map)
        )
        self.enterContext(
            patch("apps.log_unifyquery.handler.mapping.TransferApi.get_result_table", return_value={"field_list": []})
        )
        module = "apps.log_unifyquery.handler.async_export_handlers"
        self.enterContext(patch(f"{module}.AsyncTask.check_running_count_by_user"))
        duplicate_tasks = self.enterContext(patch(f"{module}.AsyncTask.objects.filter"))
        duplicate_tasks.return_value.exists.return_value = False
        self.create_task = self.enterContext(
            patch(
                f"{module}.AsyncTask.async_export_task_create_with_running_limit", return_value=SimpleNamespace(id=17)
            )
        )
        self.enqueue = self.enterContext(patch(f"{module}.union_async_export.delay"))
        self.raw_query = self.enterContext(
            patch(
                "apps.log_unifyquery.handler.base.UnifyQueryApi.query_ts_raw", return_value={"list": [{"log": "one"}]}
            )
        )
        self.enterContext(patch.object(UnifyQueryUnionAsyncExportHandlers, "_get_url", return_value="/download/"))
        self.enterContext(
            patch.object(UnifyQueryUnionAsyncExportHandlers, "_get_search_url", return_value="/retrieve/")
        )

    @staticmethod
    def run_field_queries(executor, return_exception=False):
        # SQLite 单测使用同一连接执行字段查询，避免事务内跨线程访问数据库。
        for task in executor.task_list:
            task.run(return_exception=return_exception)
        return executor.results

    def query_field_map(self, params):
        is_doris = params["table_id"] == f"bklog_index_set_{self.index_set_ids[1]}"
        return {
            "data": [
                {"field_name": "dtEventTimeStamp", "field_type": "bigint" if is_doris else "date", "is_agg": True},
                {"field_name": "level", "field_type": "varchar" if is_doris else "keyword", "is_agg": True},
                {
                    "field_name": "log",
                    "field_type": "string" if is_doris else "text",
                    "is_analyzed": True,
                    "is_agg": False,
                },
            ]
        }

    def make_handler(self, sort_field="level", query_biz_id=2, handler_biz_id=2):
        return UnifyQueryUnionAsyncExportHandlers(
            bk_biz_id=handler_biz_id,
            index_set_ids=self.index_set_ids,
            search_dict={
                "bk_biz_id": query_biz_id,
                "start_time": "2026-11-01 10:00:00",
                "end_time": "2026-11-01 10:30:00",
                "keyword": "*",
                "addition": [],
                "begin": 0,
                "size": 10,
                "sort_list": [[sort_field, "desc"]] if sort_field else [],
            },
            export_fields=[],
        )

    def test_mixed_es_and_doris_support_valid_sort(self):
        self.assertTrue(LogIndexSet.objects.get(pk=self.index_set_ids[1]).is_native_doris())
        handler = self.make_handler()

        self.assertEqual(handler.async_export(), (17, 10))

        self.es_mapping.assert_not_called()
        self.create_task.assert_called_once()
        self.enqueue.assert_called_once()
        queried_labels = {call.args[0]["table_id"] for call in self.field_map.call_args_list}
        self.assertEqual(queried_labels, {f"bklog_index_set_{index_id}" for index_id in self.index_set_ids})
        self.assertTrue(all(call.args[0]["bk_biz_id"] == 2 for call in self.field_map.call_args_list))

    def test_non_sortable_field_is_rejected_before_task_creation(self):
        handler = self.make_handler(sort_field="log")

        with self.assertRaises(PreCheckSortFieldException):
            handler.async_export()

        self.es_mapping.assert_not_called()
        self.raw_query.assert_not_called()
        self.create_task.assert_not_called()
        self.enqueue.assert_not_called()

    def test_field_lookup_uses_query_scope_when_constructor_business_is_omitted(self):
        handler = self.make_handler(query_biz_id=-9, handler_biz_id=None)
        self.field_map.reset_mock()

        handler.async_export()

        self.assertTrue(self.field_map.called)
        self.assertTrue(all(call.args[0]["bk_biz_id"] == -9 for call in self.field_map.call_args_list))
        self.enqueue.assert_called_once()

    def test_no_explicit_sort_skips_extra_field_lookup(self):
        handler = self.make_handler(sort_field=None)
        self.field_map.reset_mock()

        self.assertEqual(handler.async_export(), (17, 10))

        self.field_map.assert_not_called()
        self.es_mapping.assert_not_called()
        self.enqueue.assert_called_once()
