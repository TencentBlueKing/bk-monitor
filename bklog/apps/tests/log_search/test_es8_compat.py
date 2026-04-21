# -*- coding: utf-8 -*-

from django.test import SimpleTestCase

from apps.grafana.data_source import ESBodyAdapter
from apps.grafana.handlers.query import GrafanaQueryHandler
from apps.log_search.handlers.search.aggs_handlers import AggsHandlers
from apps.log_search.utils import normalize_date_histogram_interval


class TestES8Compat(SimpleTestCase):
    def test_normalize_date_histogram_interval(self):
        self.assertEqual(normalize_date_histogram_interval("1m"), {"fixed_interval": "1m"})
        self.assertEqual(normalize_date_histogram_interval("1d"), {"fixed_interval": "1d"})
        self.assertEqual(normalize_date_histogram_interval("1M"), {"calendar_interval": "1M"})
        self.assertEqual(normalize_date_histogram_interval("1q"), {"calendar_interval": "1q"})
        self.assertEqual(normalize_date_histogram_interval("auto"), {"interval": "auto"})

    def test_aggs_handler_uses_es8_interval_keys(self):
        self.assertEqual(AggsHandlers._get_date_histogram_interval_kwargs("1h"), {"fixed_interval": "1h"})
        self.assertEqual(AggsHandlers._get_date_histogram_interval_kwargs("1y"), {"calendar_interval": "1y"})

    def test_grafana_query_uses_es8_interval_keys(self):
        aggregations = GrafanaQueryHandler(bk_biz_id=2)._get_aggregations(
            metric_field="bytes",
            agg_method="sum",
            dimensions=[],
            time_field="dtEventTimeStamp",
            interval=60,
        )
        date_histogram = aggregations["dtEventTimeStamp"]["date_histogram"]
        self.assertEqual(date_histogram["fixed_interval"], "1m")
        self.assertNotIn("interval", date_histogram)

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

        adapted = ESBodyAdapter(body=body).adapt()

        histogram = adapted["aggs"]["group_by_histogram"]["date_histogram"]
        self.assertEqual(histogram["fixed_interval"], "1d")
        self.assertNotIn("interval", histogram)
        self.assertEqual(adapted["aggs"]["by_month"]["date_histogram"]["calendar_interval"], "1M")
