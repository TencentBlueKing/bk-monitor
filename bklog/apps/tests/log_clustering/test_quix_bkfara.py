import copy
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
    build_create_task_payload,
)
from apps.log_clustering.handlers.quix.config import get_quix_config

TASK_ID = "6f1c2c1e-0000-4000-8000-000000000001"
QUIX_CONFIG = {
    "profile": "log-clustering-es",
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "clustering_kafka"},
    "pattern_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "pattern_es"},
}
MODEL_PARAMETERS = {"delimeter": "WyIgIl0=", "min_members": 3, "max_log_length": 1000}


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

        result = self.client.create_task(
            build_create_task_payload(24466, QUIX_CONFIG), idempotency_key="op-create_task"
        )

        self.assertEqual(result, {"task_id": TASK_ID})
        args, kwargs = self.mock_request.call_args
        self.assertEqual(args, ("POST", "https://bkfara.example/ct/v1/clustering/tasks"))
        self.assertEqual(kwargs["headers"], {"Idempotency-Key": "op-create_task"})
        self.assertEqual(kwargs["verify"], "/etc/ca.pem")
        self.assertEqual(self.client.session.headers["Authorization"], "Bearer token")

    def test_get_parameters_preserves_configuration_and_adoption_snapshot(self):
        snapshot = {
            "task_id": TASK_ID,
            "control_version": 4,
            "config_revision": 3,
            "training": {"parameters": MODEL_PARAMETERS},
            "adoptions": [{"binding__config_revision": 2}],
        }
        self.mock_request.return_value = _response(body=snapshot)
        self.assertEqual(self.client.get_task_parameters(TASK_ID), snapshot)
        args, kwargs = self.mock_request.call_args
        self.assertEqual(args, ("GET", f"https://bkfara.example/ct/v1/tasks/{TASK_ID}/parameters"))
        self.assertEqual(kwargs["headers"], {})
        self.assertIsNone(kwargs["json"])

    def test_update_parameters_uses_patch_control_version_and_idempotency_key(self):
        self.mock_request.return_value = _response(202, {"control_version": 5})
        parameters = copy.deepcopy(MODEL_PARAMETERS)
        result = self.client.update_task_parameters(TASK_ID, 4, parameters, "op-update-model")
        self.assertEqual(result, {"control_version": 5})
        args, kwargs = self.mock_request.call_args
        self.assertEqual(args, ("PATCH", f"https://bkfara.example/ct/v1/tasks/{TASK_ID}/parameters"))
        self.assertEqual(kwargs["headers"], {"Idempotency-Key": "op-update-model"})
        self.assertEqual(kwargs["json"], {"expected_control_version": 4, "training": {"parameters": MODEL_PARAMETERS}})
        kwargs["json"]["training"]["parameters"]["min_members"] = 10
        self.assertEqual(parameters, MODEL_PARAMETERS)

    def test_model_update_unknown_result_reuses_request_and_key(self):
        self.mock_request.side_effect = [requests.exceptions.ReadTimeout("timeout"), _response(202, {"accepted": True})]
        with self.assertRaises(BkFaraResultUnknownException):
            self.client.update_task_parameters(TASK_ID, 4, MODEL_PARAMETERS, "op-update-model")
        self.client.update_task_parameters(TASK_ID, 4, MODEL_PARAMETERS, "op-update-model")
        first, second = self.mock_request.call_args_list
        self.assertEqual(first, second)

    def test_model_update_conflict_keeps_business_code(self):
        self.mock_request.return_value = _response(409, {"code": "CONTROL_VERSION_CONFLICT"})
        with self.assertRaises(BkFaraConflictException) as ctx:
            self.client.update_task_parameters(TASK_ID, 4, MODEL_PARAMETERS, "op-update-model")
        self.assertEqual(ctx.exception.data["code"], "CONTROL_VERSION_CONFLICT")

    def test_business_stop_accepts_optional_completion(self):
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
    def test_create_uses_profile_and_string_index_id(self):
        self.assertEqual(
            build_create_task_payload(24466, QUIX_CONFIG),
            {"profile": "log-clustering-es", "index_id": "24466"},
        )

    def test_create_model_parameters_use_training_parameters_without_mutating_inputs(self):
        config, parameters = copy.deepcopy(QUIX_CONFIG), copy.deepcopy(MODEL_PARAMETERS)
        payload = build_create_task_payload(24466, config, parameters)
        self.assertEqual(
            payload, {"profile": "log-clustering-es", "index_id": "24466", "training": {"parameters": MODEL_PARAMETERS}}
        )
        payload["training"]["parameters"]["min_members"] = 10
        self.assertEqual(parameters, MODEL_PARAMETERS)
        self.assertEqual(config, QUIX_CONFIG)

    def test_explicit_empty_parameters_are_preserved(self):
        self.assertEqual(build_create_task_payload(24466, QUIX_CONFIG, {})["training"], {"parameters": {}})


class TestQuixConfig(SimpleTestCase):
    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle")
    def test_profile_does_not_require_local_task_or_kafka_templates(self, mock_toggle):
        mock_toggle.return_value = Mock(feature_config={"bkbase_quix": QUIX_CONFIG})
        self.assertEqual(get_quix_config(), QUIX_CONFIG)

    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle")
    def test_missing_keys_are_reported(self, mock_toggle):
        broken = {**QUIX_CONFIG, "profile": None, "pattern_resource": {"kind": "ElasticSearch"}}
        mock_toggle.return_value = Mock(feature_config={"bkbase_quix": broken})
        with self.assertRaises(QuixClusteringConfigInvalidException) as ctx:
            get_quix_config()
        self.assertIn("profile", ctx.exception.message)
        self.assertIn("pattern_resource.name", ctx.exception.message)

    @patch("apps.log_clustering.handlers.quix.config.FeatureToggleObject.toggle", return_value=None)
    def test_missing_toggle_is_invalid(self, mock_toggle):
        with self.assertRaises(QuixClusteringConfigInvalidException):
            get_quix_config()
