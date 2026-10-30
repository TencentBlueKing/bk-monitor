from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.sharded_export import (
    DETAIL_FUNC_NAME,
    FUNCTIONS,
    LIST_FUNC_NAME,
    get_sharded_export_job_detail,
    list_sharded_export_jobs,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params
from apps.log_search.constants import (
    ExportErrorCode,
    ExportJobStatus,
    ExportPartStatus,
    ExportPlanStatus,
    ExportSearchType,
    ExportStage,
    ExportStatus,
    IndexSetType,
)
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.log_search.models import AsyncTask, Space


def make_job(**overrides):
    values = {
        "space_uid": "bkcc__2",
        "bk_biz_id": 2,
        "created_by": "tester",
        "source_app_code": "bk_log_search",
        "index_set_ids": [10],
        "index_set_type": IndexSetType.SINGLE.value,
        "search_params": {
            "start_time": 0,
            "end_time": 4000,
            "keyword": "error token=search-secret",
            "addition": [{"field": "host", "operator": "=", "value": ["a"]}],
            "ip_chooser": {"host_list": [{"host_id": 1}]},
            "begin": 0,
        },
        "base_dict": {"query": "do-not-return"},
        "raw_params": {"keyword": "do-not-return"},
        "start_time": 0,
        "end_time": 4000,
    }
    values.update(overrides)
    return ExportJob.objects.create(**values)


def make_part(job, part_no, **overrides):
    values = {
        "job": job,
        "part_no": part_no,
        "plan_version": job.plan_version,
        "start_time": part_no * 1000,
        "end_time": (part_no + 1) * 1000,
        "status": ExportPartStatus.SUCCESS,
        "actual_rows": 10,
    }
    values.update(overrides)
    return ExportPart.objects.create(**values)


def make_success_job(**overrides):
    values = {
        "status": ExportJobStatus.SUCCESS,
        "plan_version": 1,
        "actual_total": 20,
        "merged_object_key": "exports/job/merged.jsonl.gz",
        "merged_bytes": 1024,
        "merged_checksum": "a" * 64,
        "manifest_object_key": "exports/job/manifest.json",
        "manifest_bytes": 128,
        "manifest_checksum": "b" * 64,
        "completed_at": timezone.now() + timedelta(seconds=1),
        "expires_at": timezone.now() + timedelta(days=1),
    }
    values.update(overrides)
    job = make_job(**values)
    ExportPlan.objects.create(job=job, plan_version=1, status=ExportPlanStatus.SUCCESS, planned_parts=2)
    make_part(job, 0)
    make_part(job, 1)
    return job


class ShardedExportListTest(TestCase):
    def test_list_filters_and_returns_bounded_summary(self):
        selected = make_job(status=ExportJobStatus.FAILED, error_code=ExportErrorCode.PART_RETRIES_EXHAUSTED)
        make_job(bk_biz_id=3, status=ExportJobStatus.SUCCESS)
        make_part(selected, 0, status=ExportPartStatus.FAILED)
        make_part(selected, 1, status=ExportPartStatus.SPLIT)

        result = list_sharded_export_jobs({"bk_biz_id": 2, "status": ExportJobStatus.FAILED})

        validate_params(result, FUNCTIONS[LIST_FUNC_NAME]["response_schema"], "response")
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["job_id"], selected.id)
        self.assertEqual(item["engine"], "sharded")
        self.assertEqual(item["user_export_status"], ExportStatus.FAILED)
        self.assertEqual(item["progress"]["parts_total"], 1)
        self.assertEqual(item["progress"]["parts_failed"], 1)
        for hidden in ("search_params", "base_dict", "raw_params", "merged_object_key", "manifest_object_key"):
            self.assertNotIn(hidden, item)

    def test_list_does_not_return_legacy_async_tasks(self):
        AsyncTask.objects.create(
            request_param={},
            sorted_param=[],
            scenario_id="log",
            index_set_id=10,
            result=False,
            export_status=ExportStatus.SUCCESS,
            start_time="1",
            end_time="2",
            export_type="async",
            bk_biz_id=2,
            index_set_ids=[],
            index_set_type=IndexSetType.SINGLE.value,
        )

        self.assertEqual(list_sharded_export_jobs({"bk_biz_id": 2})["total"], 0)

    def test_list_matches_single_union_and_scene_targets(self):
        single = make_job(index_set_ids=[10])
        union = make_job(index_set_ids=[10, 11], index_set_type=IndexSetType.UNION.value)
        scene = make_job(index_set_ids=[], search_type=ExportSearchType.SCENE)

        self.assertEqual(
            [item["job_id"] for item in list_sharded_export_jobs({"index_set_id": 10})["items"]], [single.id]
        )
        union_items = list_sharded_export_jobs({"index_set_ids": [10, 11]})["items"]
        self.assertEqual([item["job_id"] for item in union_items], [union.id])
        self.assertEqual(union_items[0]["target"], {"type": "union", "index_set_ids": [10, 11]})
        unordered_items = list_sharded_export_jobs({"index_set_ids": [11, 10, 11]})["items"]
        self.assertEqual([item["job_id"] for item in unordered_items], [union.id])
        scene_items = list_sharded_export_jobs({"search_type": ExportSearchType.SCENE})["items"]
        self.assertEqual([item["job_id"] for item in scene_items], [scene.id])
        self.assertEqual(scene_items[0]["target"]["type"], "scene")

    def test_list_supports_time_window_and_ascending_order(self):
        older = make_job()
        newer = make_job()
        now = timezone.now()
        ExportJob.objects.filter(id=older.id).update(created_at=now - timedelta(minutes=2))
        ExportJob.objects.filter(id=newer.id).update(created_at=now - timedelta(minutes=1))

        result = list_sharded_export_jobs(
            {
                "created_from": (now - timedelta(minutes=3)).isoformat(),
                "created_to": now.isoformat(),
                "ordering": "created_at",
            }
        )

        self.assertEqual([item["job_id"] for item in result["items"]], [older.id, newer.id])

    def test_list_rejects_invalid_ordering_pagination_and_datetime(self):
        cases = (
            ({"ordering": "base_dict"}, "unsupported ordering"),
            ({"page": 0}, "page must be positive"),
            ({"page_size": 101}, "page_size must be at most 100"),
            ({"created_from": "not-a-datetime"}, "created_from must be an ISO-8601 datetime"),
        )
        for params, message in cases:
            with self.subTest(params=params), self.assertRaisesRegex(ValidationError, message):
                list_sharded_export_jobs(params)


class ShardedExportDetailTest(TestCase):
    def test_detail_rejects_missing_job_and_unknown_part_status(self):
        with self.assertRaisesRegex(ValidationError, "sharded export job does not exist"):
            get_sharded_export_job_detail({"job_id": 999999})
        job = make_job()
        with self.assertRaisesRegex(ValidationError, "unsupported part_status"):
            get_sharded_export_job_detail({"job_id": job.id, "part_status": ["BROKEN"]})

    def test_success_job_returns_plan_progress_and_artifact_presence_without_internal_values(self):
        job = make_success_job()

        result = get_sharded_export_job_detail({"job_id": job.id})

        validate_params(result, FUNCTIONS[DETAIL_FUNC_NAME]["response_schema"], "response")
        self.assertEqual(result["user_export_status"], ExportStatus.SUCCESS)
        self.assertEqual(result["plan"]["plan_version"], 1)
        self.assertEqual(result["plan"]["current"]["planned_parts"], 2)
        self.assertEqual(result["progress"]["parts_success"], 2)
        self.assertEqual(result["progress"]["leaf_rows"], 20)
        self.assertEqual(result["artifact"]["merged"], {"present": True, "bytes": 1024, "checksum_present": True})
        self.assertFalse(result["artifact"]["expired"])
        self.assertEqual(result["consistency_warnings"], [])
        self.assertEqual(result["evidence_scope"], "db_only")
        self.assertEqual(
            result["request_summary"]["included_fields"], ["addition", "end_time", "keyword", "start_time"]
        )
        self.assertEqual(result["request_summary"]["omitted_field_count"], 2)
        serialized = str(result)
        for hidden in (
            "do-not-return",
            "search-secret",
            "host_list",
            "exports/job/merged.jsonl.gz",
            "exports/job/manifest.json",
            "a" * 64,
        ):
            self.assertNotIn(hidden, serialized)

    def test_progress_counts_follow_history_leaf_rules(self):
        job = make_job(status=ExportJobStatus.RUNNING, plan_version=1)
        parent = make_part(job, 0, status=ExportPartStatus.SPLIT, actual_rows=None)
        make_part(job, 1, status=ExportPartStatus.RUNNING, stage=ExportStage.DOWNLOAD_LOG, parent_part=parent)
        make_part(job, 2, status=ExportPartStatus.SUCCESS, parent_part=parent)
        make_part(job, 3, status=ExportPartStatus.FAILED, actual_rows=None)

        result = get_sharded_export_job_detail({"job_id": job.id})

        progress = result["progress"]
        self.assertEqual(progress["parts_total"], 3)
        self.assertEqual(progress["parts_success"], 1)
        self.assertEqual(progress["parts_failed"], 1)
        self.assertEqual(progress["status_counts"][ExportPartStatus.SPLIT], 1)
        self.assertEqual(progress["stage_counts"][ExportStage.DOWNLOAD_LOG], 1)
        self.assertEqual(progress["leaf_rows"], 20)
        self.assertEqual(result["consistency_warnings"][0]["code"], "CURRENT_PLAN_MISSING")

    def test_parts_are_bounded_prioritized_filtered_and_sanitized(self):
        job = make_job(status=ExportJobStatus.RUNNING)
        for part_no in range(3):
            make_part(job, part_no, status=ExportPartStatus.SUCCESS)
        make_part(job, 3, status=ExportPartStatus.RUNNING)
        failed = make_part(
            job,
            4,
            status=ExportPartStatus.FAILED,
            error_code=ExportErrorCode.FETCH_TIMEOUT,
            error_detail="query failed token=part-secret " + "x" * 2000,
            object_key="exports/job/part-4.jsonl.gz",
            task_id="celery-task-4",
        )

        result = get_sharded_export_job_detail({"job_id": job.id, "part_limit": 2})

        parts = result["parts"]
        self.assertEqual(parts["total"], 5)
        self.assertEqual(parts["returned_count"], 2)
        self.assertTrue(parts["truncated"])
        self.assertEqual(
            [item["status"] for item in parts["items"]], [ExportPartStatus.FAILED, ExportPartStatus.RUNNING]
        )
        failed_item = parts["items"][0]
        self.assertEqual(failed_item["part_id"], failed.id)
        self.assertEqual(failed_item["celery_task_id"], "celery-task-4")
        self.assertFalse(failed_item["artifact_present"])
        self.assertNotIn("part-secret", failed_item["error_detail"])
        self.assertLessEqual(len(failed_item["error_detail"]), 500)
        self.assertNotIn("exports/job/part-4.jsonl.gz", str(result))

        filtered = get_sharded_export_job_detail({"job_id": job.id, "part_status": [ExportPartStatus.SUCCESS]})
        self.assertEqual(filtered["parts"]["total"], 3)
        self.assertFalse(filtered["parts"]["truncated"])

    def test_failure_is_sanitized_and_labeled(self):
        job = make_job(
            status=ExportJobStatus.FAILED,
            error_code=ExportErrorCode.MERGE_FAILED,
            error_detail="merge failed password=job-secret",
            completed_at=timezone.now() + timedelta(seconds=1),
        )

        result = get_sharded_export_job_detail({"job_id": job.id})

        self.assertEqual(result["failure"]["error_code"], ExportErrorCode.MERGE_FAILED)
        self.assertTrue(result["failure"]["error_label"])
        self.assertNotIn("job-secret", result["failure"]["error_detail"])

    def test_consistency_warnings_report_observed_conflicts_only(self):
        job = make_success_job(merged_checksum="", manifest_object_key="", actual_total=99)
        make_part(job, 2, status=ExportPartStatus.FAILED, actual_rows=None)
        running = make_job(status=ExportJobStatus.RUNNING, completed_at=timezone.now())
        ExportJob.objects.filter(id=running.id).update(
            created_at=timezone.now(), completed_at=timezone.now() - timedelta(days=1)
        )
        canceled = make_job(status=ExportJobStatus.CANCELED, completed_at=None)

        self.assertEqual(
            [item["code"] for item in get_sharded_export_job_detail({"job_id": job.id})["consistency_warnings"]],
            [
                "SUCCESS_WITHOUT_MERGED_ARTIFACT",
                "SUCCESS_WITHOUT_MANIFEST",
                "SUCCESS_WITH_UNFINISHED_LEAF_PARTS",
                "ACTUAL_TOTAL_MISMATCH_LEAF_ROWS",
            ],
        )
        self.assertEqual(
            [item["code"] for item in get_sharded_export_job_detail({"job_id": running.id})["consistency_warnings"]],
            ["NON_TERMINAL_WITH_COMPLETED_AT", "COMPLETED_BEFORE_CREATED"],
        )
        self.assertEqual(
            [item["code"] for item in get_sharded_export_job_detail({"job_id": canceled.id})["consistency_warnings"]],
            ["TERMINAL_WITHOUT_COMPLETED_AT"],
        )

    def test_expired_artifact_is_reported(self):
        job = make_success_job(expires_at=timezone.now() - timedelta(minutes=1))

        result = get_sharded_export_job_detail({"job_id": job.id})

        self.assertTrue(result["artifact"]["expired"])
        self.assertEqual(result["user_export_status"], ExportStatus.DOWNLOAD_EXPIRED)

    def test_detail_does_not_write(self):
        job = make_success_job()
        before = ExportJob.objects.filter(id=job.id).values().get()

        get_sharded_export_job_detail({"job_id": job.id})

        self.assertEqual(ExportJob.objects.filter(id=job.id).values().get(), before)


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
class ShardedExportTenantScopeTest(TestCase):
    @staticmethod
    def create_space(bk_biz_id, tenant_id):
        return Space.objects.create(
            space_uid=f"bkcc__{bk_biz_id}",
            bk_biz_id=bk_biz_id,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id=str(bk_biz_id),
            space_name=f"biz-{bk_biz_id}",
            bk_tenant_id=tenant_id,
        )

    def setUp(self):
        self.create_space(2, "tenant-1")
        self.create_space(3, "tenant-2")
        self.own_job = make_job(space_uid="bkcc__2", bk_biz_id=2)
        self.other_job = make_job(space_uid="bkcc__3", bk_biz_id=3)

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-1")
    def test_list_only_returns_jobs_in_request_tenant(self, _mock_tenant):
        result = list_sharded_export_jobs({})
        self.assertEqual([item["job_id"] for item in result["items"]], [self.own_job.id])
        self.assertEqual(result["total"], 1)
        self.assertEqual(list_sharded_export_jobs({"bk_biz_id": 3})["total"], 0)

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="tenant-1")
    def test_detail_hides_other_tenant_job_as_missing(self, _mock_tenant):
        self.assertEqual(get_sharded_export_job_detail({"job_id": self.own_job.id})["job_id"], self.own_job.id)
        with self.assertRaisesRegex(ValidationError, "sharded export job does not exist"):
            get_sharded_export_job_detail({"job_id": self.other_job.id})

    @patch("apps.log_admin_resource.handlers.inspection.get_request_tenant_id", return_value="")
    def test_missing_request_tenant_fails_closed(self, _mock_tenant):
        with self.assertRaisesRegex(BklogPermissionError, "request tenant is required"):
            list_sharded_export_jobs({})
        with self.assertRaisesRegex(BklogPermissionError, "request tenant is required"):
            get_sharded_export_job_detail({"job_id": self.own_job.id})


@override_settings(RESOURCE_CALL_APP_CODE_WHITE_LIST=[])
class ShardedExportRegistryTest(TestCase):
    def test_registry_exposes_sharded_export_handlers_to_readonly_callers(self):
        result = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="resource-reader")

        self.assertIn(LIST_FUNC_NAME, result["functions"])
        self.assertIn(DETAIL_FUNC_NAME, result["functions"])
        capabilities = {item["func_name"]: item["safety_level"] for item in result["capabilities"]}
        self.assertEqual(capabilities[LIST_FUNC_NAME], "read")
        self.assertEqual(capabilities[DETAIL_FUNC_NAME], "inspect")

    def test_registry_validates_detail_params(self):
        with self.assertRaisesRegex(ValidationError, "job_id"):
            AdminResourceRegistry.call(DETAIL_FUNC_NAME, {}, app_code="resource-reader")
        with self.assertRaisesRegex(ValidationError, "part_limit"):
            AdminResourceRegistry.call(DETAIL_FUNC_NAME, {"job_id": 1, "part_limit": 201}, app_code="resource-reader")
