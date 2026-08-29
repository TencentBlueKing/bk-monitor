import os
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from qcloud_cos import CosServiceError

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.log_extract import (
    PHASES,
    get_log_extract_detail,
    list_log_extract_tasks,
    probe_log_extract_artifact,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_extract.constants import DownloadStatus
from apps.log_extract.models import ExtractLink, Tasks
from apps.utils.cos import QcloudCos


def create_link(link_type="common", **overrides):
    values = {
        "name": f"{link_type}-link",
        "link_type": link_type,
        "operator": "operator",
        "op_bk_biz_id": 2,
        "qcloud_secret_id": "",
        "qcloud_secret_key": "",
        "qcloud_cos_bucket": "",
        "qcloud_cos_region": "",
        "is_enable": True,
        "created_by": "operator",
    }
    values.update(overrides)
    return ExtractLink.objects.create(**values)


def create_task(link, **overrides):
    values = {
        "bk_biz_id": 2,
        "target_node_type": "INSTANCE",
        "ip_list": ["0:127.0.0.1:101"],
        "target_nodes": [{"bk_host_id": 101}],
        "file_path": ["/var/log/app.log"],
        "filter_type": "match_word",
        "filter_content": {"keyword": "ERROR"},
        "download_status": DownloadStatus.PIPELINE.value,
        "expiration_date": timezone.now() + timedelta(days=1),
        "pipeline_id": "pipeline-1",
        "pipeline_components_id": {"activities": {"component-1": {"name": "packing"}}},
        "job_task_id": 123,
        "task_process_info": None,
        "remark": None,
        "ex_data": {"0:127.0.0.1": {"file_count": 2, "all_origin_file_size": 100, "all_pack_file_size": 50}},
        "cos_file_name": "artifact.tar.gz",
        "link_id": link.link_id,
        "source_app_code": "bk_log_search",
        "created_by": "operator",
    }
    values.update(overrides)
    return Tasks.objects.create(**values)


class LogExtractEvidenceTest(TestCase):
    def test_list_filters_and_hides_host_path_failure_and_artifact_details(self):
        link = create_link()
        selected = create_task(link, download_status=DownloadStatus.FAILED.value)
        create_task(link, bk_biz_id=3, download_status=DownloadStatus.DOWNLOADABLE.value)

        result = list_log_extract_tasks(
            {"bk_biz_id": 2, "download_status": DownloadStatus.FAILED.value, "page": 1, "page_size": 20}
        )

        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(item["task_id"], selected.task_id)
        self.assertEqual(item["host_count"], 1)
        self.assertEqual(item["file_count"], 1)
        for hidden in ("ip_list", "file_path", "task_process_info", "cos_file_name"):
            self.assertNotIn(hidden, item)

    def test_list_filters_by_link_type_and_time_window(self):
        common = create_link("common")
        bkrepo = create_link("bk_repo")
        selected = create_task(common)
        create_task(bkrepo)
        now = timezone.now()
        Tasks.objects.filter(task_id=selected.task_id).update(created_at=now - timedelta(minutes=1))

        result = list_log_extract_tasks(
            {
                "link_type": "common",
                "created_from": (now - timedelta(minutes=2)).isoformat(),
                "created_to": now.isoformat(),
                "ordering": "created_at",
            }
        )

        self.assertEqual([item["task_id"] for item in result["items"]], [selected.task_id])

    def test_list_and_detail_reject_invalid_numeric_time_and_ordering_inputs(self):
        cases = (
            (lambda: list_log_extract_tasks({"ordering": "file_path"}), "unsupported ordering"),
            (lambda: list_log_extract_tasks({"page": True}), "page must be an integer"),
            (lambda: list_log_extract_tasks({"page": "invalid"}), "page must be an integer"),
            (lambda: list_log_extract_tasks({"page": 0}), "page must be positive"),
            (lambda: list_log_extract_tasks({"page_size": 101}), "page_size must be at most 100"),
            (
                lambda: list_log_extract_tasks({"created_from": "not-a-datetime"}),
                "created_from must be an ISO-8601 datetime",
            ),
        )
        for call, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValidationError, message):
                call()

    def test_detail_rejects_missing_task(self):
        with self.assertRaisesRegex(ValidationError, "log extract task does not exist"):
            get_log_extract_detail({"task_id": 999999})

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_detail_returns_pipeline_projection_and_does_not_update_task(self, mock_get_state):
        link = create_link()
        task = create_task(
            link,
            target_nodes=[
                {
                    "bk_host_id": 101,
                    "description": "token=target-secret https://target-user:target-pass@example.com/path",
                }
            ],
            filter_content={
                "keyword": "ERROR authorization: Bearer filter-bearer",
                "password": "filter-password",
            },
            task_process_info=(
                "failed token=top-secret password:another-secret "
                "authorization: Bearer bearer-secret https://user:pass@example.com/path"
            ),
        )
        mock_get_state.return_value = {
            "state": "RUNNING",
            "children": {
                "component-1": {
                    "state": "RUNNING",
                    "start_time": "2026-08-29 10:00:00",
                    "finish_time": None,
                    "retry_count": 1,
                    "inputs": {"secret": "never-return"},
                }
            },
        }
        before = (task.download_status, task.updated_at, task.task_process_info)

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(result["raw_status"], DownloadStatus.PIPELINE.value)
        self.assertEqual(result["phase"], "workflow_submitting")
        self.assertEqual(result["pipeline"]["probe_status"], "success")
        component = result["pipeline"]["data"]["components"][0]
        self.assertEqual(component["name"], "packing")
        self.assertNotIn("inputs", component)
        self.assertNotIn("top-secret", result["failure_reason"])
        self.assertNotIn("another-secret", result["failure_reason"])
        self.assertNotIn("bearer-secret", result["failure_reason"])
        self.assertNotIn("user:pass", result["failure_reason"])
        for sensitive in (
            "target-secret",
            "target-user:target-pass",
            "filter-bearer",
            "filter-password",
        ):
            self.assertNotIn(sensitive, str(result))
        self.assertTrue(result["cos_file_name_present"])
        self.assertTrue(result["artifact_reference_present"])
        self.assertNotIn("cos_file_name", result)
        self.assertTrue(result["pipeline"]["observed_at"])
        self.assertEqual(
            result["link"], {"link_id": link.link_id, "name": "common-link", "link_type": "common", "is_enable": True}
        )

        task.refresh_from_db()
        self.assertEqual((task.download_status, task.updated_at, task.task_process_info), before)

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_pipeline_failure_is_evidence_not_a_database_write(self, mock_get_state):
        link = create_link()
        task = create_task(link, download_status=DownloadStatus.PACKING.value)
        mock_get_state.return_value = {
            "state": "FAILED",
            "children": {
                "component-1": {
                    "state": "FAILED",
                    "start_time": "2026-08-29 10:00:00",
                    "finish_time": "2026-08-29 10:00:10",
                }
            },
        }

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(result["pipeline"]["data"]["failed_component_ids"], ["component-1"])
        self.assertEqual(result["pipeline"]["data"]["elapsed_seconds"], 10)
        self.assertIn(
            "PIPELINE_FAILED_WITH_NON_TERMINAL_TASK", [item["code"] for item in result["consistency_warnings"]]
        )
        task.refresh_from_db()
        self.assertEqual(task.download_status, DownloadStatus.PACKING.value)

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_pipeline_projection_skips_missing_children_and_tolerates_invalid_times(self, mock_get_state):
        link = create_link()
        task = create_task(
            link,
            pipeline_components_id={
                "activities": {"missing": {"name": "missing"}, "invalid-time": {"name": "invalid-time"}}
            },
        )
        mock_get_state.return_value = {
            "state": "RUNNING",
            "children": {"invalid-time": {"state": "RUNNING", "start_time": "bad", "finish_time": "also-bad"}},
        }

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual([item["component_id"] for item in result["pipeline"]["data"]["components"]], ["invalid-time"])
        self.assertEqual(result["pipeline"]["data"]["elapsed_seconds"], 0)

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_pipeline_provider_failure_preserves_database_evidence(self, mock_get_state):
        link = create_link()
        task = create_task(link)
        mock_get_state.side_effect = RuntimeError("pipeline unavailable")

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(result["task_id"], task.task_id)
        self.assertEqual(result["pipeline"]["probe_status"], "failed")
        self.assertTrue(result["pipeline"]["observed_at"])

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_detail_preserves_supported_target_node_types(self, mock_get_state):
        mock_get_state.return_value = {"state": "RUNNING", "children": {}}
        link = create_link()
        for node_type, target_nodes in (
            ("INSTANCE", [{"bk_host_id": 101}]),
            ("TOPO", [{"bk_obj_id": "module", "bk_inst_id": 3}]),
            ("SERVICE_TEMPLATE", [{"bk_inst_id": 4}]),
        ):
            with self.subTest(node_type=node_type):
                task = create_task(link, target_node_type=node_type, target_nodes=target_nodes)
                result = get_log_extract_detail({"task_id": task.task_id})
                self.assertEqual(result["target"]["target_node_type"], node_type)
                self.assertEqual(result["target"]["target_nodes"]["value"], target_nodes)

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_finished_pipeline_with_nonterminal_task_is_reported(self, mock_get_state):
        link = create_link()
        task = create_task(link, download_status=DownloadStatus.PACKING.value)
        mock_get_state.return_value = {"state": "FINISHED", "children": {}}

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertIn(
            "PIPELINE_FINISHED_WITH_NON_TERMINAL_TASK", [item["code"] for item in result["consistency_warnings"]]
        )

    def test_common_link_without_pipeline_or_artifact_reports_both_persisted_gaps(self):
        link = create_link("common")
        task = create_task(
            link,
            download_status=DownloadStatus.DOWNLOADABLE.value,
            pipeline_id=None,
            cos_file_name=None,
        )

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(result["pipeline"]["error"]["code"], "PIPELINE_ID_MISSING")
        self.assertEqual(
            [item["code"] for item in result["consistency_warnings"]],
            ["DOWNLOADABLE_WITHOUT_ARTIFACT_REFERENCE", "PIPELINE_ID_MISSING"],
        )

    @patch("apps.log_admin_resource.handlers.log_extract.task_service.get_state")
    def test_file_statistics_invalid_values_degrade_to_zero(self, mock_get_state):
        link = create_link()
        task = create_task(
            link,
            ex_data={"host": {"file_count": "bad", "all_origin_file_size": {}, "all_pack_file_size": None}},
        )
        mock_get_state.return_value = {"state": "RUNNING", "children": {}}

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(
            result["file_statistics"], {"host_count": 1, "file_count": 0, "original_size": 0, "packed_size": 0}
        )

    def test_bkrepo_without_runtime_id_is_explicit_mcp_gap(self):
        link = create_link("bk_repo")
        task = create_task(link, pipeline_id=None, pipeline_components_id=None)

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(result["pipeline"]["probe_status"], "skipped")
        self.assertEqual(result["pipeline"]["error"]["code"], "CELERY_RUNTIME_NOT_PERSISTED")
        self.assertTrue(result["evidence_scope"]["mcp_required"])
        self.assertIn("CELERY_RUNTIME_NOT_PERSISTED", [item["code"] for item in result["consistency_warnings"]])

    def test_downloadable_past_expiration_is_derived_without_writeback(self):
        link = create_link()
        task = create_task(
            link,
            download_status=DownloadStatus.DOWNLOADABLE.value,
            expiration_date=timezone.now() - timedelta(seconds=1),
        )

        result = get_log_extract_detail({"task_id": task.task_id})

        self.assertEqual(result["raw_status"], DownloadStatus.DOWNLOADABLE.value)
        self.assertEqual(result["effective_status"], DownloadStatus.EXPIRED.value)
        self.assertIn("DOWNLOADABLE_PAST_EXPIRATION", [item["code"] for item in result["consistency_warnings"]])
        task.refresh_from_db()
        self.assertEqual(task.download_status, DownloadStatus.DOWNLOADABLE.value)

    def test_status_mapping_covers_current_and_historical_values(self):
        expected = {
            DownloadStatus.INIT.value: "record_created",
            DownloadStatus.PIPELINE.value: "workflow_submitting",
            DownloadStatus.PACKING.value: "source_packaging",
            DownloadStatus.DISTRIBUTING.value: "transferring",
            DownloadStatus.DISTRIBUTING_PACKING.value: "transferring",
            DownloadStatus.UPLOADING.value: "artifact_uploading",
            DownloadStatus.CSTONE_UPLOADING.value: "artifact_uploading",
            DownloadStatus.COS_UPLOAD.value: "artifact_uploading",
            DownloadStatus.DOWNLOADABLE.value: "completed",
            DownloadStatus.EXPIRED.value: "artifact_expired",
            DownloadStatus.FAILED.value: "failed",
        }
        self.assertEqual(PHASES, expected)


class LogExtractArtifactProbeTest(TestCase):
    def test_common_probe_reads_only_file_metadata(self):
        link = create_link("common")
        with tempfile.TemporaryDirectory() as directory:
            file_path = os.path.join(directory, "artifact.tar.gz")
            with open(file_path, "wb") as file_object:
                file_object.write(b"12345")
            task = create_task(link, cos_file_name="artifact.tar.gz")
            before = (task.download_status, task.updated_at)

            with override_settings(EXTRACT_SAAS_STORE_DIR=directory):
                result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "success")
        self.assertTrue(result["artifact"]["exists"])
        self.assertEqual(result["artifact"]["data"]["size"], 5)
        task.refresh_from_db()
        self.assertEqual((task.download_status, task.updated_at), before)

    def test_common_probe_rejects_reference_outside_extract_directory(self):
        link = create_link("common")
        task = create_task(link, cos_file_name="../outside.tar.gz")
        with tempfile.TemporaryDirectory() as directory, override_settings(EXTRACT_SAAS_STORE_DIR=directory):
            result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "failed")

    def test_common_probe_rejects_symlink_outside_extract_directory(self):
        link = create_link("common")
        task = create_task(link, cos_file_name="artifact-link.tar.gz")
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            outside_path = os.path.join(outside, "outside.tar.gz")
            with open(outside_path, "wb") as file_object:
                file_object.write(b"outside")
            os.symlink(outside_path, os.path.join(directory, "artifact-link.tar.gz"))
            with override_settings(EXTRACT_SAAS_STORE_DIR=directory):
                result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "failed")
        self.assertIsNone(result["artifact"]["exists"])

    def test_missing_link_is_reported_without_storage_probe(self):
        link = create_link("common")
        task = create_task(link)
        ExtractLink.objects.filter(link_id=link.link_id).delete()

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["error"]["code"], "EXTRACT_LINK_MISSING")

    def test_unsupported_link_type_is_reported_without_storage_probe(self):
        link = create_link("custom")
        task = create_task(link)

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["error"]["code"], "UNSUPPORTED_LINK_TYPE")

    @patch("apps.log_admin_resource.handlers.log_extract.QcloudCos")
    def test_cos_probe_uses_head_only_and_never_generates_download_url(self, mock_cos):
        link = create_link(
            "qcloud_cos",
            qcloud_secret_id="secret-id",
            qcloud_secret_key="secret-key",
            qcloud_cos_bucket="bucket",
            qcloud_cos_region="region",
        )
        task = create_task(link)
        mock_cos.return_value.head_object.return_value = {"Content-Length": "99", "ETag": "etag"}

        result = probe_log_extract_artifact({"task_id": task.task_id})

        mock_cos.return_value.head_object.assert_called_once_with("artifact.tar.gz")
        mock_cos.return_value.get_download_url.assert_not_called()
        self.assertTrue(result["artifact"]["exists"])
        self.assertEqual(result["artifact"]["data"]["size"], 99)

    @patch("apps.log_admin_resource.handlers.log_extract.QcloudCos")
    def test_cos_not_found_is_a_successful_negative_probe(self, mock_cos):
        link = create_link("qcloud_cos")
        task = create_task(link)
        mock_cos.return_value.head_object.side_effect = CosServiceError("HEAD", {"code": "NoSuchKey"}, 404)

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "success")
        self.assertFalse(result["artifact"]["exists"])

    @patch("apps.log_admin_resource.handlers.log_extract.QcloudCos")
    def test_cos_provider_error_is_a_failed_probe(self, mock_cos):
        link = create_link("qcloud_cos")
        task = create_task(link)
        mock_cos.return_value.head_object.side_effect = CosServiceError("HEAD", {"code": "AccessDenied"}, 403)

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.log_extract.QcloudCos")
    def test_cos_invalid_size_is_kept_as_unknown_without_failing_probe(self, mock_cos):
        link = create_link("qcloud_cos")
        task = create_task(link)
        mock_cos.return_value.head_object.return_value = {"Content-Length": "invalid"}

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertTrue(result["artifact"]["exists"])
        self.assertIsNone(result["artifact"]["data"]["size"])

    @patch("apps.log_admin_resource.handlers.log_extract.QcloudCos")
    def test_unexpected_cos_error_is_a_failed_probe(self, mock_cos):
        link = create_link("qcloud_cos")
        task = create_task(link)
        mock_cos.return_value.head_object.side_effect = RuntimeError("cos unavailable")

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.log_extract.BKRepoStorage")
    def test_bkrepo_probe_uses_exists_and_size_without_url(self, mock_storage):
        link = create_link("bk_repo")
        task = create_task(link)
        mock_storage.return_value.exists.return_value = True
        mock_storage.return_value.size.return_value = 88

        result = probe_log_extract_artifact({"task_id": task.task_id})

        mock_storage.return_value.exists.assert_called_once_with("artifact.tar.gz")
        mock_storage.return_value.size.assert_called_once_with("artifact.tar.gz")
        self.assertFalse(mock_storage.return_value.url.called)
        self.assertEqual(result["artifact"]["data"]["size"], 88)

    @patch("apps.log_admin_resource.handlers.log_extract.BKRepoStorage")
    def test_bkrepo_provider_error_is_a_failed_probe(self, mock_storage):
        link = create_link("bk_repo")
        task = create_task(link)
        mock_storage.return_value.exists.side_effect = RuntimeError("bkrepo unavailable")

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.log_extract.BKRepoStorage")
    def test_downloadable_missing_artifact_returns_consistency_warning(self, mock_storage):
        link = create_link("bk_repo")
        task = create_task(link, download_status=DownloadStatus.DOWNLOADABLE.value)
        mock_storage.return_value.exists.return_value = False

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertFalse(result["artifact"]["exists"])
        self.assertEqual(result["consistency_warnings"][0]["code"], "DOWNLOADABLE_ARTIFACT_MISSING")

    def test_missing_artifact_reference_is_skipped_without_storage_calls(self):
        link = create_link("common")
        task = create_task(link, cos_file_name=None)

        result = probe_log_extract_artifact({"task_id": task.task_id})

        self.assertEqual(result["artifact"]["probe_status"], "skipped")
        self.assertEqual(result["artifact"]["error"]["code"], "ARTIFACT_REFERENCE_MISSING")


class QcloudCosMetadataTest(TestCase):
    @patch("apps.utils.cos.CosS3Client")
    @patch("apps.utils.cos.CosConfig")
    def test_head_object_delegates_to_sdk_metadata_api(self, mock_config, mock_client):
        mock_client.return_value.head_object.return_value = {"Content-Length": "1"}
        cos = QcloudCos("secret-id", "secret-key", "region", "bucket")

        result = cos.head_object("artifact.tar.gz")

        self.assertEqual(result, {"Content-Length": "1"})
        mock_client.return_value.head_object.assert_called_once_with(Bucket="bucket", Key="artifact.tar.gz")
        mock_client.return_value.get_presigned_download_url.assert_not_called()

    @override_settings(EXTRACT_COS_DOMAIN=None)
    @patch("apps.utils.cos.CosS3Client")
    @patch("apps.utils.cos.CosConfig")
    def test_download_url_without_acceleration_is_returned_unchanged(self, mock_config, mock_client):
        mock_client.return_value.get_presigned_download_url.return_value = "https://bucket.cos.region.myqcloud.com/a"
        cos = QcloudCos("secret-id", "secret-key", "region", "bucket")

        result = cos.get_download_url("artifact.tar.gz")

        self.assertEqual(result, "https://bucket.cos.region.myqcloud.com/a")

    @override_settings(EXTRACT_COS_DOMAIN="accelerate.example.com")
    @patch("apps.utils.cos.CosS3Client")
    @patch("apps.utils.cos.CosConfig")
    def test_download_url_rewrites_acceleration_domain(self, mock_config, mock_client):
        mock_client.return_value.get_presigned_download_url.return_value = "https://bucket.cos.region.myqcloud.com/a"
        cos = QcloudCos("secret-id", "secret-key", "region", "bucket")

        result = cos.get_download_url("artifact.tar.gz")

        self.assertEqual(result, "https://bucket.accelerate.example.com/a")

    @patch("apps.utils.cos.CosS3Client")
    @patch("apps.utils.cos.CosConfig")
    def test_upload_file_returns_sdk_etag(self, mock_config, mock_client):
        mock_client.return_value.put_object_from_local_file.return_value = {"ETag": "etag-1"}
        cos = QcloudCos("secret-id", "secret-key", "region", "bucket")

        result = cos.upload_file("/tmp/archive.tar.gz", "artifact.tar.gz")

        self.assertEqual(result, "etag-1")
        mock_client.return_value.put_object_from_local_file.assert_called_once_with(
            Bucket="bucket", LocalFilePath="/tmp/archive.tar.gz", Key="artifact.tar.gz"
        )


@override_settings(
    RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
)
class LogExtractRegistryTest(TestCase):
    def test_registry_lists_all_three_log_extract_evidence_handlers(self):
        result = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="resource-reader")

        self.assertIn("bklog.log_extract.list", result["functions"])
        self.assertIn("bklog.log_extract.detail", result["functions"])
        self.assertIn("bklog.log_extract.artifact_probe", result["functions"])
