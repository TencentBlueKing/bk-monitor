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

from unittest.mock import patch

from django.test import SimpleTestCase
from packaging.version import Version

from apps.grafana.data_source import ESBodyAdapter
from apps.grafana.handlers.query import GrafanaQueryHandler
from apps.log_search.utils import (
    adapt_date_histogram_params,
    get_es_date_histogram_param_version,
    normalize_date_histogram_interval,
    parse_es_date_histogram_param_version,
)


class TestES8Compat(SimpleTestCase):
    def test_parse_es_date_histogram_param_version(self):
        self.assertEqual(parse_es_date_histogram_param_version("7.0.0"), Version("7.0.0"))
        self.assertEqual(parse_es_date_histogram_param_version("7.17.9"), Version("7.17.9"))
        self.assertEqual(parse_es_date_histogram_param_version("8.0.0"), Version("8.0.0"))
        self.assertIsNone(parse_es_date_histogram_param_version("invalid"))

    @patch("apps.log_esquery.esquery.client.QueryClientEs.QueryClientEs._connect_info")
    def test_get_es_date_histogram_param_version(self, mock_connect_info):
        mock_connect_info.return_value = ("127.0.0.1", 9200, "user", "password", "8.11.1", "http")
        self.assertEqual(get_es_date_histogram_param_version(2), Version("8.11.1"))
        self.assertIsNone(get_es_date_histogram_param_version(None))

    def test_normalize_date_histogram_interval(self):
        es_version = Version("8.0.0")
        self.assertEqual(normalize_date_histogram_interval("1m", es_version=es_version), {"fixed_interval": "1m"})
        self.assertEqual(normalize_date_histogram_interval("1d", es_version=es_version), {"fixed_interval": "1d"})
        self.assertEqual(normalize_date_histogram_interval("1w", es_version=es_version), {"calendar_interval": "1w"})
        self.assertEqual(normalize_date_histogram_interval("1M", es_version=es_version), {"calendar_interval": "1M"})
        self.assertEqual(normalize_date_histogram_interval("1q", es_version=es_version), {"calendar_interval": "1q"})
        self.assertEqual(normalize_date_histogram_interval("auto", es_version=es_version), {"interval": "auto"})

    def test_normalize_date_histogram_interval_es7(self):
        es_version = Version("7.17.9")
        self.assertEqual(normalize_date_histogram_interval("1m", es_version=es_version), {"interval": "1m"})
        self.assertEqual(normalize_date_histogram_interval("1M", es_version=es_version), {"interval": "1M"})

    def test_aggs_handler_uses_es8_interval_keys(self):
        es_version = Version("8.0.0")
        self.assertEqual(normalize_date_histogram_interval("1h", es_version=es_version), {"fixed_interval": "1h"})
        self.assertEqual(normalize_date_histogram_interval("1y", es_version=es_version), {"calendar_interval": "1y"})

    @patch("apps.grafana.handlers.query.get_es_date_histogram_param_version", return_value=Version("8.11.1"))
    def test_grafana_query_uses_es8_interval_keys(self, _mock_version):
        aggregations = GrafanaQueryHandler(bk_biz_id=2)._get_aggregations(
            metric_field="bytes",
            agg_method="sum",
            dimensions=[],
            time_field="dtEventTimeStamp",
            interval=60,
            storage_cluster_id=2,
        )
        date_histogram = aggregations["dtEventTimeStamp"]["date_histogram"]
        self.assertEqual(date_histogram["fixed_interval"], "1m")
        self.assertNotIn("interval", date_histogram)

    @patch("apps.grafana.handlers.query.get_es_date_histogram_param_version", return_value=Version("7.17.9"))
    def test_grafana_query_uses_es7_interval_key(self, _mock_version):
        aggregations = GrafanaQueryHandler(bk_biz_id=2)._get_aggregations(
            metric_field="bytes",
            agg_method="sum",
            dimensions=[],
            time_field="dtEventTimeStamp",
            interval=60,
            storage_cluster_id=2,
        )
        date_histogram = aggregations["dtEventTimeStamp"]["date_histogram"]
        self.assertEqual(date_histogram["interval"], "1m")
        self.assertNotIn("fixed_interval", date_histogram)

    def test_es_body_adapter_normalizes_legacy_interval(self):
        body = {
            "aggs": {
                "group_by_histogram": {
                    "date_histogram": {"field": "dtEventTimeStamp", "interval": "1d"},
                },
                "by_month": {
                    "date_histogram": {"field": "dtEventTimeStamp", "calendar_interval": "1M"},
                },
            }
        }

        adapted = ESBodyAdapter(body=body, es_version=Version("8.0.0")).adapt()

        histogram = adapted["aggs"]["group_by_histogram"]["date_histogram"]
        self.assertEqual(histogram["fixed_interval"], "1d")
        self.assertNotIn("interval", histogram)
        self.assertEqual(adapted["aggs"]["by_month"]["date_histogram"]["calendar_interval"], "1M")

    def test_adapt_date_histogram_params_to_es7(self):
        adapted = adapt_date_histogram_params(
            {"field": "dtEventTimeStamp", "fixed_interval": "1d"}, es_version=Version("7.17.9")
        )
        self.assertEqual(adapted["interval"], "1d")
        self.assertNotIn("fixed_interval", adapted)

    def test_es_body_adapter_normalizes_to_es7_interval(self):
        body = {
            "aggs": {
                "group_by_histogram": {
                    "date_histogram": {"field": "dtEventTimeStamp", "fixed_interval": "1d"},
                }
            }
        }

        adapted = ESBodyAdapter(body=body, es_version=Version("7.17.9")).adapt()

        histogram = adapted["aggs"]["group_by_histogram"]["date_histogram"]
        self.assertEqual(histogram["interval"], "1d")
        self.assertNotIn("fixed_interval", histogram)
