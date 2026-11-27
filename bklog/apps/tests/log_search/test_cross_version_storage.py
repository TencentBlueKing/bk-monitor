import copy
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.log_esquery.esquery.esquery import EsQuery
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import Scenario


@override_settings(DEAL_RETENTION_TIME=False)
class TestCrossVersionStorage(SimpleTestCase):
    def test_history_cluster_dispatch_adapts_aggs_for_each_connection(self):
        aggs = {
            "hist": {"date_histogram": {"field": "dtEventTimeStamp", "interval": "5m"}},
            "group": {"terms": {"field": "host", "order": {"_term": "asc"}}},
        }
        original = copy.deepcopy(aggs)
        for scenario, client_name in ((Scenario.LOG, "QueryClientLog"), (Scenario.ES, "QueryClientEs")):
            module = import_module(f"apps.log_esquery.esquery.client.{client_name}")
            client_class = getattr(module, client_name)
            connection_method = "_connect_info_by_storage_cluster_id" if scenario == Scenario.LOG else "_connect_info"
            for versions in (("9.4.3", "5.6.16", "6.8.0"), ("5.6.16", "8.19.19")):
                with self.subTest(scenario=scenario, versions=versions):
                    cluster_versions = dict(enumerate(versions, start=10))
                    clients = {version: MagicMock() for version in versions}
                    for client in clients.values():
                        client.search.return_value = {
                            "took": 1,
                            "hits": {"total": 0, "hits": []},
                            "aggregations": {"hist": {"buckets": [{"key": 0, "doc_count": 1}]}},
                        }
                    handler = SearchHandler.__new__(SearchHandler)
                    params = {
                        "index_set_id": 123,
                        "indices": "2_bklog.same_logs" if scenario == Scenario.LOG else "same_logs_*",
                        "scenario_id": scenario,
                        "storage_cluster_id": 10,
                        "start_time": "2020-03-21 07:00:00",
                        "end_time": "2020-03-22 23:59:59",
                        "_filter": [],
                        "query_string": "*",
                        "sort_list": [],
                        "start": 0,
                        "aggs": aggs,
                        "highlight": None,
                        "use_time_range": True,
                        "time_zone": "Asia/Shanghai",
                        "time_range": "customized",
                        "time_field": "dtEventTimeStamp",
                        "time_field_type": "date",
                        "time_field_unit": "millisecond",
                        "scroll": None,
                        "collapse": None,
                        "include_nested_fields": False,
                        "track_total_hits": False,
                    }
                    for key, value in params.items():
                        setattr(handler, key, value)
                    records = [
                        SimpleNamespace(storage_cluster_id=cluster_id)
                        for cluster_id in cluster_versions
                        if cluster_id != 10
                    ]
                    with (
                        patch(
                            "apps.log_search.handlers.search.search_handlers_esquery.StorageClusterRecord.objects.filter"
                        ) as history,
                        patch.object(handler, "fetch_esquery_method", return_value=lambda data: EsQuery(data).search()),
                        patch.object(
                            client_class,
                            connection_method,
                            side_effect=lambda storage_cluster_id: (
                                "localhost",
                                9200,
                                "u",
                                "p",
                                cluster_versions[storage_cluster_id],
                                "http",
                            ),
                        ) as connect,
                        patch.object(module, "es_socket_ping"),
                        patch.object(module, "get_es_client", side_effect=lambda **kwargs: clients[kwargs["version"]]),
                    ):
                        history.return_value.exclude.return_value = records
                        result = handler._multi_search(once_size=10)
                    self.assertEqual(
                        {call.kwargs["storage_cluster_id"] for call in connect.call_args_list}, set(cluster_versions)
                    )
                    for version, client in clients.items():
                        client.search.assert_called_once()
                        sent = client.search.call_args.kwargs["body"]["aggs"]
                        interval_key = "fixed_interval" if version.startswith(("8.", "9.")) else "interval"
                        order_key = "_term" if version.startswith("5.") else "_key"
                        self.assertEqual(
                            sent["hist"]["date_histogram"], {"field": "dtEventTimeStamp", interval_key: "5m"}
                        )
                        self.assertEqual(sent["group"]["terms"]["order"], {order_key: "asc"})
                    self.assertEqual(
                        result["aggregations"]["hist"]["buckets"], [{"key": 0, "doc_count": len(versions)}]
                    )
                    self.assertEqual(aggs, original)
