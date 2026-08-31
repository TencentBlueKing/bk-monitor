from unittest import TestCase, mock

from apm_web.llm.resources import ListSpansResource


class ListSpansResourceTestCase(TestCase):
    def test_adapts_standard_span(self):
        trace_id = "a" * 32
        response = {
            "total": 1,
            "data": [
                {
                    "trace_id": trace_id,
                    "span_id": "b" * 16,
                    "parent_span_id": "",
                    "span_name": "chat demo-model",
                    "start_time": 1,
                    "end_time": 2,
                    "elapsed_time": 1,
                    "status": {"code": 1, "message": ""},
                    "resource": {"service.name": "demo"},
                    "attributes": {
                        "gen_ai.operation.name": "chat",
                        "gen_ai.request.model": "demo-model",
                        "vendor.debug": "drop-me",
                    },
                    "events": [],
                }
            ],
        }

        with mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response):
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": trace_id,
                }
            )

        self.assertEqual(result["trace_id"], trace_id)
        self.assertEqual(result["total"], 1)
        attributes = result["spans"][0]["attributes"]
        self.assertEqual(attributes["gen_ai.operation.name"], "chat")
        self.assertEqual(attributes["gen_ai.request.model"], "demo-model")
        self.assertNotIn("vendor.debug", attributes)

    def test_adapts_apm_api_response(self):
        response = {"total": 1, "data": [{"trace_id": "trace-1", "span_id": "span-1"}]}
        converted_span = {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "attributes": {"gen_ai.operation.name": "chat"},
        }

        with (
            mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response) as query_span_list,
            mock.patch(
                "apm_web.llm.resources.adapt_spans",
                return_value=[converted_span],
            ) as adapt_spans,
        ):
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": "trace-1",
                }
            )

        self.assertEqual(
            result,
            {"trace_id": "trace-1", "total": 1, "spans": [converted_span]},
        )
        adapt_spans.assert_called_once_with(response["data"])
        query_span_list.assert_called_once_with(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "filters": [{"key": "trace_id", "operator": "equal", "value": ["trace-1"]}],
                "limit": 10000,
                "exclude_field": ["bk_app_code"],
            }
        )
