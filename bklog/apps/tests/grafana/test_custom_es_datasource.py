import copy
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

import bk_dataview.grafana  # noqa: F401
from apps.grafana.data_source import (
    BkDataCustomESDataSource,
    ESCustomESDataSource,
    LogCustomESDataSource,
)
from apps.log_search.models import Scenario


class TestESBodyAdapterAndCustomDataSource(TestCase):
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
            patch("apps.grafana.data_source.QueryClientBkData.get_es_version", return_value=None),
        ):
            mock_model.objects.filter.return_value.first.return_value = fake_bkdata_index_set

            ds_bkdata = BkDataCustomESDataSource(index_set_id=12)
            ds_bkdata.query(copy.deepcopy(body))
            sent_sql = json.loads(mock_bkdata_query.call_args.args[0]["sql"])
            self.assertEqual(sent_sql["body"]["aggs"]["hist"]["date_histogram"]["interval"], "5m")
            self.assertNotIn("fixed_interval", sent_sql["body"]["aggs"]["hist"]["date_histogram"])

    def test_bkdata_query_uses_version_adapter_and_preserves_grafana_authentication(self):
        body = {
            "aggs": {
                "hist": {"date_histogram": {"field": "ts", "fixed_interval": "1d"}},
                "group": {"terms": {"field": "host", "order": {"_key": "asc"}}},
            }
        }
        original = copy.deepcopy(body)
        index_set = MagicMock(
            index_set_id=12,
            storage_cluster_id=-1,
            scenario_id=Scenario.BKDATA,
            indexes=[{"result_table_id": "2_first"}, {"result_table_id": "2_second"}],
        )
        for version in ("5.6.16", "8.19.19", "9.4.3", None):
            with (
                self.subTest(version=version),
                patch("apps.grafana.data_source.LogIndexSet") as model,
                patch("apps.grafana.data_source.update_bkdata_auth_info") as update_auth,
                patch("apps.grafana.data_source.BkDataQueryApi.query", return_value={"list": {}}) as query,
                patch("apps.grafana.data_source.QueryClientBkData.get_es_version", return_value=version) as get_version,
            ):
                model.objects.filter.return_value.first.return_value = index_set
                datasource = BkDataCustomESDataSource(index_set_id=12)
                datasource.query(body)
                get_version.assert_called_once_with("2_first_*,2_second_*")
                sql = json.loads(query.call_args.args[0]["sql"])
                self.assertEqual(sql["index"], "2_first_*,2_second_*")
                histogram_key = "fixed_interval" if version in ("8.19.19", "9.4.3") else "interval"
                order_key = "_key" if version in ("8.19.19", "9.4.3") else "_term"
                self.assertEqual(sql["body"]["aggs"]["hist"]["date_histogram"], {"field": "ts", histogram_key: "1d"})
                self.assertEqual(sql["body"]["aggs"]["group"]["terms"]["order"], {order_key: "asc"})
                self.assertEqual(body, original)
                self.assertTrue(query.call_args.args[0]["no_request"])
                self.assertFalse(query.call_args.kwargs["request_cookies"])
                update_auth.assert_called_once()

                query.reset_mock()
                get_version.reset_mock()
                datasource.mapping()
                get_version.assert_not_called()
                self.assertEqual(
                    json.loads(query.call_args.args[0]["sql"]), {"index": "2_first_*,2_second_*", "mapping": True}
                )
