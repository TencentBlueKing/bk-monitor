import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest.mock import patch

import requests
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.api.modules.bkfara import _BkFaraApi
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.models import LogIndexSet, Space
from scripts.start_v3_quix_prediction import main, start_prediction


@override_settings(BKFARA_API_URL="https://runtime.example", APP_CODE="test-log")
class TestStartV3QuixPrediction(TestCase):
    @classmethod
    def setUpTestData(cls):
        Space.objects.create(space_uid="bkcc__2", bk_biz_id=2, bk_tenant_id="example")
        LogIndexSet.objects.create(index_set_id=42, space_uid="bkcc__2", collector_config_id=10)
        cls.legacy = ClusteringConfig.objects.create(
            index_set_id=42,
            collector_config_id=10,
            new_cls_index_set_id=101,
            bk_biz_id=2,
            model_output_rt="2_original_model_output",
            min_members=2,
            max_dist_list="0.5",
            predefined_varibles="",
            delimeter="",
            max_log_length=1000,
            clustering_fields="log",
        )

    def setUp(self):
        client = patch("apps.api.BkFaraApi", _BkFaraApi())
        client.start()
        self.addCleanup(client.stop)
        transport = patch("requests.sessions.Session.request", autospec=True)
        self.http = transport.start()
        self.addCleanup(transport.stop)
        self.receipt = {
            "status": "ADOPTED",
            "tenant_id": "example",
            "index_id": "42",
            "v3_source_scope": self.legacy.model_output_rt,
            "task_id": "b5f384dd-5419-4a54-8aff-fc93846b2869",
            "generation": 1,
            "model_ref": {"revision": 8},
            "kafka_cluster_id": 99,
        }

    @staticmethod
    def response(status, body):
        result = requests.Response()
        result.status_code = status
        result._content = json.dumps(body).encode()
        return result

    def test_one_authenticated_post_per_run_and_no_local_writes(self):
        self.http.side_effect = [
            self.response(202, {"status": "WAITING_FOR_SYNC", "reason": "V3_PARAMETERS_NOT_IMPORTED"}),
            self.response(200, self.receipt),
        ]
        with CaptureQueriesContext(connection) as queries:
            with redirect_stdout(StringIO()) as waiting:
                self.assertEqual(main(["--index-id", "42"]), 75)
            self.assertEqual(self.http.call_count, 1)
            self.assertEqual(json.loads(waiting.getvalue())["reason"], "V3_PARAMETERS_NOT_IMPORTED")
            with redirect_stdout(StringIO()) as accepted:
                self.assertEqual(main(["--index-id", "42"]), 0)
            self.assertEqual(json.loads(accepted.getvalue()), self.receipt)
        self.assertEqual(self.http.call_count, 2)
        for call in self.http.call_args_list:
            self.assertEqual(call.kwargs["method"], "POST")
            self.assertEqual(call.kwargs["url"], "https://runtime.example/ct/v1/clustering/tasks")
            self.assertEqual(
                json.loads(call.kwargs["data"]),
                {"index_id": "42", "v3_source_scope": self.legacy.model_output_rt, "expected_tenant_id": "example"},
            )
            headers = call.args[0].headers
            self.assertEqual(headers["Idempotency-Key"], "bklog-v3-predict-42")
            self.assertEqual(json.loads(headers["X-Bkapi-Authorization"])["bk_app_code"], "test-log")
        self.assertTrue(all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries))

    def test_missing_ambiguous_or_incomplete_original_is_not_submitted(self):
        LogIndexSet.objects.create(index_set_id=101, space_uid="bkcc__2")
        for index in (0, 101):
            with self.subTest(index=index), self.assertRaises(ValueError):
                start_prediction(index)
        for changes in ({"access_finished": False}, {"model_output_rt": ""}, {"collector_config_id": 11}):
            with self.subTest(changes=changes):
                original = {name: getattr(self.legacy, name) for name in changes}
                ClusteringConfig.objects.filter(pk=self.legacy.pk).update(**changes)
                with self.assertRaises(ValueError):
                    start_prediction(42)
                ClusteringConfig.objects.filter(pk=self.legacy.pk).update(**original)
        another = ClusteringConfig.objects.get(pk=self.legacy.pk)
        another.pk = None
        another.save()
        with self.assertRaises(ValueError):
            start_prediction(42)
        self.http.assert_not_called()

    @override_settings(ENABLE_MULTI_TENANT_MODE=True)
    def test_missing_space_does_not_start_a_different_tenants_worker(self):
        for space_uid in ("", "bkcc__missing"):
            with self.subTest(space_uid=space_uid):
                LogIndexSet.objects.filter(index_set_id=42).update(space_uid=space_uid)
                with self.assertRaises(ValueError):
                    start_prediction(42)
        self.http.assert_not_called()

    def test_wrong_receipt_is_not_reported_as_accepted(self):
        for changes in ({"tenant_id": "other"}, {"index_id": "99"}, {"v3_source_scope": "other"}, {"status": "READY"}):
            with self.subTest(changes=changes):
                self.http.return_value = self.response(200, {**self.receipt, **changes})
                with self.assertRaises(ValueError):
                    start_prediction(42)

    def test_api_conflict_exits_without_another_request(self):
        self.http.return_value = self.response(409, {"code": "V3_ADOPTION_CONFLICT"})
        with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
            self.assertEqual(main(["--index-id", "42"]), 1)
        self.http.assert_called_once()
