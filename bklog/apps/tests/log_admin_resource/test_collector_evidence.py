from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.collector_evidence import (
    _collector_config_evidence,
    _evidence_status,
    _platform_result_to_probe,
    get_collector_control_plane_snapshot,
    get_collector_host_snapshot,
)
from apps.log_admin_resource.handlers.platform_source import PlatformSourceError
from apps.log_admin_resource.registry import AdminResourceRegistry


@override_settings(ENVIRONMENT="bkte")
class CollectorControlPlaneSnapshotTest(SimpleTestCase):
    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    def test_snapshot_combines_database_and_three_independent_nodeman_probes(self, mock_detail, mock_platform):
        mock_detail.return_value = {
            "collector": {"collector_config_id": 10},
            "chain": {"subscription_id": 20},
            "raw": {
                "params": {
                    "description": "token=collector-secret https://collector-user:collector-pass@example.com/path"
                }
            },
            "warnings": [],
        }
        mock_platform.side_effect = [
            {"result": [{"id": 20}], "warnings": []},
            {"result": [{"subscription_id": 20, "instances": 2}], "warnings": []},
            {"result": [{"subscription_id": 20, "instances": []}], "warnings": []},
        ]

        result = get_collector_control_plane_snapshot({"collector_config_id": 10})

        self.assertEqual(result["source_env"], "bkte")
        self.assertEqual(result["problem_env"], "bkte")
        self.assertEqual(result["evidence_status"], "complete")
        self.assertEqual(result["effective_config"]["probe_status"], "success")
        self.assertEqual(result["database"]["probe_status"], "success")
        self.assertEqual(result["subscription_summary"]["probe_status"], "success")
        self.assertEqual(result["subscription_statistic"]["probe_status"], "success")
        self.assertEqual(result["subscription_instances"]["probe_status"], "success")
        self.assertNotIn("collector-secret", str(result))
        self.assertNotIn("collector-user:collector-pass", str(result))
        self.assertEqual(mock_platform.call_count, 3)
        operations = [call.args[0]["operation"] for call in mock_platform.call_args_list]
        self.assertEqual(
            operations,
            ["get_subscription_summary", "fetch_subscription_statistic", "get_subscription_instance_status"],
        )

    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    def test_missing_subscription_is_explicit_and_does_not_call_nodeman(self, mock_detail, mock_platform):
        mock_detail.return_value = {"collector": {"collector_config_id": 10}, "chain": {"subscription_id": None}}

        result = get_collector_control_plane_snapshot({"collector_config_id": 10})

        self.assertEqual(result["subscription_summary"]["probe_status"], "skipped")
        self.assertEqual(result["consistency_warnings"][0]["code"], "MISSING_SUBSCRIPTION_ID")
        mock_platform.assert_not_called()

    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    def test_database_failure_keeps_stable_probe_envelope(self, mock_detail, mock_platform):
        mock_detail.side_effect = RuntimeError("database unavailable")

        result = get_collector_control_plane_snapshot({"collector_config_id": 10})

        self.assertEqual(result["database"]["probe_status"], "failed")
        self.assertEqual(result["subscription_instances"]["probe_status"], "skipped")
        mock_platform.assert_not_called()

    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    def test_one_nodeman_failure_does_not_hide_sibling_evidence(self, mock_detail, mock_platform):
        mock_detail.return_value = {"collector": {"collector_config_id": 10}, "chain": {"subscription_id": 20}}
        mock_platform.side_effect = [
            {"result": [{"id": 20}], "warnings": []},
            PlatformSourceError("unavailable", code="PROVIDER_UNAVAILABLE"),
            {"result": [{"subscription_id": 20, "instances": []}], "warnings": []},
        ]

        result = get_collector_control_plane_snapshot({"collector_config_id": 10})

        self.assertEqual(result["subscription_summary"]["probe_status"], "success")
        self.assertEqual(result["subscription_statistic"]["probe_status"], "failed")
        self.assertEqual(result["subscription_instances"]["probe_status"], "success")

    def test_collector_id_validation_rejects_bool_non_integer_and_zero(self):
        for value, message in (
            (True, "must be an integer"),
            ("invalid", "must be an integer"),
            (0, "must be positive"),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValidationError, message):
                get_collector_control_plane_snapshot({"collector_config_id": value})

    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    def test_effective_snapshot_exposes_missing_conflict_and_environment_evidence(self, mock_detail, mock_platform):
        mock_detail.return_value = {
            "collector": {"collector_config_id": 10, "bk_biz_id": 2, "updated_at": "2026-08-30T00:00:00Z"},
            "chain": {"subscription_id": None, "bk_data_id": None, "table_id": None, "primary_index_set_id": None},
            "raw": {"params": {"paths": ["/var/log/app.log"]}, "target_nodes": [{"bk_inst_id": 1}]},
            "warnings": [{"code": "storage_conflict", "message": "storage relation differs"}],
        }

        result = get_collector_control_plane_snapshot({"collector_config_id": 10, "problem_env": "bkte-problem"})

        snapshot = result["effective_config"]["data"]["value"]
        self.assertEqual(snapshot["collection"]["params"]["paths"], ["/var/log/app.log"])
        self.assertEqual(snapshot["evidence"]["problem_env"], "bkte-problem")
        self.assertEqual(snapshot["evidence"]["source_env"], "bkte")
        self.assertEqual(snapshot["missing"], ["bk_data_id", "result_table_id", "subscription_id", "index_set_id"])
        self.assertEqual(snapshot["conflicts"][0]["code"], "storage_conflict")
        mock_platform.assert_not_called()

    def test_truncated_platform_result_emits_probe_warning(self):
        result = _platform_result_to_probe(
            {
                "result": [1],
                "warnings": [{"code": "RESPONSE_TRUNCATED", "message": "bounded response"}],
            }
        )

        self.assertEqual(result["probe_status"], "success")
        self.assertEqual(result["warnings"][0]["code"], "RESPONSE_TRUNCATED")


@override_settings(ENVIRONMENT="bkte")
class CollectorHostSnapshotTest(SimpleTestCase):
    def test_host_query_requires_nonempty_ip_and_nonnegative_cloud_id(self):
        for params, message in (
            ({}, "ip or bk_host_id with bk_biz_id is required"),
            ({"ip": "   "}, "ip or bk_host_id with bk_biz_id is required"),
            ({"ip": "127.0.0.1", "bk_cloud_id": True}, "bk_cloud_id must be an integer"),
            ({"ip": "127.0.0.1", "bk_cloud_id": "invalid"}, "bk_cloud_id must be an integer"),
            ({"ip": "127.0.0.1", "bk_cloud_id": -1}, "bk_cloud_id must not be negative"),
        ):
            with self.subTest(params=params), self.assertRaisesRegex(ValidationError, message):
                get_collector_host_snapshot(params)

    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    def test_ambiguous_cmdb_host_stops_before_collector_lookup(self, mock_platform, mock_host_handler):
        mock_platform.return_value = {
            "result": {"resolution_status": "ambiguous", "candidate_count": 2, "host": None},
            "warnings": [],
        }

        result = get_collector_host_snapshot({"ip": "127.0.0.1"})

        self.assertEqual(result["cmdb"]["probe_status"], "success")
        self.assertEqual(result["collector_runtime"]["probe_status"], "skipped")
        mock_host_handler.assert_not_called()

    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    def test_resolved_host_drives_existing_readonly_collector_handler(self, mock_platform, mock_host_handler):
        mock_platform.return_value = {
            "result": {
                "resolution_status": "resolved",
                "host": {"bk_host_id": 101, "bk_biz_id": 2, "bk_cloud_id": 0},
            },
            "warnings": [],
        }
        instance = MagicMock()
        instance.list_collectors_by_host.return_value = [
            {
                "collector_config_id": 10,
                "status": "SUCCESS",
                "index_set_id": 20,
                "description": "authorization: Bearer runtime-secret",
            }
        ]
        mock_host_handler.return_value = instance

        result = get_collector_host_snapshot({"ip": "127.0.0.1", "bk_cloud_id": 0})

        instance.list_collectors_by_host.assert_called_once_with({"bk_host_id": 101, "bk_biz_id": 2, "bk_cloud_id": 0})
        self.assertEqual(result["collector_runtime"]["probe_status"], "success")
        self.assertEqual(result["collector_runtime"]["data"]["value"][0]["collector_config_id"], 10)
        self.assertNotIn("runtime-secret", str(result))

    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    def test_incomplete_cmdb_context_stops_before_collector_lookup(self, mock_platform, mock_host_handler):
        mock_platform.return_value = {
            "result": {"resolution_status": "resolved", "host": {"bk_host_id": 101}},
            "warnings": [],
        }

        result = get_collector_host_snapshot({"ip": "127.0.0.1"})

        self.assertEqual(result["collector_runtime"]["probe_status"], "skipped")
        self.assertEqual(result["consistency_warnings"][0]["code"], "HOST_CONTEXT_INCOMPLETE")
        mock_host_handler.assert_not_called()

    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    def test_empty_collector_runtime_is_success_with_consistency_warning(self, mock_platform, mock_host_handler):
        mock_platform.return_value = {
            "result": {"resolution_status": "resolved", "host": {"bk_host_id": 101, "bk_biz_id": 2}},
            "warnings": [],
        }
        mock_host_handler.return_value.list_collectors_by_host.return_value = []

        result = get_collector_host_snapshot({"ip": "127.0.0.1"})

        self.assertEqual(result["collector_runtime"]["probe_status"], "success")
        self.assertEqual(result["consistency_warnings"][0]["code"], "NO_ACTIVE_COLLECTOR")

    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    def test_collector_provider_failure_keeps_cmdb_evidence(self, mock_platform, mock_host_handler):
        mock_platform.return_value = {
            "result": {
                "resolution_status": "resolved",
                "host": {"bk_host_id": 101, "bk_biz_id": 2, "bk_cloud_id": 0},
            },
            "warnings": [],
        }
        mock_host_handler.return_value.list_collectors_by_host.side_effect = RuntimeError("nodeman failed")

        result = get_collector_host_snapshot({"ip": "127.0.0.1"})

        self.assertEqual(result["cmdb"]["probe_status"], "success")
        self.assertEqual(result["collector_runtime"]["probe_status"], "failed")

    @patch("apps.log_admin_resource.handlers.collector_evidence._platform_probe")
    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    def test_direct_host_identity_skips_cmdb_and_collects_subscription_evidence(
        self, mock_host_handler, mock_detail, mock_platform_probe
    ):
        mock_host_handler.return_value.list_collectors_by_host.return_value = [{"collector_config_id": 10}]
        mock_detail.return_value = {
            "collector": {"collector_config_id": 10, "bk_biz_id": 2},
            "chain": {"subscription_id": 20},
            "raw": {},
            "warnings": [],
        }
        mock_platform_probe.return_value = {
            "probe_status": "success",
            "exists": True,
            "empty": False,
            "observed_at": "2026-08-30T00:00:00Z",
            "duration_ms": 1,
            "data": [],
            "error": None,
            "warnings": [],
        }

        result = get_collector_host_snapshot({"bk_host_id": 101, "bk_biz_id": 2})

        self.assertEqual(result["cmdb"]["probe_status"], "skipped")
        mock_host_handler.return_value.list_collectors_by_host.assert_called_once_with(
            {"bk_host_id": 101, "bk_biz_id": 2}
        )
        operations = [call.args[1] for call in mock_platform_probe.call_args_list]
        self.assertEqual(
            operations,
            [
                "search_host_plugin_status",
                "get_subscription_summary",
                "fetch_subscription_statistic",
                "get_subscription_instance_status",
            ],
        )

    def test_host_identity_rejects_partial_or_mixed_forms(self):
        for params, message in (
            ({"bk_host_id": 1}, "bk_biz_id must be an integer"),
            ({"bk_biz_id": 2}, "bk_host_id must be an integer"),
            ({"bk_host_id": 1, "bk_biz_id": 2, "ip": "127.0.0.1"}, "not both"),
        ):
            with self.subTest(params=params), self.assertRaisesRegex(ValidationError, message):
                get_collector_host_snapshot(params)

    @patch("apps.log_admin_resource.handlers.collector_evidence._platform_probe")
    @patch("apps.log_admin_resource.handlers.collector_evidence.HostCollectorHandler")
    def test_direct_host_accepts_explicit_cloud_id(self, mock_host_handler, mock_platform_probe):
        mock_host_handler.return_value.list_collectors_by_host.return_value = []
        mock_platform_probe.return_value = {
            "probe_status": "success",
            "exists": True,
            "empty": True,
            "observed_at": "2026-08-30T00:00:00Z",
            "duration_ms": 1,
            "data": [],
            "error": None,
            "warnings": [],
        }

        get_collector_host_snapshot({"bk_host_id": 101, "bk_biz_id": 2, "bk_cloud_id": 3})

        mock_host_handler.return_value.list_collectors_by_host.assert_called_once_with(
            {"bk_host_id": 101, "bk_biz_id": 2, "bk_cloud_id": 3}
        )

    @patch("apps.log_admin_resource.handlers.collector_evidence.query_platform_source")
    def test_cmdb_provider_failure_stops_host_dependent_probes(self, mock_platform):
        mock_platform.side_effect = PlatformSourceError("unavailable", code="PROVIDER_UNAVAILABLE")

        result = get_collector_host_snapshot({"ip": "127.0.0.1"})

        self.assertEqual(result["cmdb"]["probe_status"], "failed")
        self.assertEqual(result["collector_runtime"]["probe_status"], "skipped")
        self.assertEqual(result["evidence_status"], "unavailable")

    @patch("apps.log_admin_resource.handlers.collector_evidence.get_collector_detail")
    def test_collector_config_evidence_skips_malformed_rows_and_missing_subscription(self, mock_detail):
        mock_detail.return_value = {"collector": {"collector_config_id": 10}, "chain": {}, "raw": {}}

        configs, subscription_ids, warnings = _collector_config_evidence(["malformed", {}, {"collector_config_id": 10}])

        self.assertEqual(len(configs), 1)
        self.assertEqual(subscription_ids, [])
        self.assertEqual(warnings, [])

    def test_invalid_problem_environment_and_unavailable_evidence_status(self):
        with self.assertRaisesRegex(ValidationError, "problem_env must be a non-empty string"):
            get_collector_host_snapshot({"bk_host_id": 1, "bk_biz_id": 2, "problem_env": " "})
        self.assertEqual(
            _evidence_status(
                {
                    "failed": {"probe_status": "failed"},
                    "skipped": {"probe_status": "skipped", "error": {"code": "DEPENDENCY_UNAVAILABLE"}},
                }
            ),
            "unavailable",
        )


@override_settings(
    RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
)
class CollectorEvidenceRegistryTest(SimpleTestCase):
    def test_registry_exposes_both_collector_evidence_handlers(self):
        result = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="resource-reader")

        self.assertIn("bklog.collector.control_plane.snapshot", result["functions"])
        self.assertIn("bklog.collector.host_snapshot", result["functions"])
