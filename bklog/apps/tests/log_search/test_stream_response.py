"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json

from django.test import RequestFactory, SimpleTestCase
from rest_framework.response import Response

from apps.log_search.decorators import search_history_record
from apps.log_search.utils import (
    LOG_STREAM_CONTENT_TYPE,
    create_log_ndjson_stream_response,
    is_log_stream_request,
)


class LogStreamResponseTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _load_events_from_response(self, response):
        content = ""
        for chunk in response.streaming_content:
            content += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        return response, [json.loads(line) for line in content.splitlines()]

    def _load_stream_events(self, result):
        return self._load_events_from_response(create_log_ndjson_stream_response(result))

    def test_create_log_ndjson_stream_response_pairs_list_and_origin_log_list(self):
        response, events = self._load_stream_events(
            {
                "total": 2,
                "took": 10,
                "fields": [{"field_name": "log"}],
                "list": [{"log": "rendered-1"}, {"log": "rendered-2"}],
                "origin_log_list": [{"log": "origin-1"}, {"log": "origin-2"}],
            }
        )

        self.assertEqual(response["Content-Type"], LOG_STREAM_CONTENT_TYPE)
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertEqual(events[0]["event"], "meta")
        self.assertNotIn("list", events[0])
        self.assertNotIn("origin_log_list", events[0])
        self.assertEqual(events[1]["event"], "row")
        self.assertEqual(events[1]["index"], 0)
        self.assertEqual(events[1]["data"], {"log": "rendered-1"})
        self.assertEqual(events[1]["origin_data"], {"log": "origin-1"})
        self.assertEqual(events[2]["origin_data"], {"log": "origin-2"})
        self.assertEqual(events[3], {"event": "done"})

    def test_create_log_ndjson_stream_response_keeps_large_log_in_one_row_event(self):
        _, events = self._load_stream_events(
            {
                "list": [{"log": "中文\nline2" + "x" * 1024}],
                "origin_log_list": [{"log": "origin\nline2"}],
            }
        )

        self.assertEqual([event["event"] for event in events], ["meta", "row", "done"])
        self.assertEqual(events[1]["data"]["log"], "中文\nline2" + "x" * 1024)

    def test_create_log_ndjson_stream_response_falls_back_when_origin_log_list_missing(self):
        _, events = self._load_stream_events({"list": [{"log": "rendered"}]})

        self.assertEqual(events[0]["warnings"], ["origin_log_list_missing"])
        self.assertEqual(events[1]["data"], {"log": "rendered"})
        self.assertEqual(events[1]["origin_data"], {"log": "rendered"})

    def test_create_log_ndjson_stream_response_falls_back_when_origin_log_list_length_mismatch(self):
        _, events = self._load_stream_events(
            {
                "list": [{"log": "rendered-1"}, {"log": "rendered-2"}],
                "origin_log_list": [{"log": "origin-1"}],
            }
        )

        self.assertEqual(events[0]["warnings"], ["origin_log_list_length_mismatch"])
        self.assertEqual(events[1]["origin_data"], {"log": "origin-1"})
        self.assertEqual(events[2]["origin_data"], {"log": "rendered-2"})

    def test_is_log_stream_request_checks_query_param_and_accept_header(self):
        self.assertTrue(is_log_stream_request(self.factory.post("/search/?stream=true")))
        self.assertTrue(is_log_stream_request(self.factory.post("/search/", HTTP_ACCEPT="application/x-ndjson")))
        self.assertFalse(is_log_stream_request(self.factory.post("/search/")))

    def test_search_history_record_converts_stream_request_after_took_fields_are_added(self):
        @search_history_record
        def fake_view(request):
            return Response(
                {
                    "took": 1,
                    "list": [{"log": "rendered"}],
                    "origin_log_list": [{"log": "origin"}],
                }
            )

        response, events = self._load_events_from_response(fake_view(self.factory.post("/search/?stream=true")))

        self.assertEqual(response["Content-Type"], LOG_STREAM_CONTENT_TYPE)
        self.assertEqual(events[0]["event"], "meta")
        self.assertEqual(events[0]["raw_took"], 1)
        self.assertIn("took", events[0])
        self.assertEqual(events[1]["origin_data"], {"log": "origin"})
