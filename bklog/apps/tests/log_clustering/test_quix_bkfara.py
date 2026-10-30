import copy
import json
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from apps.api.base import DataAPI
from apps.api.modules.bkfara import _BkFaraApi
from apps.exceptions import ApiRequestError
from apps.log_clustering.exceptions import QuixClusteringConfigInvalidException
from apps.log_clustering.handlers.quix.payload import build_create_task_payload
from apps.log_clustering.handlers.quix.config import get_quix_config

TASK_ID = "6f1c2c1e-0000-4000-8000-000000000001"
QUIX_CONFIG = {
    "profile": "log-clustering-es",
    "kafka_resource": {"kind": "Kafka", "namespace": "bklog", "name": "clustering_kafka"},
    "pattern_resource": {"kind": "ElasticSearch", "namespace": "bklog", "name": "pattern_es"},
}
MODEL_PARAMETERS = {"delimeter": "WyIgIl0=", "min_members": 3, "max_log_length": 1000}


def response(status=200, body=None):
    value = requests.Response()
    value.status_code = status
    value._content = json.dumps({} if body is None else body).encode()
    value.encoding = "utf-8"
    return value


@override_settings(BKFARA_API_URL="https://bkfara.example/", BKFARA_API_TOKEN="token")
class TestBkFaraApi(SimpleTestCase):
    def setUp(self):
        patcher = patch("requests.sessions.Session.request")
        self.request = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch("apps.api.base.get_request_api_headers", return_value="{}")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.api = _BkFaraApi()

    def test_registered_api_uses_standard_data_api(self):
        from apps.api import BkFaraApi

        self.assertIsInstance(BkFaraApi.create_task, DataAPI)
        self.assertEqual(self.api.create_task.default_timeout, DataAPI("GET", "", "").default_timeout)

    def test_create_accepts_200_201_202_and_preserves_inputs(self):
        params = {**build_create_task_payload(24466, QUIX_CONFIG, MODEL_PARAMETERS), "Idempotency-Key": "op-create"}
        original = copy.deepcopy(params)
        for status in (200, 201, 202):
            with self.subTest(status=status):
                self.request.return_value = response(status, {"task_id": TASK_ID, "clustering": {"input_revision": 1}})
                result = self.api.create_task(params)
                self.assertEqual(result, {"task_id": TASK_ID, "clustering": {"input_revision": 1}})
                kwargs = self.request.call_args.kwargs
                self.assertEqual(kwargs["url"], "https://bkfara.example/ct/v1/clustering/tasks")
                self.assertEqual(
                    json.loads(kwargs["data"]), build_create_task_payload(24466, QUIX_CONFIG, MODEL_PARAMETERS)
                )
                self.assertEqual(kwargs["params"], {})
                self.assertEqual(params, original)
                self.assertEqual(self.api.create_task.headers["Authorization"], "Bearer token")
                self.assertEqual(self.api.create_task.headers["Idempotency-Key"], "op-create")

    def test_parameter_get_has_no_path_fields_in_query(self):
        snapshot = {
            "control_version": 4,
            "config_revision": 3,
            "training": {"parameters": MODEL_PARAMETERS},
            "adoptions": [],
        }
        self.request.return_value = response(body=snapshot)
        self.assertEqual(self.api.get_task_parameters({"task_id": TASK_ID}), snapshot)
        self.assertEqual(self.request.call_args.kwargs["params"], {})
        self.assertEqual(
            self.request.call_args.kwargs["url"], f"https://bkfara.example/ct/v1/tasks/{TASK_ID}/parameters"
        )

    def test_parameter_patch_keeps_version_key_and_body_separate(self):
        params = {
            "task_id": TASK_ID,
            "Idempotency-Key": "op-model",
            "expected_control_version": 4,
            "training": {"parameters": MODEL_PARAMETERS},
        }
        original = copy.deepcopy(params)
        self.request.return_value = response(202, {"control_version": 5})
        self.assertEqual(self.api.update_task_parameters(params), {"control_version": 5})
        kwargs = self.request.call_args.kwargs
        self.assertEqual(kwargs["method"], "PATCH")
        self.assertEqual(
            json.loads(kwargs["data"]), {"expected_control_version": 4, "training": {"parameters": MODEL_PARAMETERS}}
        )
        self.assertEqual(params, original)

    def test_business_stop_and_restart_use_declared_paths(self):
        self.request.return_value = response(body={"state": "STOPPED"})
        boundary = {"0": 10}
        completion = {"input_boundary": boundary, "storage_complete": True, "binding_removed": True}
        self.api.stop_clustering({"task_id": TASK_ID, "boundary": boundary, "completion": completion})
        self.assertEqual(
            json.loads(self.request.call_args.kwargs["data"]), {"boundary": boundary, "completion": completion}
        )
        self.api.restart_clustering({"task_id": TASK_ID, "expected_control_version": 2, "Idempotency-Key": "op-reopen"})
        self.assertTrue(self.request.call_args.kwargs["url"].endswith(f"/{TASK_ID}/restart"))
        self.assertEqual(json.loads(self.request.call_args.kwargs["data"]), {"expected_control_version": 2})

    def test_http_errors_preserve_status_and_business_code(self):
        for status, code, unknown in [
            (409, "CONTROL_VERSION_CONFLICT", False),
            (422, "TASK_PARAMETERS_INVALID", False),
            (503, "RUNTIME_UNAVAILABLE", True),
        ]:
            with self.subTest(status=status):
                self.request.return_value = response(status, {"code": code})
                with self.assertRaises(ApiRequestError) as ctx:
                    self.api.update_task_parameters({"task_id": TASK_ID, "Idempotency-Key": "op-model"})
                self.assertEqual(ctx.exception.errors, {"status_code": status, "code": code, "result_unknown": unknown})

    def test_timeout_has_no_automatic_retry_and_inputs_can_be_reused(self):
        params = {"profile": "p", "index_id": "24466", "Idempotency-Key": "op-create"}
        original = copy.deepcopy(params)
        self.request.side_effect = requests.exceptions.ReadTimeout("timeout")
        with self.assertRaises(ApiRequestError) as ctx:
            self.api.create_task(params)
        self.assertTrue(ctx.exception.errors["result_unknown"])
        self.assertEqual(self.request.call_count, 1)
        self.assertEqual(params, original)
        self.request.side_effect = None
        self.request.return_value = response(201, {"task_id": TASK_ID})
        self.api.create_task(params)
        self.assertEqual(self.api.create_task.headers["Idempotency-Key"], "op-create")
        self.assertEqual(params, original)

    def test_tls_error_is_not_an_unknown_write_result(self):
        self.request.side_effect = requests.exceptions.SSLError("bad certificate")
        with self.assertRaises(ApiRequestError) as ctx:
            self.api.create_task({})
        self.assertFalse(ctx.exception.errors["result_unknown"])

    def test_success_with_invalid_json_is_unknown_for_write(self):
        value = response(201)
        value._content = b"not json"
        self.request.return_value = value
        with self.assertRaises(ApiRequestError) as ctx:
            self.api.create_task({})
        self.assertTrue(ctx.exception.errors["result_unknown"])

    @override_settings(BKFARA_API_TOKEN="")
    def test_missing_config_fails_before_request(self):
        with self.assertRaises(ApiRequestError):
            self.api.create_task({})
        self.request.assert_not_called()

    def test_standard_data_api_still_requires_200_and_keeps_url_keys(self):
        api = DataAPI("POST", "https://example.test/{task_id}", "test", url_keys=["task_id"], no_query_params=True)
        self.request.return_value = response(201, {"result": True, "data": {}})
        with self.assertRaises(ApiRequestError):
            api({"task_id": "task-1"}, request_cookies=False)
        self.assertEqual(json.loads(self.request.call_args.kwargs["data"]), {"task_id": "task-1"})


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
