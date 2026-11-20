import copy
import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

import bk_dataview.grafana  # noqa: F401
from apps.grafana.data_source import (
    BkDataCustomESDataSource,
    ESBodyAdapter,
    ESCustomESDataSource,
    LogCustomESDataSource,
)
from apps.log_search.models import Scenario


class TestESBodyAdapterAndCustomDataSource(TestCase):
    def setUp(self) -> None:
        cache.clear()

    def tearDown(self) -> None:
        cache.clear()

    def _build_body(self):
        return {
            "aggs": {
                "hist": {
                    "date_histogram": {
                        "field": "dtEventTimeStamp",
                        "fixed_interval": "5m",
                    },
                    "aggs": {
                        "terms_agg": {
                            "terms": {
                                "field": "status",
                                "order": {"_key": "asc"},
                            }
                        }
                    },
                },
                "cal_hist": {
                    "date_histogram": {
                        "field": "dtEventTimeStamp",
                        "calendar_interval": "1h",
                    }
                },
                "malformed_non_dict": "ignored",
            }
        }

    def test_es_body_adapter_versions(self):
        body = self._build_body()

        for ver in ("9.4.3", "8.19.19", "7.14.2"):
            adapted = ESBodyAdapter(copy.deepcopy(body), es_version=ver, legacy_fallback=False).adapt()
            self.assertEqual(adapted["aggs"]["hist"]["date_histogram"]["fixed_interval"], "5m")
            self.assertEqual(adapted["aggs"]["cal_hist"]["date_histogram"]["calendar_interval"], "1h")
            self.assertEqual(adapted["aggs"]["hist"]["aggs"]["terms_agg"]["terms"]["order"], {"_key": "asc"})

        adapted_es6 = ESBodyAdapter(copy.deepcopy(body), es_version="6.8.0", legacy_fallback=False).adapt()
        self.assertEqual(adapted_es6["aggs"]["hist"]["date_histogram"], {"field": "dtEventTimeStamp", "interval": "5m"})
        self.assertEqual(
            adapted_es6["aggs"]["cal_hist"]["date_histogram"], {"field": "dtEventTimeStamp", "interval": "1h"}
        )
        self.assertEqual(adapted_es6["aggs"]["hist"]["aggs"]["terms_agg"]["terms"]["order"], {"_key": "asc"})

        adapted_es5 = ESBodyAdapter(copy.deepcopy(body), es_version="5.6.16", legacy_fallback=False).adapt()
        self.assertEqual(adapted_es5["aggs"]["hist"]["date_histogram"], {"field": "dtEventTimeStamp", "interval": "5m"})
        self.assertEqual(
            adapted_es5["aggs"]["cal_hist"]["date_histogram"], {"field": "dtEventTimeStamp", "interval": "1h"}
        )
        self.assertEqual(adapted_es5["aggs"]["hist"]["aggs"]["terms_agg"]["terms"]["order"], {"_term": "asc"})

        adapted_unknown_modern = ESBodyAdapter(copy.deepcopy(body), es_version=None, legacy_fallback=False).adapt()
        self.assertEqual(adapted_unknown_modern["aggs"]["hist"]["date_histogram"]["fixed_interval"], "5m")
        self.assertEqual(adapted_unknown_modern["aggs"]["cal_hist"]["date_histogram"]["calendar_interval"], "1h")
        self.assertEqual(adapted_unknown_modern["aggs"]["hist"]["aggs"]["terms_agg"]["terms"]["order"], {"_key": "asc"})

        adapted_unknown_legacy = ESBodyAdapter(copy.deepcopy(body), es_version=None, legacy_fallback=True).adapt()
        self.assertEqual(
            adapted_unknown_legacy["aggs"]["hist"]["date_histogram"], {"field": "dtEventTimeStamp", "interval": "5m"}
        )
        self.assertEqual(
            adapted_unknown_legacy["aggs"]["cal_hist"]["date_histogram"], {"field": "dtEventTimeStamp", "interval": "1h"}
        )
        self.assertEqual(adapted_unknown_legacy["aggs"]["hist"]["aggs"]["terms_agg"]["terms"]["order"], {"_term": "asc"})

    def test_custom_es_datasource_query_routing(self):
        mock_query_client = MagicMock()
        mock_query_client.query.return_value = {"hits": {"total": 1, "hits": []}}

        body = {
            "aggs": {
                "hist": {
                    "date_histogram": {"field": "dtEventTimeStamp", "fixed_interval": "5m"},
                }
            }
        }

        fake_log_index_set = MagicMock(
            index_set_id=10,
            storage_cluster_id=77,
            scenario_id=Scenario.LOG,
            indexes=[{"result_table_id": "2_bklog_test", "time_field": "dtEventTimeStamp"}],
        )
        with (
            patch("apps.grafana.data_source.LogIndexSet") as mock_model,
            patch("apps.grafana.data_source.get_cluster_es_version", return_value="9.4.3"),
            patch("apps.grafana.data_source.QueryClient") as mock_client_cls,
        ):
            mock_model.objects.filter.return_value.first.return_value = fake_log_index_set
            mock_client_cls.return_value.get_instance.return_value = mock_query_client

            ds_log = LogCustomESDataSource(index_set_id=10)
            ds_log.query(copy.deepcopy(body))
            sent_body = mock_query_client.query.call_args.kwargs["body"]
            self.assertEqual(sent_body["aggs"]["hist"]["date_histogram"]["fixed_interval"], "5m")
            self.assertNotIn("interval", sent_body["aggs"]["hist"]["date_histogram"])

        mock_query_client.reset_mock()
        fake_es_index_set = MagicMock(
            index_set_id=11,
            storage_cluster_id=78,
            scenario_id=Scenario.ES,
            indexes=[{"result_table_id": "es_idx_test", "time_field": "dtEventTimeStamp"}],
        )
        with (
            patch("apps.grafana.data_source.LogIndexSet") as mock_model,
            patch("apps.grafana.data_source.get_cluster_es_version", return_value=None),
            patch("apps.grafana.data_source.QueryClient") as mock_client_cls,
        ):
            mock_model.objects.filter.return_value.first.return_value = fake_es_index_set
            mock_client_cls.return_value.get_instance.return_value = mock_query_client

            ds_es = ESCustomESDataSource(index_set_id=11)
            ds_es.query(copy.deepcopy(body))
            sent_body = mock_query_client.query.call_args.kwargs["body"]
            self.assertEqual(sent_body["aggs"]["hist"]["date_histogram"]["fixed_interval"], "5m")

        fake_bkdata_index_set = MagicMock(
            index_set_id=12,
            storage_cluster_id=-1,
            scenario_id=Scenario.BKDATA,
            indexes=[{"result_table_id": "2_bklog_bkdata", "time_field": "dtEventTimeStamp"}],
        )
        with (
            patch("apps.grafana.data_source.LogIndexSet") as mock_model,
            patch("apps.grafana.data_source.update_bkdata_auth_info"),
            patch("apps.grafana.data_source.BkDataQueryApi.query", return_value={"list": []}) as mock_bkdata_query,
        ):
            mock_model.objects.filter.return_value.first.return_value = fake_bkdata_index_set

            ds_bkdata = BkDataCustomESDataSource(index_set_id=12)
            ds_bkdata.query(copy.deepcopy(body))
            sent_sql = json.loads(mock_bkdata_query.call_args.args[0]["sql"])
            self.assertEqual(sent_sql["body"]["aggs"]["hist"]["date_histogram"]["interval"], "5m")
            self.assertNotIn("fixed_interval", sent_sql["body"]["aggs"]["hist"]["date_histogram"])
