# -*- coding: utf-8 -*-

from django.test import SimpleTestCase, override_settings

from apps.grafana.data_source import ESBodyAdapter
from apps.grafana.handlers.query import GrafanaQueryHandler
from apps.log_search.handlers.search.aggs_handlers import AggsHandlers
from apps.log_search.utils import adapt_date_histogram_params, normalize_date_histogram_interval


class TestES8Compat(SimpleTestCase):
    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es8")
    def test_normalize_date_histogram_interval(self):
        self.assertEqual(normalize_date_histogram_interval("1m"), {"fixed_interval": "1m"})
        self.assertEqual(normalize_date_histogram_interval("1d"), {"fixed_interval": "1d"})
        self.assertEqual(normalize_date_histogram_interval("1M"), {"calendar_interval": "1M"})
        self.assertEqual(normalize_date_histogram_interval("1q"), {"calendar_interval": "1q"})
        self.assertEqual(normalize_date_histogram_interval("auto"), {"interval": "auto"})

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es7")
    def test_normalize_date_histogram_interval_es7(self):
        self.assertEqual(normalize_date_histogram_interval("1m"), {"interval": "1m"})
        self.assertEqual(normalize_date_histogram_interval("1M"), {"interval": "1M"})

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es8")
    def test_aggs_handler_uses_es8_interval_keys(self):
        self.assertEqual(AggsHandlers._get_date_histogram_interval_kwargs("1h"), {"fixed_interval": "1h"})
        self.assertEqual(AggsHandlers._get_date_histogram_interval_kwargs("1y"), {"calendar_interval": "1y"})

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es7")
    def test_aggs_handler_uses_es7_interval_key(self):
        self.assertEqual(AggsHandlers._get_date_histogram_interval_kwargs("1h"), {"interval": "1h"})

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es8")
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

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es7")
    def test_grafana_query_uses_es7_interval_key(self):
        aggregations = GrafanaQueryHandler(bk_biz_id=2)._get_aggregations(
            metric_field="bytes",
            agg_method="sum",
            dimensions=[],
            time_field="dtEventTimeStamp",
            interval=60,
        )
        date_histogram = aggregations["dtEventTimeStamp"]["date_histogram"]
        self.assertEqual(date_histogram["interval"], "1m")
        self.assertNotIn("fixed_interval", date_histogram)

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es8")
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

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es7")
    def test_adapt_date_histogram_params_to_es7(self):
        adapted = adapt_date_histogram_params({"field": "dtEventTimeStamp", "fixed_interval": "1d"})
        self.assertEqual(adapted["interval"], "1d")
        self.assertNotIn("fixed_interval", adapted)

    @override_settings(ES_DATE_HISTOGRAM_PARAM_VERSION="es7")
    def test_es_body_adapter_normalizes_to_es7_interval(self):
        body = {
            "aggs": {
                "group_by_histogram": {
                    "date_histogram": {"field": "dtEventTimeStamp", "fixed_interval": "1d"},
                }
            }
        }

        adapted = ESBodyAdapter(body=body).adapt()

        histogram = adapted["aggs"]["group_by_histogram"]["date_histogram"]
        self.assertEqual(histogram["interval"], "1d")
        self.assertNotIn("fixed_interval", histogram)
