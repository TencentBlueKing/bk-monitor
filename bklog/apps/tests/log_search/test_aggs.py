# -*- coding: utf-8 -*-
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


from django.test import TestCase

from apps.log_search.handlers.search import aggs_handlers

SOURCE_HISTOGRAM_DICT = {
    "tags.result_code": {
        "labels": ["16:48", "16:49", "16:50", "16:51", "16:52", "16:53"],
        "datasets": [
            {"label": 904, "data": [{"label": "2021-06-22 11:10:00", "value": 1, "count": 0}]},
            {
                "label": 905,
                "data": [
                    {"label": "2021-06-22 11:10:00", "value": 1, "count": 1},
                    {"label": "2021-06-22 11:20:00", "value": 0, "count": 0},
                ],
            },
            {
                "label": 906,
                "data": [
                    {"label": "2021-06-22 11:10:00", "value": 0, "count": 0},
                    {"label": "2021-06-22 11:20:00", "value": 0, "count": 0},
                ],
            },
        ],
    }
}

DST_HISTOGRAM_DICT = {
    "tags.result_code": {
        "labels": ["16:48", "16:49", "16:50", "16:51", "16:52", "16:53"],
        "datasets": [
            {"label": 904, "data": [{"label": "2021-06-22 11:10:00", "value": 1, "count": 0}]},
            {
                "label": 905,
                "data": [
                    {"label": "2021-06-22 11:10:00", "value": 1, "count": 1},
                    {"label": "2021-06-22 11:20:00", "value": 0, "count": 0},
                ],
            },
        ],
    }
}


class TestAggsHandlers(TestCase):
    def setUp(self) -> None:
        self.aggs_view_adapter = aggs_handlers.AggsViewAdapter()

    def test_del_empty_histogram(self):
        print(self.aggs_view_adapter._del_empty_histogram(SOURCE_HISTOGRAM_DICT))
        self.assertEqual(self.aggs_view_adapter._del_empty_histogram(SOURCE_HISTOGRAM_DICT), DST_HISTOGRAM_DICT)


class TestAggsHandlersDateHistogram(TestCase):
    def test_get_es_version_lookup(self):
        from unittest.mock import Mock, patch

        index_set_obj = Mock(scenario_id=aggs_handlers.Scenario.LOG, storage_cluster_id=88)
        bkdata_obj = Mock(scenario_id=aggs_handlers.Scenario.BKDATA, storage_cluster_id=99)
        with (
            patch("apps.log_search.handlers.search.aggs_handlers.LogIndexSet") as mock_index_set,
            patch(
                "apps.log_search.handlers.search.aggs_handlers.get_cluster_es_version",
                return_value="9.4.3",
            ) as mock_get_ver,
        ):
            mock_index_set.objects.filter.return_value.only.return_value.first.return_value = index_set_obj
            version = aggs_handlers.AggsHandlers._get_es_version(123)
            self.assertEqual(version, "9.4.3")
            mock_get_ver.assert_called_once_with(88)

            mock_index_set.objects.filter.return_value.only.return_value.first.return_value = bkdata_obj
            self.assertIsNone(aggs_handlers.AggsHandlers._get_es_version(456))

            mock_index_set.objects.filter.return_value.only.return_value.first.return_value = None
            self.assertIsNone(aggs_handlers.AggsHandlers._get_es_version(999))

    def test_date_histogram_interval_params_by_es_version(self):
        from unittest.mock import MagicMock, patch

        cases = [
            ("9.4.3", "10m", "date", {"fixed_interval": "10m"}),
            ("9.4.3", "1m", "date", {"calendar_interval": "1m"}),
            ("8.19.19", "5m", "long", {"fixed_interval": "5m"}),
            ("8.19.19", "1d", "long", {"calendar_interval": "1d"}),
            ("6.8.0", "5m", "date", {"interval": "5m"}),
            ("6.8.0", "1d", "long", {"interval": "1d"}),
            (None, "10m", "date", {"interval": "10m"}),
        ]

        for es_version, interval, time_field_type, expected_interval_dict in cases:
            captured_query_data = {}

            def _fake_search_handler(index_set_id, query_data, only_for_agg=True):
                captured_query_data.update(query_data)
                handler = MagicMock()
                handler.time_field = "dtEventTimeStamp"
                handler.time_field_type = time_field_type
                handler.time_field_unit = "millisecond"
                handler.search.return_value = {
                    "aggs": {"group_by_histogram": {"buckets": [{"key": 1700000000000, "doc_count": 2}]}},
                    "_shards": {},
                }
                return handler

            query_data = {
                "start_time": "2026-01-01 00:00:00",
                "end_time": "2026-01-01 01:00:00",
                "interval": interval,
                "fields": [],
                "time_zone": "Asia/Shanghai",
            }
            with (
                patch.object(aggs_handlers.AggsHandlers, "_get_es_version", return_value=es_version),
                patch.object(
                    aggs_handlers.SearchHandlerEsquery,
                    "init_time_field",
                    return_value=("dtEventTimeStamp", time_field_type, "millisecond"),
                ),
                patch.object(aggs_handlers.AggsHandlers, "search_handler_class", side_effect=_fake_search_handler),
            ):
                result = aggs_handlers.AggsHandlers.date_histogram(1, query_data)

            hist = captured_query_data["aggs"]["group_by_histogram"]["date_histogram"]
            self.assertEqual(hist["field"], "dtEventTimeStamp")
            for k, v in expected_interval_dict.items():
                self.assertEqual(hist[k], v, msg=f"version={es_version}, interval={interval}, type={time_field_type}")
            if "interval" not in expected_interval_dict:
                self.assertNotIn("interval", hist)
            else:
                self.assertNotIn("fixed_interval", hist)
                self.assertNotIn("calendar_interval", hist)
            self.assertIn("aggs", result)

