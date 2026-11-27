import copy
from importlib import import_module
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_esquery.utils.es_client import adapt_es_query_body, needs_es_query_body_adaptation


class TestQueryBodyCompat(SimpleTestCase):
    def test_nested_aggs_and_preserve_explicit_interval_semantics(self):
        body = {
            "query": {"term": {"interval": "5m"}},
            "aggregations": {
                "group": {
                    "terms": {"field": "host", "order": [{"_term": "asc"}, {"_count": "desc"}]},
                    "aggs": {
                        "legacy": {"date_histogram": {"field": "ts", "interval": "1d"}},
                        "fixed": {"date_histogram": {"field": "ts", "fixed_interval": "1d"}},
                        "calendar": {"date_histogram": {"field": "ts", "calendar_interval": "1M"}},
                    },
                }
            },
        }
        original = copy.deepcopy(body)
        for version in ("7.2.0", "8.19.19", "9.4.3"):
            with self.subTest(version=version):
                adapted = adapt_es_query_body(body, version)
                group = adapted["aggregations"]["group"]
                self.assertEqual(group["terms"]["order"], [{"_key": "asc"}, {"_count": "desc"}])
                self.assertEqual(group["aggs"]["legacy"]["date_histogram"], {"field": "ts", "calendar_interval": "1d"})
                self.assertEqual(group["aggs"]["fixed"], body["aggregations"]["group"]["aggs"]["fixed"])
                self.assertEqual(group["aggs"]["calendar"], body["aggregations"]["group"]["aggs"]["calendar"])
                self.assertEqual(adapted["query"], body["query"])
        self.assertEqual(body, original)

    def test_composite_date_sources_follow_version_without_changing_other_sources(self):
        sources = [
            {
                "day": {
                    "date_histogram": {
                        "field": "ts",
                        "interval": "1d",
                        "time_zone": "+08:00",
                        "format": "yyyy-MM-dd",
                        "order": "desc",
                    }
                }
            },
            {"minutes": {"date_histogram": {"field": "ts", "interval": "5m"}}},
            {"milliseconds": {"date_histogram": {"field": "ts", "interval": 60000}}},
            {"fixed": {"date_histogram": {"field": "ts", "fixed_interval": "1d"}}},
            {"calendar": {"date_histogram": {"field": "ts", "calendar_interval": "1M"}}},
            {"host": {"terms": {"field": "host", "order": "asc", "missing_bucket": True}}},
            {"bytes": {"histogram": {"field": "bytes", "interval": 100}}},
        ]
        after = {next(iter(source)): 0 for source in sources}
        after["host"] = "web-1"
        for alias in ("aggs", "aggregations"):
            body = {
                "query": {"term": {"interval": "1d"}},
                alias: {
                    "group": {
                        "filter": {"term": {"status": "ok"}},
                        "aggs": {"pages": {"composite": {"size": 100, "after": after, "sources": sources}}},
                    }
                },
            }
            original = copy.deepcopy(body)
            self.assertTrue(needs_es_query_body_adaptation(body))
            for version in (None, "6.8.0", "7.1.0", "7.2.0", "8.19.19", "9.4.3"):
                with self.subTest(alias=alias, version=version):
                    modern = version in ("7.2.0", "8.19.19", "9.4.3")
                    expected = copy.deepcopy(body)
                    expected_sources = expected[alias]["group"]["aggs"]["pages"]["composite"]["sources"]
                    intervals = (
                        (
                            ("calendar_interval", "1d"),
                            ("fixed_interval", "5m"),
                            ("fixed_interval", "60000ms"),
                            ("fixed_interval", "1d"),
                            ("calendar_interval", "1M"),
                        )
                        if modern
                        else (
                            ("interval", "1d"),
                            ("interval", "5m"),
                            ("interval", 60000),
                            ("interval", "1d"),
                            ("interval", "1M"),
                        )
                    )
                    for source, (key, interval) in zip(expected_sources, intervals):
                        histogram = next(iter(source.values()))["date_histogram"]
                        histogram.pop("interval", None)
                        histogram.pop("fixed_interval", None)
                        histogram.pop("calendar_interval", None)
                        histogram[key] = interval
                    self.assertEqual(adapt_es_query_body(body, version), expected)
                    self.assertEqual(body, original)

    def test_composite_non_date_sources_skip_adaptation(self):
        body = {
            "aggs": {
                "pages": {
                    "composite": {
                        "sources": [
                            {"host": {"terms": {"field": "host", "order": "asc"}}},
                            {"bytes": {"histogram": {"field": "bytes", "interval": 100}}},
                        ]
                    }
                }
            }
        }
        self.assertFalse(needs_es_query_body_adaptation(body))
        self.assertEqual(adapt_es_query_body(body, "9.4.3"), body)

    def test_clients_adapt_shared_body_using_each_connection_version(self):
        intervals = {
            "hist": "5m",
            "milliseconds": 60000,
            "single_millisecond": 1,
            "second": "second",
            "single_second": "1s",
        }
        body = {
            "aggs": {
                name: {"date_histogram": {"field": "ts", "interval": interval}} for name, interval in intervals.items()
            }
        }
        body["aggs"]["pages"] = {
            "composite": {"sources": [{"day": {"date_histogram": {"field": "ts", "interval": "1d"}}}]}
        }
        original = copy.deepcopy(body)
        modern_aggs = {
            "hist": {"date_histogram": {"field": "ts", "fixed_interval": "5m"}},
            "milliseconds": {"date_histogram": {"field": "ts", "fixed_interval": "60000ms"}},
            "single_millisecond": {"date_histogram": {"field": "ts", "fixed_interval": "1ms"}},
            "second": {"date_histogram": {"field": "ts", "calendar_interval": "second"}},
            "single_second": {"date_histogram": {"field": "ts", "calendar_interval": "1s"}},
            "pages": {
                "composite": {"sources": [{"day": {"date_histogram": {"field": "ts", "calendar_interval": "1d"}}}]}
            },
        }
        versions = (
            (None, False),
            ("unknown", False),
            ("5.6.16", False),
            ("6.8.0", False),
            ("7.1.0", False),
            ("7.2.0", True),
            ("7.17.13", True),
            ("8.19.19", True),
            ("9.4.3", True),
        )
        for name in ("QueryClientLog", "QueryClientEs"):
            module = import_module(f"apps.log_esquery.esquery.client.{name}")
            for version, use_modern_syntax in versions:
                with self.subTest(client=name, version=version):
                    es = MagicMock()
                    client = getattr(module, name)(storage_cluster_id=77)
                    connect_method = (
                        "_connect_info_by_storage_cluster_id" if name == "QueryClientLog" else "_connect_info"
                    )
                    with (
                        patch.object(
                            client, connect_method, return_value=("localhost", 9200, "u", "p", version, "http")
                        ),
                        patch.object(module, "es_socket_ping"),
                        patch.object(module, "get_es_client", return_value=es),
                    ):
                        client.query("2_bklog.test", body, track_total_hits=True)
                    sent = es.search.call_args.kwargs["body"]
                    self.assertEqual(sent["aggs"], modern_aggs if use_modern_syntax else original["aggs"])
                    self.assertTrue(sent["track_total_hits"])
                    self.assertEqual(body, original)

    def test_log_client_resolves_version_from_result_table_without_cluster_id(self):
        from apps.log_esquery.esquery.client import QueryClientLog as module

        for cluster_id in (None, -1):
            with self.subTest(cluster_id=cluster_id):
                client = module.QueryClientLog(storage_cluster_id=cluster_id)
                es = MagicMock()
                with (
                    patch.object(
                        client, "_connect_info", return_value=("localhost", 9200, "u", "p", "9.4.3", "http")
                    ) as connect,
                    patch.object(module, "es_socket_ping"),
                    patch.object(module, "get_es_client", return_value=es),
                ):
                    client.query("2_bklog.test_*", {"aggs": {"hist": {"date_histogram": {"interval": "1h"}}}})
                connect.assert_called_once_with(index="2_bklog.test")
                self.assertEqual(
                    es.search.call_args.kwargs["body"]["aggs"]["hist"]["date_histogram"], {"calendar_interval": "1h"}
                )

    def test_legacy_client_syntax(self):
        body = {
            "aggs": {
                "hist": {"date_histogram": {"fixed_interval": "5m"}},
                "calendar": {"date_histogram": {"calendar_interval": "1d"}},
                "group": {"terms": {"order": {"_key": "asc"}}},
            }
        }
        for version in ("5.6.16", "6.8.0", "7.1.0"):
            with self.subTest(version=version):
                adapted = adapt_es_query_body(body, version)["aggs"]
                self.assertEqual(adapted["hist"]["date_histogram"], {"interval": "5m"})
                self.assertEqual(adapted["calendar"]["date_histogram"], {"interval": "1d"})
                order_key = "_term" if version.startswith("5.") else "_key"
                self.assertEqual(adapted["group"]["terms"]["order"], {order_key: "asc"})
