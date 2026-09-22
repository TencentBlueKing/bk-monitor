import json
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.api.modules.bkdata_databus import _BkDataDatabusApi
from apps.exceptions import ApiResultError, ValidationError
from apps.log_admin_resource.handlers.bkdata_inspection import get_bkdata_clean_errors
from apps.log_admin_resource.handlers.inspection import MAX_SAMPLE_BYTES
from apps.log_admin_resource.registry import FUNCTIONS
from apps.tests.log_admin_resource.test_clustering_inspection import BKDATA_CONTEXT


MODULE = "apps.log_admin_resource.handlers.bkdata_inspection"
PARAMS = {"bk_biz_id": 2, "raw_data_id": 1, "result_table_id": "2_clean"}


def sample(rt="2_clean", **fields):
    return {
        "raw_data_id": 1,
        "result_table_id": rt,
        "msg_value": '{"event": "example", "password": "sample-secret"}',
        "error": "TimeFormatError: Illegal pattern character 'e'",
        "partition": 0,
        "offset": 123,
        "timestamp": 1790000000,
        **fields,
    }


class CleanErrorsTest(SimpleTestCase):
    def setUp(self):
        self.context = self.enterContext(patch(f"{MODULE}.build_bkdata_context", return_value=BKDATA_CONTEXT))
        self.api = self.enterContext(patch(f"{MODULE}.BkDataDatabusApi.get_raw_data_badmsg"))

    def test_filter_before_limit_and_use_service_identity(self):
        self.api.return_value = [sample("2_other"), sample(offset=1), sample(offset=2)]
        probe = get_bkdata_clean_errors({**PARAMS, "sample_limit": 1})["errors"]
        data = probe["data"]
        self.assertEqual(probe["probe_status"], "success")
        self.assertFalse(probe["empty"])
        self.assertEqual(data["source_sample_count"], 3)
        self.assertEqual(data["matched_sample_count"], 2)
        self.assertEqual(data["excluded_sample_count"], 1)
        self.assertEqual(data["sample_count"], 1)
        self.assertTrue(data["has_more"])
        self.assertEqual(data["assessment"], "target_errors_observed")
        self.assertEqual(data["samples"][0]["raw"]["value"]["offset"], 1)
        self.assertNotIn("sample-secret", json.dumps(data))
        self.assertNotIn("time_evidence", data)
        self.context.assert_called_once_with(2)
        self.api.assert_called_once()
        kwargs = self.api.call_args.kwargs
        self.assertEqual(kwargs["bk_tenant_id"], "system")
        self.assertFalse(kwargs["request_cookies"])
        self.assertEqual(
            kwargs["params"], {k: v for k, v in {**BKDATA_CONTEXT, "raw_data_id": 1}.items() if k != "bk_tenant_id"}
        )

    def test_empty_or_other_rt_does_not_claim_healthy(self):
        for rows in ([], [sample("2_other") for _ in range(10)], [sample("2_clean_suffix")]):
            with self.subTest(rows=len(rows)):
                self.api.return_value = rows
                probe = get_bkdata_clean_errors(PARAMS)["errors"]
                self.assertTrue(probe["empty"])
                self.assertEqual(probe["data"]["source_sample_count"], len(rows))
                self.assertEqual(probe["data"]["matched_sample_count"], 0)
                self.assertEqual(probe["data"]["samples"], [])
                self.assertEqual(probe["data"]["assessment"], "no_target_sample")
                self.assertEqual(probe["data"]["coverage"], "unknown")
                self.assertIn("UPSTREAM_SAMPLE_SCOPE_LIMITED", [w["code"] for w in probe["warnings"]])

    def test_upstream_failure_is_not_empty_success(self):
        self.api.side_effect = ApiResultError("query failed", code=1500002)
        probe = get_bkdata_clean_errors(PARAMS)["errors"]
        self.assertEqual(probe["probe_status"], "failed")
        self.assertIsNone(probe["data"])

    def test_invalid_upstream_shapes_fail(self):
        for rows in (None, {}, [None], [sample(raw_data_id=9)], [{"raw_data_id": 1}]):
            with self.subTest(rows=rows):
                self.api.return_value = rows
                probe = get_bkdata_clean_errors(PARAMS)["errors"]
                self.assertEqual(probe["probe_status"], "failed")
                self.assertEqual(probe["error"]["code"], "UPSTREAM_INVALID_RESPONSE")

    def test_identity_failure_does_not_call_upstream(self):
        self.context.side_effect = ValidationError("business tenant mismatch")
        self.assertEqual(get_bkdata_clean_errors(PARAMS)["errors"]["probe_status"], "failed")
        self.api.assert_not_called()

    def test_invalid_params_do_not_call_upstream(self):
        for updates in (
            {"result_table_id": " "},
            {"result_table_id": None},
            {"raw_data_id": 0},
            {"bk_biz_id": 0},
            {"sample_limit": 21},
            {"bk_username": "spoof"},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                get_bkdata_clean_errors({**PARAMS, **updates})
        self.api.assert_not_called()

    def test_oversized_sample_is_bounded_and_redacted(self):
        self.api.return_value = [sample(msg_value="password=hidden " + "x" * (MAX_SAMPLE_BYTES * 2))]
        probe = get_bkdata_clean_errors(PARAMS)["errors"]
        raw = probe["data"]["samples"][0]["raw"]
        self.assertTrue(raw["truncated"])
        self.assertLessEqual(raw["returned_size_bytes"], MAX_SAMPLE_BYTES)
        self.assertNotIn("hidden", json.dumps(raw))
        self.assertIn("SAMPLE_TRUNCATED", [w["code"] for w in probe["warnings"]])

    def test_api_route_is_read_only_uncached_for_both_gateways(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled), override_settings(USE_APIGW=enabled):
                api = _BkDataDatabusApi().get_raw_data_badmsg
                self.assertEqual(api.method, "GET")
                self.assertTrue(api.url.endswith("rawdatas/{raw_data_id}/badmsg/"))
                self.assertEqual(api.cache_time, 0)
                self.assertEqual(api.url_keys, ["raw_data_id"])


@override_settings(MIDDLEWARE=("apps.tests.log_admin_resource.test_resource_call.ReadOnlyAdminApiGatewayMiddleware",))
class CleanErrorsDispatchTest(TestCase):
    @patch(f"{MODULE}.build_bkdata_context", return_value=BKDATA_CONTEXT)
    @patch(f"{MODULE}.BkDataDatabusApi.get_raw_data_badmsg", return_value=[sample()])
    def test_read_only_dispatch_and_schema_validation(self, api, context):
        operation = FUNCTIONS["bklog.bkdata.clean.errors"]
        self.assertEqual(operation["safety_level"], "inspect")
        self.assertEqual(operation["data_classification"], "sensitive_logs")
        response = self.client.post(
            "/api/v1/admin/resource/call/",
            data=json.dumps({"func_name": "bklog.bkdata.clean.errors", "params": PARAMS}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["result"], body)
        self.assertEqual(body["data"]["result"]["errors"]["data"]["sample_count"], 1)
        api.reset_mock()
        for params in (
            {**PARAMS, "bk_username": "spoof"},
            {**PARAMS, "sample_limit": 21},
            {**PARAMS, "unexpected": True},
            {**PARAMS, "raw_data_id": True},
        ):
            response = self.client.post(
                "/api/v1/admin/resource/call/",
                data=json.dumps({"func_name": "bklog.bkdata.clean.errors", "params": params}),
                content_type="application/json",
            )
            self.assertFalse(response.json()["result"])
        api.assert_not_called()
