from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.http import Http404
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.log_search.constants import (
    ASYNC_EXPORT_SCENE_ID,
    ExportJobStatus,
    ExportPartStatus,
    ExportPlanStatus,
    ExportSearchType,
    ExportStage,
    ExportStatus,
    ExportType,
    IndexSetType,
)
from apps.log_search.export.history import load_export_progress, paginate_export_history, sharded_job_history_item
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.log_search.handlers.search.async_export_handlers import AsyncExportHandlers
from apps.log_search.models import AsyncTask, Scenario
from apps.log_search.views.export_views import ExportJobViewSet
from apps.log_unifyquery.handler.scene_async_export import SceneAsyncExportHandler


class ExportHistoryPaginationTests(TestCase):
    def setUp(self):
        self.expected = []
        start = timezone.now() - timedelta(hours=1)
        for number in range(12):
            task = AsyncTask.objects.create(
                id=number + 1,
                request_param={},
                created_by="tester",
                bk_biz_id=2,
                source_app_code="bk_log",
                index_set_id=3,
                scenario_id=Scenario.LOG,
                export_type=ExportType.ASYNC,
                export_status=ExportStatus.SUCCESS,
            )
            AsyncTask.objects.filter(pk=task.pk).update(created_at=start + timedelta(seconds=number * 2))
            job = ExportJob.objects.create(
                id=number + 1,
                space_uid="bkcc__2",
                created_by="tester",
                bk_biz_id=2,
                source_app_code="bk_log",
                index_set_ids=[3],
                search_params={},
                base_dict={},
                policy={},
                start_time=0,
                end_time=1000,
            )
            ExportJob.objects.filter(pk=job.pk).update(created_at=start + timedelta(seconds=number * 2 + 1))
            self.expected.extend([("legacy", task.pk), ("sharded", job.pk)])
        self.expected.reverse()

    @staticmethod
    def request(page=1, pagesize=5, body=False):
        params = {"page": page, "pagesize": pagesize}
        return SimpleNamespace(query_params={} if body else params, data=params if body else {})

    def test_interleaved_pages_load_only_current_page_details(self):
        actual = []
        for page in range(1, 6):
            with CaptureQueriesContext(connection) as queries:
                pg, records = paginate_export_history(
                    AsyncTask.objects.all(), ExportJob.objects.all(), self.request(page), None
                )
            self.assertEqual(pg.page.paginator.count, 24)
            actual.extend(("legacy" if isinstance(record, AsyncTask) else "sharded", record.pk) for record in records)
            page_query = next(
                query["sql"] for query in queries if "UNION ALL" in query["sql"] and "LIMIT" in query["sql"]
            )
            self.assertNotIn("request_param", page_query)
            self.assertNotIn("search_params", page_query)
            detail_queries = [
                query["sql"] for query in queries if "request_param" in query["sql"] or "search_params" in query["sql"]
            ]
            self.assertEqual(len(detail_queries), 2)
            self.assertTrue(all(" IN (" in query for query in detail_queries))
        self.assertEqual(actual, self.expected)

    def test_identical_time_and_id_keep_both_engines_across_pages(self):
        timestamp = timezone.now()
        AsyncTask.objects.all().update(created_at=timestamp)
        ExportJob.objects.all().update(created_at=timestamp)
        pg, first = paginate_export_history(AsyncTask.objects.all(), ExportJob.objects.all(), self.request(1, 1), None)
        _, second = paginate_export_history(AsyncTask.objects.all(), ExportJob.objects.all(), self.request(2, 1), None)
        self.assertEqual(pg.page.paginator.count, 24)
        self.assertIsInstance(first[0], AsyncTask)
        self.assertIsInstance(second[0], ExportJob)
        self.assertEqual(first[0].pk, second[0].pk)

    def test_empty_history_and_out_of_range_page(self):
        pg, records = paginate_export_history(
            AsyncTask.objects.filter(pk=0), ExportJob.objects.filter(pk=0), self.request(), None
        )
        self.assertEqual(pg.get_paginated_response(records).data, {"total": 0, "list": []})
        with self.assertRaises(NotFound):
            paginate_export_history(AsyncTask.objects.all(), ExportJob.objects.all(), self.request(6), None)

    def test_history_with_only_one_engine(self):
        for tasks, jobs, model in (
            (AsyncTask.objects.all(), ExportJob.objects.none(), AsyncTask),
            (AsyncTask.objects.none(), ExportJob.objects.all(), ExportJob),
        ):
            pg, records = paginate_export_history(tasks, jobs, self.request(), None)
            self.assertEqual(pg.page.paginator.count, 12)
            self.assertEqual([record.pk for record in records], [12, 11, 10, 9, 8])
            self.assertTrue(all(isinstance(record, model) for record in records))

    @patch("apps.log_search.export.history.get_request_external_username", return_value="")
    @patch("apps.log_search.export.history.get_request_app_code", return_value="bk_log")
    @patch("apps.log_search.handlers.search.async_export_handlers.get_request_external_username", return_value="")
    @patch("apps.log_search.handlers.search.async_export_handlers.get_request_app_code", return_value="bk_log")
    def test_index_history_formats_only_current_page(self, *_mocks):
        for is_union in (False, True):
            index_type = IndexSetType.UNION.value if is_union else IndexSetType.SINGLE.value
            AsyncTask.objects.all().update(index_set_type=index_type, index_set_ids=[3])
            ExportJob.objects.all().update(index_set_type=index_type)
            handler = AsyncExportHandlers(index_set_id=3, index_set_ids=[3], bk_biz_id=2)
            with (
                patch.object(handler, "get_index_set_retention", return_value={}) as retention,
                patch.object(handler, "generate_export_history", wraps=handler.generate_export_history) as formatter,
            ):
                response = handler.get_export_history(self.request(2), None, is_union_search=is_union)
            self.assertEqual(response.data["total"], 24)
            self.assertEqual(
                [(item.get("engine", "legacy"), item["id"]) for item in response.data["list"]], self.expected[5:10]
            )
            retention.assert_called_once_with(index_set_ids=[3])
            self.assertEqual(formatter.call_count, 3)
            for item in response.data["list"]:
                if item.get("engine") == "sharded":
                    self.assertEqual(item["progress"]["job_status"], ExportJobStatus.PENDING)
                    self.assertEqual(item["progress"]["parts_total"], 0)
                    self.assertIsNone(item["progress"]["planned_parts"])
                else:
                    self.assertNotIn("progress", item)

    @patch("apps.log_search.export.history.get_request_external_username", return_value="")
    @patch("apps.log_search.export.history.get_request_app_code", return_value="bk_log")
    @patch("apps.log_unifyquery.handler.scene_async_export.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_async_export.get_request_app_code", return_value="bk_log")
    def test_scene_history_uses_post_pagination_and_existing_scope(self, *_mocks):
        conditions = [[{"field": "scene", "value": "host", "operator": "eq"}]]
        AsyncTask.objects.all().update(
            scenario_id=ASYNC_EXPORT_SCENE_ID, request_param={"table_id_conditions": conditions}
        )
        ExportJob.objects.all().update(
            search_type=ExportSearchType.SCENE, search_params={"table_id_conditions": conditions}
        )
        ExportJob.objects.filter(pk=12).update(created_by="other")
        handler = SceneAsyncExportHandler(bk_biz_id=2)
        handler.request_user = "tester"
        response = handler.get_export_history(self.request(body=True), None, table_id_conditions=conditions)
        self.assertEqual(response.data["total"], 23)
        self.assertEqual(
            [(item.get("engine", "legacy"), item["id"]) for item in response.data["list"]], self.expected[1:6]
        )
        self.assertTrue(all("progress" in item for item in response.data["list"] if item.get("engine") == "sharded"))

    def test_progress_queries_are_limited_to_current_page_jobs(self):
        with CaptureQueriesContext(connection) as queries:
            _, records = paginate_export_history(AsyncTask.objects.all(), ExportJob.objects.all(), self.request(), None)
        job_ids = [record.pk for record in records if isinstance(record, ExportJob)]
        progress_queries = [
            query["sql"] for query in queries if "log_export_part" in query["sql"] or "log_export_plan" in query["sql"]
        ]
        self.assertEqual(len(progress_queries), 2)
        for sql in progress_queries:
            ids = sql.split(" IN (")[1].split(")")[0]
            self.assertCountEqual([int(value.strip()) for value in ids.split(",")], job_ids)


class ExportJobDetailTests(TestCase):
    def setUp(self):
        self.job = ExportJob.objects.create(
            space_uid="bkcc__2",
            created_by="tester",
            source_app_code="bk_log",
            bk_biz_id=2,
            search_params={},
            base_dict={},
            policy={},
            start_time=0,
            end_time=1000,
            plan_version=1,
            status=ExportJobStatus.RUNNING,
        )

    def part(self, part_no, **kwargs):
        return ExportPart.objects.create(
            job=self.job,
            part_no=part_no,
            plan_version=1,
            start_time=(part_no - 1) * 100,
            end_time=part_no * 100,
            **kwargs,
        )

    def detail(self, pk=None, external_username="", **params):
        request = Request(APIRequestFactory().get("/api/v1/search/export_jobs/1/", {"space_uid": "bkcc__2", **params}))
        view = ExportJobViewSet()
        view.request = request
        view.kwargs = {"pk": self.job.pk if pk is None else pk}
        view.action = "retrieve"
        with (
            patch("apps.log_search.views.export_views.get_request_app_code", return_value="bk_log"),
            patch("apps.log_search.views.export_views.get_request_external_username", return_value=external_username),
            patch(
                "apps.log_search.views.export_views.ExportJobIndexSearchPermission.has_object_permission",
                return_value=True,
            ),
            # 业务访问权限与索引集检索权限都是对象级校验；本地 .env 的 IGNORE_IAM_PERMISSION 会跳过它们，
            # CI 未开启该开关时会真实调用 IAM 后端，这里同样 mock 掉以聚焦详情接口本身的逻辑。
            patch(
                "apps.log_search.views.export_views.ViewBusinessPermission.has_object_permission",
                return_value=True,
            ),
        ):
            return view.retrieve(request).data

    def test_summary_counts_leaves_and_concurrent_stages(self):
        ExportPlan.objects.create(job=self.job, plan_version=1, planned_parts=5, status=ExportPlanStatus.SUCCESS)
        parent = self.part(1, status=ExportPartStatus.SPLIT)
        self.part(2, status=ExportPartStatus.RUNNING, stage=ExportStage.DOWNLOAD_LOG, parent_part=parent)
        self.part(3, status=ExportPartStatus.RUNNING, stage=ExportStage.PACKAGE, parent_part=parent)
        self.part(4, status=ExportPartStatus.UPLOADING, stage=ExportStage.UPLOAD)
        self.part(5, status=ExportPartStatus.SUCCESS, stage=ExportStage.UPLOAD)
        self.part(6, status=ExportPartStatus.FAILED)
        self.part(7, status=ExportPartStatus.WAITING)
        other = ExportJob.objects.create(
            space_uid="bkcc__2",
            created_by="tester",
            search_params={},
            base_dict={},
            policy={},
            start_time=0,
            end_time=1000,
        )
        with self.assertNumQueries(2):
            load_export_progress([self.job, other])
        with self.assertNumQueries(0):
            item = sharded_job_history_item(self.job)
        progress = item["progress"]
        self.assertEqual(item["export_status"], ExportStatus.DOWNLOAD_LOG)
        self.assertEqual(progress["planned_parts"], 5)
        self.assertEqual(progress["parts_total"], 6)
        self.assertEqual(progress["parts_success"], 1)
        self.assertEqual(progress["parts_failed"], 1)
        self.assertEqual(progress["status_counts"][ExportPartStatus.SPLIT], 1)
        self.assertEqual(progress["status_counts"][ExportPartStatus.WAITING], 1)
        self.assertEqual(
            progress["stage_counts"],
            {
                ExportStage.DOWNLOAD_LOG: 1,
                ExportStage.PACKAGE: 1,
                ExportStage.UPLOAD: 1,
            },
        )
        self.assertEqual(other.export_progress["parts_total"], 0)
        self.assertIsNone(other.export_progress["planned_parts"])

    def test_detail_includes_split_lineage_and_export_results(self):
        parent = self.part(1, status=ExportPartStatus.SPLIT, error_code="FETCH_TIMEOUT")
        child = self.part(
            2,
            status=ExportPartStatus.SUCCESS,
            parent_part=parent,
            attempts=2,
            actual_rows=42,
            actual_bytes=420,
            compressed_bytes=100,
            checksum="abc",
            object_key="private-object",
        )
        failed = self.part(3, status=ExportPartStatus.FAILED, error_code="QUERY_FAILED", error_detail="查询失败")
        with patch("apps.log_search.export.api.build_storage") as storage:
            detail = self.detail()
        storage.assert_not_called()
        self.assertEqual([part["id"] for part in detail["parts"]], [parent.pk, child.pk, failed.pk])
        result = detail["parts"][1]
        self.assertEqual(result["parent_part_id"], parent.pk)
        self.assertEqual(result["artifact_id"], str(child.pk))
        self.assertEqual((result["attempts"], result["actual_rows"], result["compressed_bytes"]), (2, 42, 100))
        self.assertEqual(result["checksum"], "abc")
        self.assertNotIn("object_key", result)
        result = detail["parts"][2]
        self.assertEqual(result["id"], failed.pk)
        self.assertIsNone(result["artifact_id"])
        self.assertEqual(result["error_detail"], "查询失败")
        self.assertEqual(detail["progress"]["parts_total"], 2)

    def test_detail_returns_all_parts_without_pagination(self):
        ExportPart.objects.bulk_create(
            [
                ExportPart(job=self.job, part_no=number, plan_version=1, start_time=0, end_time=1)
                for number in range(1, 102)
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            detail = self.detail()
        self.assertEqual(len(detail["parts"]), 101)
        self.assertEqual([part["part_no"] for part in detail["parts"]], list(range(1, 102)))
        part_queries = [query["sql"] for query in queries if "parent_part_id" in query["sql"]]
        self.assertEqual(len(part_queries), 1)
        self.assertNotIn("LIMIT", part_queries[0])

    def test_detail_validates_scope_and_handles_empty_parts(self):
        self.assertEqual(self.detail()["parts"], [])
        with self.assertRaises(ValidationError):
            self.detail(space_uid="")

    def test_detail_enforces_space_app_and_external_owner_scope(self):
        self.assertEqual(self.detail(external_username="tester")["id"], self.job.pk)
        for params in ({"space_uid": "bkcc__3"}, {"external_username": "another"}, {"pk": self.job.pk + 1}):
            with self.subTest(params=params), self.assertRaises(Http404):
                self.detail(**params)
        self.job.source_app_code = "other_app"
        self.job.save(update_fields=["source_app_code"])
        with self.assertRaises(Http404):
            self.detail()
