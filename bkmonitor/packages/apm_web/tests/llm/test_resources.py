from unittest import TestCase, mock

from apm_web.llm.resources import ListSpansResource


class ListSpansResourceTestCase(TestCase):
    def test_returns_apm_api_response_directly(self):
        response = {"total": 1, "data": [{"trace_id": "trace-1", "span_id": "span-1"}]}

        with mock.patch("core.drf_resource.api.apm_api.query_span_list", return_value=response) as query_span_list:
            result = ListSpansResource().request(
                {
                    "bk_biz_id": 11,
                    "app_name": "sand_local_dev",
                    "trace_id": "trace-1",
                }
            )

        self.assertEqual(result, response)
        query_span_list.assert_called_once_with(
            {
                "bk_biz_id": 11,
                "app_name": "sand_local_dev",
                "filters": [{"key": "trace_id", "operator": "equal", "value": ["trace-1"]}],
                "limit": 10000,
            }
        )
