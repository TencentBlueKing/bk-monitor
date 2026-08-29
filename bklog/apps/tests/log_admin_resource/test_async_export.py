from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.async_export import _phase, get_async_export_detail, list_async_exports
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_search.constants import ASYNC_EXPORT_SCENE_ID, ExportStatus, IndexSetType
from apps.log_search.models import AsyncTask


def create_task(**overrides):
    values = {
        "request_param": {"start_time": 1, "end_time": 2, "query_string": "error", "private_filter": "omit"},
        "sorted_param": [],
        "scenario_id": "log",
        "index_set_id": 10,
        "result": False,
        "exported_count": 1,
        "export_total_count": 10,
        "download_count": 3,
        "is_clean": False,
        "export_status": ExportStatus.DOWNLOAD_LOG,
        "start_time": "1",
        "end_time": "2",
        "export_type": "async",
        "bk_biz_id": 2,
        "source_app_code": "bk_log_search",
        "index_set_ids": [],
        "index_set_type": IndexSetType.SINGLE.value,
        "created_by": "operator",
    }
    values.update(overrides)
    return AsyncTask.objects.create(**values)


class AsyncExportEvidenceTest(TestCase):
    def test_list_filters_and_returns_summary_without_request_or_artifact_reference(self):
        selected = create_task(export_status=ExportStatus.FAILED, source_app_code="source-a")
        create_task(bk_biz_id=3, export_status=ExportStatus.SUCCESS, source_app_code="source-b")

        result = list_async_exports({"bk_biz_id": 2, "export_status": ExportStatus.FAILED, "page": 1, "page_size": 20})

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["task_id"], selected.id)
        self.assertNotIn("request_param", result["items"][0])
        self.assertNotIn("download_url", result["items"][0])
        self.assertNotIn("failed_reason", result["items"][0])

    def test_list_supports_time_window_and_ascending_order(self):
        older = create_task()
        newer = create_task()
        now = timezone.now()
        AsyncTask.objects.filter(id=older.id).update(created_at=now - timedelta(minutes=2))
        AsyncTask.objects.filter(id=newer.id).update(created_at=now - timedelta(minutes=1))

        result = list_async_exports(
            {
                "created_from": (now - timedelta(minutes=3)).isoformat(),
                "created_to": now.isoformat(),
                "ordering": "created_at",
            }
        )

        self.assertEqual([item["task_id"] for item in result["items"]], [older.id, newer.id])

    def test_list_rejects_invalid_ordering_pagination_and_datetime(self):
        cases = (
            ({"ordering": "request_param"}, "unsupported ordering"),
            ({"page": True}, "page must be an integer"),
            ({"page": "invalid"}, "page must be an integer"),
            ({"page": 0}, "page must be positive"),
            ({"page_size": 101}, "page_size must be at most 100"),
            ({"created_from": "not-a-datetime"}, "created_from must be an ISO-8601 datetime"),
        )
        for params, message in cases:
            with self.subTest(params=params), self.assertRaisesRegex(ValidationError, message):
                list_async_exports(params)

    def test_detail_rejects_missing_task(self):
        with self.assertRaisesRegex(ValidationError, "async export task does not exist"):
            get_async_export_detail({"task_id": 999999})

    def test_detail_returns_bounded_evidence_without_download_url_and_does_not_write(self):
        task = create_task(
            export_status=ExportStatus.FAILED,
            failed_reason=(
                "worker failed token=top-secret password:another-secret "
                "authorization: Bearer bearer-secret https://user:pass@example.com/path"
            ),
            file_name="export.tar.gz",
            file_size=1024,
            download_url="https://download.example/secret",
            request_param={
                "start_time": 1,
                "end_time": 2,
                "query_string": (
                    "error token=query-secret authorization: Bearer query-bearer "
                    "https://query-user:query-pass@example.com/path"
                ),
                "authorization": "do-not-return",
                "host_scopes": [{"bk_host_id": 1}],
            },
        )
        before = {
            "status": task.export_status,
            "download_count": task.download_count,
            "download_url": task.download_url,
            "updated_at": task.updated_at,
        }

        result = get_async_export_detail({"task_id": task.id})

        self.assertEqual(result["raw_status"], ExportStatus.FAILED)
        self.assertEqual(result["phase"], "failed")
        self.assertEqual(result["failure"]["stage"], "unknown")
        self.assertNotIn("top-secret", result["failure"]["reason"])
        self.assertNotIn("another-secret", result["failure"]["reason"])
        self.assertNotIn("bearer-secret", result["failure"]["reason"])
        self.assertNotIn("user:pass", result["failure"]["reason"])
        self.assertTrue(result["artifact"]["download_entry_present"])
        self.assertNotIn("download_url", result["artifact"])
        self.assertEqual(result["request_summary"]["included_fields"], ["end_time", "query_string", "start_time"])
        self.assertEqual(result["request_summary"]["omitted_field_count"], 2)
        self.assertNotIn("query-secret", str(result["request_summary"]))
        self.assertNotIn("query-bearer", str(result["request_summary"]))
        self.assertNotIn("query-user:query-pass", str(result["request_summary"]))
        self.assertEqual(result["evidence_scope"], "db_and_artifact")

        task.refresh_from_db()
        self.assertEqual(task.export_status, before["status"])
        self.assertEqual(task.download_count, before["download_count"])
        self.assertEqual(task.download_url, before["download_url"])
        self.assertEqual(task.updated_at, before["updated_at"])

    def test_status_mapping_covers_every_persisted_status_without_inventing_runtime(self):
        expected = {
            None: "record_created",
            "": "record_created",
            ExportStatus.DOWNLOAD_LOG: "querying_and_packaging",
            ExportStatus.EXPORT_PACKAGE: "uploading",
            ExportStatus.EXPORT_UPLOAD: "finalizing",
            ExportStatus.SUCCESS: "completed",
            ExportStatus.FAILED: "failed",
            ExportStatus.DOWNLOAD_EXPIRED: "artifact_expired",
            ExportStatus.DATA_EXPIRED: "unknown",
            "historical_value": "unknown",
        }
        for status, phase in expected.items():
            with self.subTest(status=status):
                self.assertEqual(_phase(status), phase)

    def test_target_summary_distinguishes_single_union_and_scene(self):
        single = create_task(index_set_id=10, index_set_type=IndexSetType.SINGLE.value)
        union = create_task(index_set_id=None, index_set_ids=[10, 11], index_set_type=IndexSetType.UNION.value)
        scene = create_task(scenario_id=ASYNC_EXPORT_SCENE_ID, index_set_id=None)

        self.assertEqual(get_async_export_detail({"task_id": single.id})["target"]["type"], "single")
        self.assertEqual(
            get_async_export_detail({"task_id": union.id})["target"], {"type": "union", "index_set_ids": [10, 11]}
        )
        self.assertEqual(get_async_export_detail({"task_id": scene.id})["target"]["type"], "scene")

    def test_non_positive_total_keeps_progress_ratio_unknown(self):
        task = create_task(export_total_count=-1, exported_count=0)

        result = get_async_export_detail({"task_id": task.id})

        self.assertIsNone(result["progress"]["ratio"])

    def test_consistency_warnings_only_report_observed_conflicts(self):
        task = create_task(
            export_status=ExportStatus.SUCCESS,
            download_url=None,
            exported_count=11,
            export_total_count=10,
        )
        AsyncTask.objects.filter(id=task.id).update(completed_at=task.created_at + timedelta(seconds=1))

        result = get_async_export_detail({"task_id": task.id})

        self.assertEqual(
            [item["code"] for item in result["consistency_warnings"]],
            ["SUCCESS_WITHOUT_DOWNLOAD_ENTRY", "EXPORTED_COUNT_EXCEEDS_TOTAL"],
        )

    def test_non_terminal_completed_time_and_expired_artifact_conflicts_are_separate(self):
        non_terminal = create_task(export_status=ExportStatus.EXPORT_PACKAGE, completed_at=timezone.now())
        expired = create_task(
            export_status=ExportStatus.DOWNLOAD_EXPIRED,
            download_url="https://download.example/file",
            is_clean=False,
        )
        AsyncTask.objects.filter(id=non_terminal.id).update(
            created_at=timezone.now(), completed_at=timezone.now() - timedelta(days=1)
        )

        non_terminal_result = get_async_export_detail({"task_id": non_terminal.id})
        expired_result = get_async_export_detail({"task_id": expired.id})

        self.assertEqual(
            [item["code"] for item in non_terminal_result["consistency_warnings"]],
            ["COMPLETED_BEFORE_CREATED", "NON_TERMINAL_WITH_COMPLETED_AT"],
        )
        self.assertEqual(
            [item["code"] for item in expired_result["consistency_warnings"]],
            ["EXPIRED_WITH_ACTIVE_ARTIFACT_REFERENCE"],
        )


@override_settings(
    RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
)
class AsyncExportRegistryTest(TestCase):
    def test_registry_lists_async_export_handlers_as_readonly_capabilities(self):
        result = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="resource-reader")

        self.assertIn("bklog.async_export.list", result["functions"])
        self.assertIn("bklog.async_export.detail", result["functions"])
