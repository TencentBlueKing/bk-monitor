import copy
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.log_esquery.esquery.client.QueryClientBkData import QueryClientBkData
from apps.log_esquery.esquery.esquery import EsQuery
from apps.log_search.models import Scenario

CLIENT_MODULE = "apps.log_esquery.esquery.client.QueryClientBkData"


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TestBkdataQueryBodyCompat(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.meta = self.enterContext(patch(f"{CLIENT_MODULE}.BkDataMetaApi.result_tables.storages"))
        self.meta.return_value = {"es": {"storage_cluster": {"cluster_name": "first-es"}}}
        self.route = self.enterContext(patch(f"{CLIENT_MODULE}.BkDataStorekitApi.storekit_es_route"))
        self.route.return_value = json.dumps({"version": {"number": "9.4.3"}})
        self.query = self.enterContext(patch(f"{CLIENT_MODULE}.BkDataQueryApi.query"))
        self.query.return_value = {"list": {"hits": {"hits": [], "total": 0}}}
        self.tenant = self.enterContext(patch(f"{CLIENT_MODULE}.get_request_tenant_id", return_value="tenant-a"))

    @staticmethod
    def body():
        return {
            "aggregations": {
                "group": {
                    "terms": {"field": "host", "order": [{"_term": "asc"}, {"_count": "desc"}]},
                    "aggs": {
                        "legacy": {"date_histogram": {"field": "ts", "interval": 60000}},
                        "fixed": {"date_histogram": {"field": "ts", "fixed_interval": "1d"}},
                        "calendar": {"date_histogram": {"field": "ts", "calendar_interval": "1M"}},
                    },
                }
            }
        }

    def sent_sql(self):
        return json.loads(self.query.call_args.args[0]["sql"])

    def test_first_result_table_version_is_cached_across_date_patterns(self):
        body = self.body()
        original = copy.deepcopy(body)
        for index in ("2_first_20261126*,2_second_20261126*", "2_first_202611*,2_second_*"):
            QueryClientBkData().query(index, body)
            sql = self.sent_sql()
            self.assertEqual(sql["index"], index)
            group = sql["body"]["aggregations"]["group"]
            self.assertEqual(group["terms"]["order"], [{"_key": "asc"}, {"_count": "desc"}])
            self.assertEqual(group["aggs"]["legacy"]["date_histogram"], {"field": "ts", "fixed_interval": "60000ms"})
            self.assertEqual(group["aggs"]["fixed"]["date_histogram"], {"field": "ts", "fixed_interval": "1d"})
            self.assertEqual(body, original)
        self.meta.assert_called_once_with({"result_table_id": "2_first"}, bk_tenant_id="tenant-a", timeout=3)
        self.route.assert_called_once_with({"cluster_name": "first-es", "uri": "/"}, bk_tenant_id="tenant-a", timeout=3)

    def test_result_table_normalization_preserves_bare_numeric_suffixes(self):
        cases = (
            ("2_first,2_other", "2_first"),
            (" 2_first_*,2_other_*", "2_first"),
            ("2_first_2026*", "2_first"),
            ("2_first_202611*", "2_first"),
            ("2_first_20261126*", "2_first"),
            ("2_first_2026112600*", "2_first"),
            ("2_first_202611", "2_first_202611"),
            ("2_first_123456_*", "2_first_123456"),
        )
        for index, table_id in cases:
            with self.subTest(index=index):
                cache.clear()
                self.meta.reset_mock()
                QueryClientBkData().query(index, self.body())
                self.assertEqual(self.meta.call_args.args[0], {"result_table_id": table_id})
        self.meta.reset_mock()
        QueryClientBkData().query("2_first*,2_other_*", self.body())
        self.meta.assert_not_called()

    def test_plain_search_and_unrelated_aggregations_do_not_probe_version(self):
        for body in (
            {"query": {"term": {"interval": "5m"}}},
            {"aggs": {"group": {"terms": {"field": "host", "order": {"_count": "desc"}}}}},
            {"aggs": {"avg": {"avg": {"field": "duration"}}}},
        ):
            with self.subTest(body=body):
                original = copy.deepcopy(body)
                QueryClientBkData().query("2_first_*", body, track_total_hits=True)
                self.assertEqual(self.sent_sql()["body"], {**original, "track_total_hits": True})
                self.assertEqual(body, original)
        self.meta.assert_not_called()
        self.route.assert_not_called()

    def test_version_cache_isolated_by_tenant_and_first_table(self):
        for tenant, index in (
            ("tenant-a", "2_first_*"),
            ("tenant-b", "2_first_*"),
            ("tenant-a", "2_other_*"),
            ("tenant-a", "2_first_20261126*,2_other_*"),
        ):
            self.tenant.return_value = tenant
            QueryClientBkData().query(index, self.body())
        self.assertEqual(self.meta.call_count, 3)
        self.assertEqual(self.route.call_count, 3)
        self.assertEqual(
            [call.kwargs["bk_tenant_id"] for call in self.meta.call_args_list], ["tenant-a", "tenant-b", "tenant-a"]
        )

    def test_probe_failures_preserve_query_and_are_cached(self):
        for failure in ("metadata", "route", "invalid_json", "invalid_version", "missing_es"):
            with self.subTest(failure=failure):
                cache.clear()
                self.meta.reset_mock()
                self.route.reset_mock()
                self.meta.side_effect = RuntimeError("metadata unavailable") if failure == "metadata" else None
                self.meta.return_value = (
                    {} if failure == "missing_es" else {"es": {"storage_cluster": {"cluster_name": "first-es"}}}
                )
                self.route.side_effect = TimeoutError("route timeout") if failure == "route" else None
                self.route.return_value = "invalid" if failure == "invalid_json" else {"version": {"number": "unknown"}}
                body = self.body()
                for _ in range(2):
                    result = QueryClientBkData().query("2_first_*", body)
                    self.assertEqual(result, self.query.return_value["list"])
                    self.assertEqual(self.sent_sql()["body"], body)
                self.meta.assert_called_once()
                self.assertEqual(self.route.call_count, 0 if failure in ("metadata", "missing_es") else 1)

    def test_cache_failure_does_not_break_query(self):
        with patch(
            f"{CLIENT_MODULE}.QueryClientBkData._get_cached_es_version", side_effect=RuntimeError("cache unavailable")
        ):
            body = self.body()
            QueryClientBkData().query("2_first_*", body)
            self.assertEqual(self.sent_sql()["body"], body)

    def test_old_and_new_versions_use_compatible_syntax(self):
        for version in ("5.6.16", "6.8.0", "7.1.0", "7.2.0", "8.19.19", "9.4.3"):
            with self.subTest(version=version), patch.object(QueryClientBkData, "get_es_version", return_value=version):
                QueryClientBkData().query("2_first_*", self.body())
                group = self.sent_sql()["body"]["aggregations"]["group"]
                order_key = "_term" if version == "5.6.16" else "_key"
                self.assertEqual(group["terms"]["order"], [{order_key: "asc"}, {"_count": "desc"}])
                if version in ("5.6.16", "6.8.0", "7.1.0"):
                    self.assertEqual(group["aggs"]["legacy"]["date_histogram"], {"field": "ts", "interval": 60000})
                    self.assertEqual(group["aggs"]["fixed"]["date_histogram"], {"field": "ts", "interval": "1d"})
                else:
                    self.assertEqual(
                        group["aggs"]["legacy"]["date_histogram"], {"field": "ts", "fixed_interval": "60000ms"}
                    )
                    self.assertEqual(group["aggs"]["fixed"]["date_histogram"], {"field": "ts", "fixed_interval": "1d"})

    def test_dsl_entry_adapts_query_without_changing_indices(self):
        index = "2_first_20261126*,2_second_20261126*"
        EsQuery({"scenario_id": Scenario.BKDATA, "indices": index, "body": self.body()}).dsl()
        self.assertEqual(self.sent_sql()["index"], index)
        self.assertEqual(self.sent_sql()["body"]["aggregations"]["group"]["terms"]["order"][0], {"_key": "asc"})
        self.assertEqual(self.meta.call_args.args[0], {"result_table_id": "2_first"})

    def test_query_preserves_authentication_and_track_total_hits_behavior(self):
        for track_total_hits in (False, True):
            with self.subTest(track_total_hits=track_total_hits):
                body = self.body()
                QueryClientBkData("token", "test-token").query("2_first_*", body, track_total_hits=track_total_hits)
                params = self.query.call_args.args[0]
                self.assertEqual(params["bkdata_authentication_method"], "token")
                self.assertEqual(params["bkdata_data_token"], "test-token")
                self.assertEqual("track_total_hits" in self.sent_sql()["body"], track_total_hits)
                self.assertNotIn("track_total_hits", body)
