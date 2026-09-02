import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.exceptions import BaseException as BklogBaseException
from apps.exceptions import PermissionError as BklogPermissionError
from apps.exceptions import ValidationError
from apps.log_admin_resource.collector_probe import (
    PROBE_PROTOCOL,
    PROBE_VERSION,
    FixedProbeError,
    fixed_probe_arguments,
    fixed_probe_script,
    parse_probe_output,
)
from apps.log_admin_resource.collector_probe_evidence import build_probe_evidence
from apps.log_admin_resource.collector_probe_parsers import (
    classify_registrar_progress,
    fallback_matching_inputs,
    parse_registrar_strings,
    state_for_file,
)
from apps.log_admin_resource.handlers.host_inspection import (
    DETAIL_FUNC_NAME,
    DETAIL_RESPONSE_SCHEMA,
    FUNCTIONS,
    START_FUNC_NAME,
    START_RESPONSE_SCHEMA,
    _start_response,
    _validate_host_membership,
    get_host_inspection_detail,
    start_host_inspection,
)
from apps.log_admin_resource.inspection_tasks import (
    TASK_TYPE_HOST_INSPECTION,
    TASK_TYPE_K8S_INSPECTION,
    ResourceInspectionTaskRecord,
    request_fingerprint,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params
from apps.log_admin_resource.tasks import (
    _finish as finish_host_inspection,
    _fixed_remote_shell_script,
    _inspect_nodeman,
    _merge_context_intervals,
    _run_remote_inspection,
    filter_runtime_logs,
    run_host_inspection,
)
from apps.log_databus.constants import Environment


TEST_CACHES = {
    alias: {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "resource-host-inspection-tests",
    }
    for alias in ("default", "redis")
}


def task_cache():
    return caches["redis"]


def collector(**overrides):
    values = {
        "collector_config_id": 123,
        "bk_biz_id": 2,
        "bk_data_id": 1001,
        "subscription_id": 2001,
        "task_id_list": [3001],
        "is_active": True,
        "environment": Environment.LINUX,
        "is_container_collector": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def probe(status="success", code="ok", evidence=None):
    now = timezone.now().isoformat()
    return {
        "status": status,
        "code": code,
        "summary": code,
        "evidence": evidence,
        "warnings": [],
        "started_at": now,
        "finished_at": now,
        "duration_ms": 1,
    }


def parsed_probe(*, registrar_unavailable=None):
    values = {
        "protocol": PROBE_PROTOCOL,
        "probe_version": PROBE_VERSION,
        "completed": "true",
        "main_config_path": "/usr/local/gse/plugins/etc/bkunifylogbeat.conf",
        "first.collector.process_pid": "101",
        "first.collector.start_ticks": "10",
        "first.collector.cpu_ticks": "20",
        "first.collector.rss_pages": "3",
        "second.collector.process_pid": "101",
        "second.collector.start_ticks": "10",
        "second.collector.cpu_ticks": "22",
        "second.collector.rss_pages": "3",
        "page_size": "4096",
        "observation_seconds": "5",
        "observation_required_seconds": "5",
        "first.source_count": "0",
        "second.source_count": "0",
        "registrar_path": "/var/lib/gse/bkunifylogbeat.bkpipe.db",
        "collector_file_log_count": "1",
    }
    if registrar_unavailable:
        values["first.registrar_unavailable"] = registrar_unavailable
        values["second.registrar_unavailable"] = registrar_unavailable
    return {
        "values": values,
        "streams": {
            "main_config": {"path": values["main_config_path"], "content": "path.data: /var/lib/gse\n"},
            "child_config.0": {
                "path": "/usr/local/gse/plugins/etc/bkunifylogbeat/1001.conf",
                "content": "local:\n  - dataid: 1001\n    paths:\n      - /data/app/*.log\n",
            },
            "first.registrar_strings": {"content": ""},
            "second.registrar_strings": {"content": ""},
            "collector_file_log.0": {
                "path": "/var/log/gse/bkunifylogbeat.log",
                "content": "collector healthy",
                "returned_size_bytes": 17,
                "total_size_bytes": 17,
                "truncated": False,
            },
        },
        "metadata": {"probe_id": "bklog.collector.fixed_read_only"},
    }


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class ResourceInspectionTaskRecordTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()

    def tearDown(self):
        task_cache().clear()

    def test_record_reuses_same_app_and_tenant_but_not_cross_app(self):
        target = {"collector_config_id": 1, "bk_host_id": 2}
        first, reused = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a", bk_tenant_id="tenant-a", target=target, request_options={}
        )
        second, reused_second = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a", bk_tenant_id="tenant-a", target=target, request_options={}
        )

        self.assertFalse(reused)
        self.assertTrue(reused_second)
        self.assertEqual(first["task_id"], second["task_id"])
        with self.assertRaisesRegex(RuntimeError, "active task"):
            ResourceInspectionTaskRecord.create_or_reuse(
                app_code="reader-b", bk_tenant_id="tenant-a", target=target, request_options={}
            )

    def test_record_stores_compressed_result_separately(self):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )

        ResourceInspectionTaskRecord.store_result(record["task_id"], {"payload": "value" * 100})

        stored_record = ResourceInspectionTaskRecord.get(record["task_id"])
        self.assertNotIn("result", stored_record)
        self.assertEqual(ResourceInspectionTaskRecord.load_result(record["task_id"])["payload"], "value" * 100)

    def test_record_failure_releases_active_key(self):
        target = {"collector_config_id": 1, "bk_host_id": 2}

        with patch.object(task_cache(), "set", side_effect=RuntimeError("redis down")):
            with self.assertRaisesRegex(RuntimeError, "redis down"):
                ResourceInspectionTaskRecord.create_or_reuse(
                    app_code="reader-a", bk_tenant_id="tenant-a", target=target, request_options={}
                )

        fingerprint = request_fingerprint(task_type=TASK_TYPE_HOST_INSPECTION, target=target, request_options={})
        self.assertIsNone(
            task_cache().get(
                ResourceInspectionTaskRecord._active_key(task_type=TASK_TYPE_HOST_INSPECTION, fingerprint=fingerprint)
            )
        )

    def test_timeout_is_normalized_and_active_key_is_released(self):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )
        record["deadline_at"] = "2000-01-01T00:00:00+00:00"
        ResourceInspectionTaskRecord.save(record)

        normalized = ResourceInspectionTaskRecord.normalize_timeout(record)

        self.assertEqual(normalized["task_status"], "timed_out")
        self.assertIsNone(
            task_cache().get(
                ResourceInspectionTaskRecord._active_key(
                    task_type=record["task_type"], fingerprint=record["request_fingerprint"]
                )
            )
        )

    def test_redis_owner_release_uses_atomic_compare_and_delete(self):
        redis_client = MagicMock()
        adapter = SimpleNamespace(
            get_client=lambda write: redis_client,
            encode=lambda value: ("encoded:" + value).encode(),
        )
        backend = SimpleNamespace(client=adapter, make_key=lambda key: "prefix:" + key)

        with patch.object(ResourceInspectionTaskRecord, "cache", return_value=backend):
            ResourceInspectionTaskRecord._delete_if_owner("active-key", "task-id")

        redis_client.eval.assert_called_once()
        args = redis_client.eval.call_args.args
        self.assertEqual(args[2], "prefix:active-key")
        self.assertEqual(args[3], b"encoded:task-id")


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class HostInspectionHandlerTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()

    def tearDown(self):
        task_cache().clear()

    @patch("apps.log_admin_resource.tasks.run_host_inspection.apply_async")
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_host_membership")
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.host_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_start_dispatches_public_task_with_internal_celery_id(
        self, _identity, _get_collector, _validate_collector, _membership, mock_apply_async
    ):
        result = start_host_inspection(
            {
                "collector_config_id": 123,
                "bk_host_id": 99,
                "runtime_log_options": {
                    "keywords": ["1600123", 'reload "failed"; $(ignored)'],
                    "match": "all",
                    "context_lines": 3,
                },
            }
        )

        validate_params(result, START_RESPONSE_SCHEMA, "response")
        kwargs = mock_apply_async.call_args.kwargs
        self.assertEqual(kwargs["args"], [result["task_id"]])
        self.assertNotEqual(kwargs["task_id"], result["task_id"])
        record = ResourceInspectionTaskRecord.get(result["task_id"])
        self.assertEqual(record["request_options"]["runtime_log_options"]["match"], "all")

    @patch("apps.log_admin_resource.tasks.run_host_inspection.apply_async")
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_host_membership")
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.host_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_start_reuses_active_task_without_second_dispatch(
        self, _identity, _get_collector, _validate_collector, _membership, mock_apply_async
    ):
        first = start_host_inspection({"collector_config_id": 123, "bk_host_id": 99})
        second = start_host_inspection({"collector_config_id": 123, "bk_host_id": 99})

        self.assertEqual(first["task_id"], second["task_id"])
        self.assertTrue(second["reused"])
        mock_apply_async.assert_called_once()

    @patch("apps.log_admin_resource.tasks.run_host_inspection.apply_async", side_effect=RuntimeError("broker down"))
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_host_membership")
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.host_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_dispatch_failure_cleans_record_and_active_key(
        self, _identity, _get_collector, _validate_collector, _membership, _apply_async
    ):
        target = {"collector_config_id": 123, "bk_host_id": 99}

        with self.assertRaisesRegex(BklogBaseException, "dispatch failed"):
            start_host_inspection({"collector_config_id": 123, "bk_host_id": 99})

        active_key = ResourceInspectionTaskRecord._active_key(
            task_type=TASK_TYPE_HOST_INSPECTION,
            fingerprint=request_fingerprint(
                task_type=TASK_TYPE_HOST_INSPECTION,
                target={
                    "collector_config_id": 123,
                    "bk_host_id": 99,
                    "bk_biz_id": 2,
                    "bk_data_id": 1001,
                    "subscription_id": 2001,
                    "source": None,
                    "include_source_sample": False,
                },
                request_options={
                    "source": None,
                    "include_source_sample": False,
                    "runtime_log_options": {
                        "keywords": [],
                        "match": "any",
                        "case_sensitive": False,
                        "context_lines": 0,
                    },
                },
            ),
        )
        self.assertIsNone(task_cache().get(active_key))
        self.assertEqual(target, {"collector_config_id": 123, "bk_host_id": 99})

    @patch("apps.log_admin_resource.tasks.run_host_inspection.apply_async")
    @patch(
        "apps.log_admin_resource.handlers.host_inspection.ResourceInspectionTaskRecord.create_or_reuse",
        side_effect=RuntimeError("redis down"),
    )
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_host_membership")
    @patch("apps.log_admin_resource.handlers.host_inspection._validate_collector", return_value="tenant-a")
    @patch("apps.log_admin_resource.handlers.host_inspection._get_collector", return_value=collector())
    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_record_failure_never_dispatches(
        self, _identity, _get_collector, _validate_collector, _membership, _create, mock_apply_async
    ):
        with self.assertRaisesRegex(BklogBaseException, "storage is unavailable"):
            start_host_inspection({"collector_config_id": 123, "bk_host_id": 99})
        mock_apply_async.assert_not_called()

    @patch("apps.log_admin_resource.handlers.host_inspection.Space.get_tenant_id", return_value="tenant-a")
    def test_non_linux_collector_is_rejected_before_remote_execution(self, _tenant):
        from apps.log_admin_resource.handlers.host_inspection import _validate_collector

        with self.assertRaisesRegex(ValidationError, "unsupported_os"):
            _validate_collector(collector(environment=Environment.WINDOWS), "tenant-a")

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    @patch("apps.log_admin_resource.handlers.host_inspection.Space.get_tenant_id", return_value=None)
    def test_collector_without_tenant_mapping_fails_closed(self, _tenant):
        from apps.log_admin_resource.handlers.host_inspection import _validate_collector

        with self.assertRaisesRegex(BklogPermissionError, "tenant is not configured"):
            _validate_collector(collector(), "tenant-a")

    @patch("apps.log_admin_resource.handlers.host_inspection.NodeApi.query_host_subscriptions", return_value=[])
    def test_host_must_belong_to_exact_collector_subscription(self, mock_query):
        with self.assertRaisesRegex(ValidationError, "host_not_in_collector_subscription"):
            _validate_host_membership(collector(), 99, "tenant-a")
        mock_query.assert_called_once_with(
            params={
                "bk_biz_id": 2,
                "bk_host_id": 99,
                "source_type": "subscription",
                "no_request": True,
                "bk_tenant_id": "tenant-a",
            },
            request_cookies=False,
            bk_tenant_id="tenant-a",
        )

    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_detail_returns_evidence_without_internal_ids(self, _identity):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={
                "collector_config_id": 123,
                "bk_host_id": 99,
                "bk_biz_id": 2,
                "bk_data_id": 1001,
                "subscription_id": 2001,
                "source": None,
                "include_source_sample": False,
            },
            request_options={},
        )
        ResourceInspectionTaskRecord.store_result(
            record["task_id"],
            {
                "problem_env": "bkte",
                "source_env": "bkte",
                "observed_at": timezone.now().isoformat(),
                "target": {
                    "collector_config_id": 123,
                    "bk_host_id": 99,
                    "bk_biz_id": 2,
                    "bk_data_id": 1001,
                    "subscription_id": 2001,
                },
                "remote_execution": {
                    "executor": "JOB",
                    "mode": "server_fixed_read_only_script",
                    "mutations_permitted": False,
                },
                "probes": {"config": probe()},
                "partial": False,
                "error": None,
            },
        )
        ResourceInspectionTaskRecord.update(
            record["task_id"],
            task_status="success",
            phase="completed",
            probes={"config": ResourceInspectionTaskRecord._probe_summary(probe())},
            celery_task_id="internal-celery",
            job_instance_id=12345,
            job_step_instance_id=67890,
        )

        result = get_host_inspection_detail({"task_id": record["task_id"]})

        validate_params(result, DETAIL_RESPONSE_SCHEMA, "response")
        serialized = json.dumps(result)
        self.assertEqual(result["task_status"], "success")
        self.assertNotIn("internal-celery", serialized)
        self.assertNotIn("job_instance_id", serialized)
        self.assertNotIn("job_step_instance_id", serialized)

    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-b", "tenant-a"))
    def test_cross_app_detail_is_indistinguishable_from_missing_task(self, _identity):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )

        result = get_host_inspection_detail({"task_id": record["task_id"]})

        self.assertEqual(result["task_status"], "not_found")
        self.assertIsNone(result["target"])

    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_k8s_task_is_indistinguishable_from_missing_host_task(self, _identity):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-1"},
            request_options={},
            task_type=TASK_TYPE_K8S_INSPECTION,
        )

        result = get_host_inspection_detail({"task_id": record["task_id"]})

        self.assertEqual(result["task_status"], "not_found")
        self.assertIsNone(result["target"])

    @patch("apps.log_admin_resource.handlers.host_inspection._request_identity", return_value=("reader-a", "tenant-a"))
    def test_expired_result_is_distinct_from_missing_task(self, _identity):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={
                "collector_config_id": 1,
                "bk_host_id": 2,
                "bk_biz_id": 3,
                "bk_data_id": 4,
                "subscription_id": 5,
                "source": None,
                "include_source_sample": False,
            },
            request_options={},
        )
        record["task_status"] = "success"
        record["result_expires_at"] = "2000-01-01T00:00:00+00:00"
        ResourceInspectionTaskRecord.save(record)

        result = get_host_inspection_detail({"task_id": record["task_id"]})

        self.assertEqual(result["task_status"], "expired")
        self.assertEqual(result["error"]["code"], "task_expired")

    def test_registry_exposes_both_host_inspection_functions(self):
        metadata = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="reader-a")

        self.assertIn(START_FUNC_NAME, metadata["functions"])
        self.assertIn(DETAIL_FUNC_NAME, metadata["functions"])
        self.assertTrue(FUNCTIONS[START_FUNC_NAME]["validate_params"])

    def test_runtime_log_schema_accepts_literal_newline_and_rejects_regex_option(self):
        schema = FUNCTIONS[START_FUNC_NAME]["params_schema"]

        validate_params(
            {
                "collector_config_id": 123,
                "bk_host_id": 99,
                "runtime_log_options": {"keywords": ["line one\nline two"]},
            },
            schema,
        )
        with self.assertRaises(ValidationError):
            validate_params(
                {
                    "collector_config_id": 123,
                    "bk_host_id": 99,
                    "runtime_log_options": {"keywords": ["error.*timeout"], "regex": True},
                },
                schema,
            )

    def test_start_response_schema_allows_fast_terminal_task(self):
        now = timezone.now().isoformat()
        response = _start_response(
            {
                "task_id": "94a4c1a8-fb24-49b4-9bfa-b2dc724f07d5",
                "task_status": "failed",
                "created_at": now,
                "result_expires_at": now,
            },
            reused=False,
        )

        validate_params(response, START_RESPONSE_SCHEMA, "response")


class RuntimeLogFilterTest(SimpleTestCase):
    def test_literal_any_filter_merges_overlapping_contexts(self):
        evidence = {
            "files": [
                {
                    "path": "/var/log/gse/bkunifylogbeat.err",
                    "start_offset_bytes": 10,
                    "end_offset_bytes": 100,
                    "content": "before\nReload Failed\nmiddle\n1600123 received\nafter",
                }
            ],
            "truncated": True,
        }

        result = filter_runtime_logs(
            evidence,
            {"keywords": ["reload failed", "1600123"], "match": "any", "case_sensitive": False, "context_lines": 1},
        )

        filtered = result["files"][0]["filter_result"]
        self.assertEqual(filtered["matched_lines"], 2)
        self.assertEqual([item["line_number"] for item in filtered["lines"]], [1, 2, 3, 4, 5])
        self.assertNotIn("content", result["files"][0])
        self.assertEqual(result["filter"]["scanned_lines"], 5)
        self.assertTrue(result["filter"]["truncated"])

    def test_literal_all_filter_treats_shell_metacharacters_as_plain_text(self):
        keyword = 'value "quoted"; $(not-a-command) * ? [x]'
        evidence = {"files": [{"path": "x", "content": f"prefix {keyword} suffix\nother"}], "truncated": False}

        result = filter_runtime_logs(
            evidence,
            {"keywords": ["quoted", "$(not-a-command)", "* ?"], "match": "all", "case_sensitive": True},
        )

        self.assertEqual(result["filter"]["matched_lines"], 1)

    def test_zero_match_states_bounded_scan_scope(self):
        evidence = {"files": [{"path": "x", "content": "one\ntwo"}], "truncated": False}

        result = filter_runtime_logs(evidence, {"keywords": ["missing"], "match": "any"})

        self.assertEqual(result["filter"]["matched_lines"], 0)
        self.assertIn("does not cover all historical logs", result["filter"]["scope_statement"])

    def test_case_sensitive_and_newline_keywords_are_plain_literals(self):
        evidence = {"files": [{"path": "x", "content": "Error\nline one\nline two"}], "truncated": False}

        result = filter_runtime_logs(
            evidence,
            {"keywords": ["error", "line one\nline two"], "match": "any", "case_sensitive": True},
        )

        self.assertEqual(result["filter"]["matched_lines"], 0)

    def test_context_interval_merging_does_not_duplicate_lines(self):
        self.assertEqual(_merge_context_intervals([2, 4, 9], 2, 12), [(0, 6), (7, 11)])


@override_settings(CACHES=TEST_CACHES, BK_APP_TENANT_ID="tenant-a", ENVIRONMENT="bkte")
class HostInspectionWorkerTest(SimpleTestCase):
    def setUp(self):
        task_cache().clear()

    def tearDown(self):
        task_cache().clear()

    @patch("apps.log_admin_resource.tasks.NodeApi.plugin_search")
    @patch("apps.log_admin_resource.handlers.host_inspection.NodeApi.query_host_subscriptions", return_value=[])
    def test_worker_revalidates_host_subscription_before_nodeman_lookup(self, _membership, plugin_search):
        result, setup_path = _inspect_nodeman(
            {
                "bk_tenant_id": "tenant-a",
                "target": {"bk_biz_id": 2, "bk_host_id": 99, "subscription_id": 2001},
            }
        )

        self.assertEqual(result["code"], "host_not_in_collector_subscription")
        self.assertIsNone(setup_path)
        plugin_search.assert_not_called()

    def test_oversized_final_result_is_compacted_and_reaches_terminal_state(self):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )
        oversized = probe(evidence={"blob": "x" * (ResourceInspectionTaskRecord.MAX_RESULT_BYTES + 1)})

        finish_host_inspection(record["task_id"], record, {"runtime": oversized}, task_status="success", error=None)

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        result = ResourceInspectionTaskRecord.load_result(record["task_id"])
        self.assertEqual(stored["task_status"], "partial")
        self.assertEqual(result["probes"]["response_limit"]["code"], "response_compacted")

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_worker_persists_success_and_probe_summaries(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2, "bk_data_id": 1001},
            request_options={"runtime_log_options": {}},
        )
        mock_nodeman.return_value = (probe(evidence={"setup_path": "/usr/local/gse"}), "/usr/local/gse")
        mock_remote.return_value = parsed_probe()

        run_host_inspection.run(record["task_id"])

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        result = ResourceInspectionTaskRecord.load_result(record["task_id"])
        self.assertEqual(stored["task_status"], "success")
        self.assertEqual(
            set(stored["probes"]),
            {
                "nodeman",
                "main_config_mounted",
                "collector_process",
                "sidecar_process",
                "source_path",
                "registrar",
                "progress",
                "collector_logs",
            },
        )
        self.assertIn("main_config_mounted", result["probes"])

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_worker_preserves_successful_probe_when_sibling_fails(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2, "bk_data_id": 1001},
            request_options={},
        )
        mock_nodeman.return_value = (probe(), "/usr/local/gse")
        mock_remote.return_value = parsed_probe(registrar_unavailable="strings_missing")

        run_host_inspection.run(record["task_id"])

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        self.assertEqual(stored["task_status"], "partial")
        self.assertEqual(
            ResourceInspectionTaskRecord.load_result(record["task_id"])["probes"]["main_config_mounted"]["status"],
            "success",
        )

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_remote_script_failure_preserves_nodeman_as_partial_with_error(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )
        mock_nodeman.return_value = (probe(), "/usr/local/gse")
        mock_remote.side_effect = RuntimeError("remote probe failed")

        run_host_inspection.run(record["task_id"])

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        result = ResourceInspectionTaskRecord.load_result(record["task_id"])
        self.assertEqual(stored["task_status"], "partial")
        self.assertEqual(result["error"]["code"], "inspection_execution_failed")

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_fixed_probe_error_preserves_specific_code(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2, "bk_data_id": 1001},
            request_options={},
        )
        mock_nodeman.return_value = (probe(), "/usr/local/gse")
        mock_remote.side_effect = FixedProbeError("probe_incomplete", "completion marker missing", retryable=False)

        run_host_inspection.run(record["task_id"])

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        result = ResourceInspectionTaskRecord.load_result(record["task_id"])
        self.assertEqual(stored["task_status"], "partial")
        self.assertEqual(result["error"]["code"], "probe_incomplete")
        self.assertEqual(result["probes"]["collector_probe"]["code"], "probe_incomplete")

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_worker_does_not_publish_success_after_resource_deadline(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )
        record["deadline_at"] = "2000-01-01T00:00:00+00:00"
        ResourceInspectionTaskRecord.save(record)
        mock_nodeman.return_value = (probe(), "/usr/local/gse")
        mock_remote.return_value = parsed_probe()

        run_host_inspection.run(record["task_id"])

        stored = ResourceInspectionTaskRecord.get(record["task_id"])
        self.assertEqual(stored["task_status"], "timed_out")
        mock_nodeman.assert_not_called()
        mock_remote.assert_not_called()

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_duplicate_celery_delivery_does_not_repeat_execution(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )
        self.assertTrue(ResourceInspectionTaskRecord.claim_execution(record["task_id"]))

        run_host_inspection.run(record["task_id"])

        mock_nodeman.assert_not_called()
        mock_remote.assert_not_called()

    @patch("apps.log_admin_resource.tasks._run_remote_inspection")
    @patch("apps.log_admin_resource.tasks._inspect_nodeman")
    def test_nodeman_failure_does_not_dispatch_job(self, mock_nodeman, mock_remote):
        record, _ = ResourceInspectionTaskRecord.create_or_reuse(
            app_code="reader-a",
            bk_tenant_id="tenant-a",
            target={"collector_config_id": 1, "bk_host_id": 2},
            request_options={},
        )
        mock_nodeman.return_value = (probe(status="failed", code="unsupported_os"), None)

        run_host_inspection.run(record["task_id"])

        mock_remote.assert_not_called()
        self.assertEqual(ResourceInspectionTaskRecord.get(record["task_id"])["task_status"], "failed")

    @patch("apps.log_admin_resource.tasks.ResourceInspectionTaskRecord.update")
    @patch("apps.log_admin_resource.tasks.ResourceInspectionTaskRecord.set_internal_execution_ids")
    @patch("apps.log_admin_resource.tasks.JobApi.batch_get_job_instance_ip_log")
    @patch("apps.log_admin_resource.tasks.JobApi.get_job_instance_status")
    @patch("apps.log_admin_resource.tasks.JobHelper.execute_script")
    @patch("apps.log_admin_resource.tasks.JobHelper.adapt_hosts_target_server", return_value={"host_id_list": [2]})
    def test_runtime_keywords_never_enter_remote_job_payload(
        self, _adapt, execute, get_status, get_logs, _set_ids, _update
    ):
        execute.return_value = {"job_instance_id": 11, "step_instance_id": 22}
        get_status.return_value = {
            "finished": True,
            "step_instance_list": [{"step_instance_id": 22, "step_ip_result_list": [{"bk_host_id": 2, "status": 9}]}],
        }
        get_logs.return_value = {
            "script_task_logs": [
                {
                    "log_content": "\n".join(
                        [
                            f"BKLOG_KV\tprotocol\t{PROBE_PROTOCOL}",
                            f"BKLOG_KV\tprobe_version\t{PROBE_VERSION}",
                            "BKLOG_KV\tmanifest_kv_count\t2",
                            "BKLOG_KV\tmanifest_stream_count\t0",
                            "BKLOG_KV\toutput_budget_bytes\t4194304",
                            "BKLOG_KV\toutput_budget_exhausted\tfalse",
                            "BKLOG_KV\tcompleted\ttrue",
                        ]
                    )
                }
            ]
        }
        record = {
            "task_id": "public-task",
            "bk_tenant_id": "tenant-a",
            "target": {"bk_biz_id": 2, "bk_host_id": 2, "bk_data_id": 1001, "subscription_id": 2001},
            "request_options": {
                "source": "/data/app.log",
                "include_source_sample": False,
                "runtime_log_options": {"keywords": ["$(touch /tmp/never)", "reload failed"]},
            },
        }

        _run_remote_inspection(record)

        kwargs = execute.call_args.kwargs
        self.assertEqual(kwargs["script_language"], 1)
        self.assertEqual(
            base64.b64decode(kwargs["script_param"]).decode("ascii"),
            "1001 0 bkunifylogbeat_sub_2001",
        )
        script = fixed_probe_script().decode("utf-8")
        self.assertNotIn("/data/app.log", script)
        self.assertNotIn("reload failed", script)
        self.assertNotIn("touch", script)


class FixedRemoteScriptTest(SimpleTestCase):
    def test_host_job_uses_the_exact_shared_shell_probe(self):
        script = _fixed_remote_shell_script()

        self.assertEqual(script, fixed_probe_script())
        decoded = script.decode("utf-8")
        self.assertTrue(decoded.startswith("#!/bin/sh"))
        self.assertNotIn("python", decoded.lower())
        self.assertIn(PROBE_PROTOCOL, decoded)
        self.assertIn(PROBE_VERSION, decoded)

    def test_shared_probe_accepts_only_typed_server_arguments_and_performs_no_file_writes(self):
        script = fixed_probe_script().decode("utf-8")

        self.assertIn("accepts only server-controlled typed arguments", script)
        self.assertIn('[ "$#" -ne 3 ]', script)
        self.assertIn("TARGET_DATA_ID=$1", script)
        self.assertIn("INCLUDE_SOURCE_SAMPLE=$2", script)
        self.assertIn("TARGET_CONFIG_HINTS=$3", script)
        self.assertNotIn("$@", script)
        self.assertNotIn("/tmp", script)
        self.assertNotIn("mktemp", script)
        self.assertNotIn("kubectl", script)
        self.assertNotIn("eval ", script)
        self.assertNotIn(' > "', script)
        self.assertNotIn('[ -L "$blob_path" ]', script)
        self.assertIn('find -H "$directory"', script)
        self.assertIn("MAX_CHILD_CONFIG_SCAN=1000", script)
        self.assertIn('-name "$hint" -o -name "*_$hint"', script)
        self.assertIn('-name "$hint.conf" -o -name "${hint}_*.conf"', script)
        self.assertIn('-name "*${hint}.conf" -o -name "*${hint}_*.conf"', script)
        self.assertIn('if [ "$target_config_hint_count" -gt 0 ]; then', script)
        self.assertIn("all_child_paths=$(printf '%s\\n' \"$hinted_child_paths\"", script)
        self.assertIn('awk -v wanted="$TARGET_DATA_ID"', script)
        self.assertIn("child_paths=$(printf '%s\\n' \"$matching_child_paths\"", script)
        self.assertIn("-name 'bkunifylogbeat'", script)
        self.assertIn("/usr/local/gse*/plugins/etc/bkunifylogbeat.conf", script)

    def test_shared_probe_rejects_caller_shaped_config_hints(self):
        for hint in ("../secret.conf", "/data/etc/secret.conf", "*.conf", "a,b.conf"):
            with self.subTest(hint=hint), self.assertRaises(ValueError):
                fixed_probe_arguments(1001, False, [hint])

    def test_shared_probe_resolves_relative_main_config_from_process_runtime(self):
        script = fixed_probe_script().decode("utf-8")

        self.assertIn('process_cwd=$(readlink "/proc/$process_pid/cwd"', script)
        self.assertIn('process_binary_path=$(readlink "/proc/$process_pid/exe"', script)
        self.assertIn('main_config_source="process_argument_relative_cwd"', script)
        self.assertIn('main_config_source="process_argument_relative_binary"', script)
        self.assertIn('canonical_main_config=$(readlink -f "$main_config"', script)

    def test_job_log_prefix_does_not_hide_shared_protocol(self):
        parsed = parse_probe_output(f"[JOB] BKLOG_KV\tprotocol\t{PROBE_PROTOCOL}")

        self.assertEqual(parsed["values"]["protocol"], PROBE_PROTOCOL)

    def test_ambiguous_fallback_main_config_is_reported(self):
        parsed = parsed_probe()
        parsed["values"]["main_config_source"] = "bounded_fallback_discovery"
        parsed["values"]["main_config_candidate_count"] = "2"

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source=None,
            include_source_sample=False,
            config_map_main=None,
            sidecar_required=False,
        )

        warning_codes = {item["code"] for item in probes["main_config_mounted"]["warnings"]}
        self.assertIn("multiple_main_config_candidates", warning_codes)

    def test_bounded_scan_does_not_misreport_target_data_id_as_not_rendered(self):
        parsed = parsed_probe()
        parsed["streams"].pop("child_config.0")
        parsed["values"].update(
            {
                "target_data_id": "1001",
                "child_config_scanned_count": "1000",
                "child_config_scan_limit": "1000",
                "child_config_scan_truncated": "true",
                "child_config_match_count": "0",
                "child_config_match_limit_exceeded": "false",
            }
        )

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source=None,
            include_source_sample=False,
            config_map_main=None,
            sidecar_required=False,
        )

        config_probe = probes["main_config_mounted"]
        self.assertEqual(config_probe["code"], "child_config_scan_truncated")
        self.assertNotEqual(config_probe["code"], "data_id_child_config_not_rendered")
        self.assertTrue(config_probe["evidence"]["child_config_scan"]["scan_truncated"])

    def test_missing_authoritative_hint_reports_target_data_id_as_not_rendered(self):
        parsed = parsed_probe()
        parsed["streams"].pop("child_config.0")
        parsed["values"].update(
            {
                "target_data_id": "1001",
                "child_config_hint_count": "1",
                "child_config_hint_path_count": "0",
                "child_config_scanned_count": "0",
                "child_config_scan_limit": "1000",
                "child_config_scan_truncated": "false",
                "child_config_match_count": "0",
                "child_config_match_limit_exceeded": "false",
            }
        )

        probes = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source=None,
            include_source_sample=False,
            config_map_main=None,
            sidecar_required=False,
        )

        config_probe = probes["main_config_mounted"]
        self.assertEqual(config_probe["code"], "data_id_child_config_not_rendered")
        self.assertEqual(config_probe["evidence"]["child_config_scan"]["hint_count"], 1)
        self.assertEqual(config_probe["evidence"]["child_config_scan"]["scanned_count"], 0)
        self.assertFalse(config_probe["evidence"]["child_config_scan"]["scan_truncated"])

    def test_fallback_config_parser_does_not_mix_data_ids(self):
        config = """local:
  - dataid: 1001
    paths:
      - /data/a/*.log
  - dataid: 1002
    paths:
      - /data/b/*.log
"""

        inputs = fallback_matching_inputs(config, 1001)

        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["paths"], ["/data/a/*.log"])

    def test_registrar_matching_uses_source_inode_and_device(self):
        text = (
            'prefix {"source":"/data/app.log","offset":10,"timestamp":"2026-01-01T00:00:00Z",'
            '"FileStateOS":{"inode":7,"device":8}} suffix'
        )

        states = parse_registrar_strings(text)
        current = state_for_file(
            states,
            {"path": "/data/app.log", "normalized_path": "/data/app.log", "inode": 7, "device": 8},
        )
        historical = state_for_file(
            states,
            {"path": "/data/app.log", "normalized_path": "/data/app.log", "inode": 9, "device": 8},
        )

        self.assertEqual(current["current"]["offset"], 10)
        self.assertIsNone(historical["current"])
        self.assertEqual(len(historical["historical"]), 1)

    def test_registrar_progress_preserves_insufficient_window_state(self):
        first_file = {"size_bytes": 100, "inode": 7, "device": 8}
        second_file = {"size_bytes": 120, "inode": 7, "device": 8}
        first_match = {"current": {"offset": 50}, "historical": []}
        second_match = {"current": {"offset": 80}, "historical": []}

        result = classify_registrar_progress(
            first_file,
            second_file,
            first_match,
            second_match,
            insufficient=True,
        )

        self.assertEqual(result["status"], "insufficient_observation_window")
        self.assertEqual(result["observed_status"], "progress_advancing")

    def test_host_and_k8s_use_the_same_evidence_engine(self):
        parsed = parsed_probe()

        host = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source=None,
            include_source_sample=False,
            config_map_main=None,
            sidecar_required=False,
        )
        k8s = build_probe_evidence(
            parsed,
            bk_data_id=1001,
            source=None,
            include_source_sample=False,
            config_map_main=None,
            sidecar_required=True,
        )

        common = {
            "main_config_mounted",
            "collector_process",
            "source_path",
            "registrar",
            "progress",
        }
        self.assertEqual(
            {name: host[name] for name in common},
            {name: k8s[name] for name in common},
        )
        self.assertEqual(host["sidecar_process"]["code"], "sidecar_not_applicable")
        self.assertEqual(k8s["sidecar_process"]["code"], "sidecar_process_unavailable")
