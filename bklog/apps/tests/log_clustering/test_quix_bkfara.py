from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.log_clustering.exceptions import (
    BkFaraApiException,
    BkFaraConflictException,
    BkFaraNotConfiguredException,
    BkFaraResultUnknownException,
    QuixClusteringConfigInvalidException,
)
from apps.log_clustering.handlers.quix.bkfara import (
    BkFaraClient,
    build_clustering_payload,
    build_create_task_payload,
)
from apps.log_clustering.handlers.quix.config import DEFAULT_KAFKA_NAME_TEMPLATES, get_quix_config

TASK_ID = "6f1c2c1e-0000-4000-8000-000000000001"
RESOURCE_PROFILE_REF = {"uri": "urn:quix-profile", "digest": "sha256:abc", "digest_scheme": "sha256-jcs-rfc8785-v1"}
QUIX_CONFIG = {
    "task_template": {"base_model_ref": {"uri": "https://artifacts/base.json", "digest": "sha256:def"}},
    "resource_profile_ref": RESOURCE_PROFILE_REF,
    "kafka": {
        "cluster_ref": "quix-e2e",
        "partitions": 2,
        "retention_ms": 604800000,
        "recovery_window_ms": 86400000,
        "source_namespace": "bklog-prod",
        "mapping_revision": "log-v1",
    },
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "clustering_kafka"},
    "pattern_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "pattern_es"},
}


def _response(status_code=200, body=None):
    response = Mock(status_code=status_code, ok=200 <= status_code < 300)
    response.content = b"{}" if body is not None else b""
    response.json.return_value = body
    return response


@override_settings(
    BKFARA_API_URL="https://bkfara.example/", BKFARA_API_TOKEN="token", BKFARA_CA_CERT_PATH="/etc/ca.pem"
)
class TestBkFaraClient(SimpleTestCase):
    def setUp(self):
        patcher = patch.object(requests.Session, "request")
        self.mock_request = patcher.start()
        self.addCleanup(patcher.stop)
        self.client = BkFaraClient()

    def test_create_task_sends_auth_idempotency_key_and_ca(self):
        self.mock_request.return_value = _response(body={"task_id": TASK_ID})

        result = self.client.create_task({"runtime_key": {}}, idempotency_key="op-create_task")

        self.assertEqual(result, {"task_id": TASK_ID})
        args, kwargs = self.mock_request.call_args
        self.assertEqual(args, ("POST", "https://bkfara.example/ct/v1/tasks"))
        self.assertEqual(kwargs["headers"], {"Idempotency-Key": "op-create_task"})
        self.assertEqual(kwargs["verify"], "/etc/ca.pem")
        self.assertEqual(self.client.session.headers["Authorization"], "Bearer token")

    def test_two_phase_stop_payloads(self):
        self.mock_request.return_value = _response(body={"state": "DRAINING"})
        boundary = {"0": 10, "1": 10}
        completion = {"input_boundary": boundary, "storage_complete": True, "binding_removed": True}

        self.client.stop_clustering(TASK_ID, boundary)
        self.client.stop_clustering(TASK_ID, boundary, completion)

        first, second = self.mock_request.call_args_list
        self.assertEqual(first.kwargs["json"], {"boundary": boundary})
        self.assertEqual(second.kwargs["json"], {"boundary": boundary, "completion": completion})
        self.assertEqual(second.args[1], f"https://bkfara.example/internal/ct/v1/clustering/tasks/{TASK_ID}/stop")
        self.assertEqual(second.kwargs["headers"], {})

    def test_restart_uses_expected_control_version(self):
        self.mock_request.return_value = _response(body={})

        self.client.restart_clustering(TASK_ID, expected_control_version=2, idempotency_key="op-restart")

        kwargs = self.mock_request.call_args.kwargs
        self.assertEqual(kwargs["json"], {"expected_control_version": 2})
        self.assertEqual(kwargs["headers"], {"Idempotency-Key": "op-restart"})

    def test_timeout_and_gateway_error_are_result_unknown(self):
        self.mock_request.side_effect = requests.exceptions.ReadTimeout("read timeout")
        with self.assertRaises(BkFaraResultUnknownException):
            self.client.configure_clustering(TASK_ID, {}, idempotency_key="op-configure")

        self.mock_request.side_effect = None
        self.mock_request.return_value = _response(504, {"message": "gateway timeout"})
        with self.assertRaises(BkFaraResultUnknownException):
            self.client.configure_clustering(TASK_ID, {}, idempotency_key="op-configure")

    def test_conflict_keeps_business_code(self):
        self.mock_request.return_value = _response(409, {"code": "CONTROL_VERSION_CONFLICT", "message": "stale"})

        with self.assertRaises(BkFaraConflictException) as ctx:
            self.client.restart_clustering(TASK_ID, expected_control_version=1, idempotency_key="op-restart")

        self.assertEqual(ctx.exception.data, {"status_code": 409, "code": "CONTROL_VERSION_CONFLICT"})

    def test_business_error_and_ssl_error_are_api_errors(self):
        self.mock_request.return_value = _response(400, {"code": "CLUSTER_QUARANTINE_PENDING", "message": "pending"})
        with self.assertRaises(BkFaraApiException) as ctx:
            self.client.stop_clustering(TASK_ID, {"0": 1})
        self.assertNotIsInstance(ctx.exception, BkFaraConflictException)
        self.assertEqual(ctx.exception.data["code"], "CLUSTER_QUARANTINE_PENDING")

        self.mock_request.side_effect = requests.exceptions.SSLError("certificate verify failed")
        with self.assertRaises(BkFaraApiException):
            self.client.get_task(TASK_ID)

    @override_settings(BKFARA_API_TOKEN="")
    def test_missing_config_raises(self):
        with self.assertRaises(BkFaraNotConfiguredException):
            BkFaraClient()

    @override_settings(BKFARA_CA_CERT_PATH="")
    def test_empty_ca_uses_system_ca(self):
        self.assertIs(BkFaraClient().verify, True)


class TestBkFaraPayload(SimpleTestCase):
    def test_create_task_payload_keeps_template_refs(self):
        payload = build_create_task_payload(24466, QUIX_CONFIG)

        self.assertEqual(payload["runtime_key"], {"domain": "log-clustering", "business_key": "24466"})
        self.assertEqual(payload["base_model_ref"], QUIX_CONFIG["task_template"]["base_model_ref"])

    def test_clustering_payload_binds_names_to_task(self):
        config = {**QUIX_CONFIG, "kafka": {**QUIX_CONFIG["kafka"], **DEFAULT_KAFKA_NAME_TEMPLATES}}

        payload = build_clustering_payload(TASK_ID, 1, config)

        self.assertEqual(payload["expected_control_version"], 1)
        self.assertEqual(payload["kafka"]["input_topic"], f"lc-{TASK_ID}-in")
        self.assertEqual(payload["kafka"]["result_group"], f"lc-{TASK_ID}-result")
        self.assertEqual(payload["resource_profile_ref"], RESOURCE_PROFILE_REF)
        self.assertEqual(config["kafka"]["input_topic"], "lc-{task_id}-in")


class TestQuixConfig(SimpleTestCase):
    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle")
    def test_fills_default_name_templates(self, mock_toggle):
        mock_toggle.return_value = Mock(feature_config={"bkbase_quix": QUIX_CONFIG})

        config = get_quix_config()

        self.assertEqual(config["kafka"]["output_topic"], "lc-{task_id}-out")
        self.assertEqual(config["kafka"]["cluster_ref"], "quix-e2e")

    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle")
    def test_missing_keys_are_reported(self, mock_toggle):
        broken = {**QUIX_CONFIG, "resource_profile_ref": None, "pattern_resource": {"kind": "ElasticSearch"}}
        mock_toggle.return_value = Mock(feature_config={"bkbase_quix": broken})

        with self.assertRaises(QuixClusteringConfigInvalidException) as ctx:
            get_quix_config()

        self.assertIn("resource_profile_ref", ctx.exception.message)
        self.assertIn("pattern_resource.name", ctx.exception.message)

    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle", return_value=None)
    def test_missing_toggle_is_invalid(self, mock_toggle):
        with self.assertRaises(QuixClusteringConfigInvalidException):
            get_quix_config()

    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle")
    def test_recovery_window_cannot_exceed_retention(self, mock_toggle):
        kafka = {**QUIX_CONFIG["kafka"], "recovery_window_ms": QUIX_CONFIG["kafka"]["retention_ms"] + 1}
        mock_toggle.return_value = Mock(feature_config={"bkbase_quix": {**QUIX_CONFIG, "kafka": kafka}})

        with self.assertRaises(QuixClusteringConfigInvalidException):
            get_quix_config()
