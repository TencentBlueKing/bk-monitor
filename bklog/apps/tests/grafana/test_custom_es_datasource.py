import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

import bk_dataview.grafana  # noqa: F401
from apps.grafana.data_source import BkDataCustomESDataSource, ESCustomESDataSource, LogCustomESDataSource
from apps.log_search.models import Scenario


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class TestCustomESDataSource(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.index_set = SimpleNamespace(
            scenario_id=Scenario.BKDATA,
            storage_cluster_id=-1,
            indexes=[{"result_table_id": "2_first"}, {"result_table_id": "2_second"}],
        )
        model = self.enterContext(patch("apps.grafana.data_source.LogIndexSet"))
        model.objects.filter.return_value.first.return_value = self.index_set
        self.meta = self.enterContext(patch("apps.grafana.data_source.BkDataMetaApi.result_tables.storages"))
        self.meta.return_value = {"es": {"storage_cluster": {"version": "9.4.3"}}}
        self.query = self.enterContext(
            patch("apps.grafana.data_source.BkDataQueryApi.query", return_value={"list": {}})
        )
        self.route = self.enterContext(patch("apps.api.BkDataStorekitApi.storekit_es_route"))
        self.tenant = self.enterContext(
            patch("apps.grafana.data_source.get_request_tenant_id", return_value="tenant-a")
        )
        self.enterContext(patch("apps.grafana.data_source.update_bkdata_auth_info", side_effect=self.fill_auth))

    @staticmethod
    def fill_auth(params):
        params.update({"bkdata_authentication_method": "token", "bkdata_data_token": "test-token"})

    @staticmethod
    def body():
        return {
            "query": {"term": {"interval": "5m"}},
            "aggregations": {
                "group": {
                    "terms": {"field": "host", "order": [{"_key": "asc"}, {"_count": "desc"}]},
                    "aggs": {
                        "fixed": {"date_histogram": {"field": "ts", "fixed_interval": "1d"}},
                        "calendar": {"date_histogram": {"field": "ts", "calendar_interval": "1M"}},
                        "milliseconds": {"date_histogram": {"field": "ts", "interval": 60000}},
                    },
                }
            },
        }

    def sent_sql(self):
        return json.loads(self.query.call_args.args[0]["sql"])

    def test_log_and_es_keep_client_adaptation(self):
        body = self.body()
        for scenario, datasource_class in ((Scenario.LOG, LogCustomESDataSource), (Scenario.ES, ESCustomESDataSource)):
            with self.subTest(scenario=scenario), patch("apps.grafana.data_source.QueryClient") as client_factory:
                self.index_set.scenario_id = scenario
                self.index_set.storage_cluster_id = 77
                client = client_factory.return_value.get_instance.return_value
                client.query.return_value = {"hits": {"total": 0, "hits": []}}
                datasource = datasource_class(index_set_id=12)
                self.assertEqual(datasource.query(body), client.query.return_value)
                client.query.assert_called_once_with(index=datasource.index, body=body)
        self.meta.assert_not_called()
        self.query.assert_not_called()

    def test_bkdata_adapts_each_version_without_changing_input_or_authentication(self):
        body = self.body()
        original = copy.deepcopy(body)
        for version in ("5.6.16", "6.8.0", "7.1.0", "7.2.0", "7.10.2", "8.19.19", "9.4.3", None, "unknown"):
            with self.subTest(version=version):
                cache.clear()
                self.meta.return_value["es"]["storage_cluster"]["version"] = version
                datasource = BkDataCustomESDataSource(index_set_id=12)
                self.assertEqual(datasource.query(body), {})
                sql = self.sent_sql()
                self.assertEqual(sql["index"], "2_first_*,2_second_*")
                group = sql["body"]["aggregations"]["group"]
                modern = version in ("7.2.0", "7.10.2", "8.19.19", "9.4.3")
                order_key = "_term" if version in ("5.6.16", None, "unknown") else "_key"
                self.assertEqual(group["terms"]["order"], [{order_key: "asc"}, {"_count": "desc"}])
                if modern:
                    self.assertEqual(group["aggs"]["fixed"]["date_histogram"], {"field": "ts", "fixed_interval": "1d"})
                    self.assertEqual(
                        group["aggs"]["calendar"]["date_histogram"], {"field": "ts", "calendar_interval": "1M"}
                    )
                    self.assertEqual(
                        group["aggs"]["milliseconds"]["date_histogram"], {"field": "ts", "fixed_interval": "60000ms"}
                    )
                else:
                    self.assertEqual(group["aggs"]["fixed"]["date_histogram"], {"field": "ts", "interval": "1d"})
                    self.assertEqual(group["aggs"]["calendar"]["date_histogram"], {"field": "ts", "interval": "1M"})
                    self.assertEqual(
                        group["aggs"]["milliseconds"]["date_histogram"], {"field": "ts", "interval": 60000}
                    )
                self.assertEqual(sql["body"]["query"], body["query"])
                self.assertEqual(body, original)
                params = self.query.call_args.args[0]
                self.assertTrue(params["no_request"])
                self.assertEqual(params["bkdata_authentication_method"], "token")
                self.assertEqual(params["bkdata_data_token"], "test-token")
                self.assertEqual(self.query.call_args.kwargs, {"request_cookies": False})
        self.route.assert_not_called()

    def test_only_first_result_table_is_probed_and_cached_across_requests(self):
        self.index_set.indexes[0]["result_table_id"] = "2_first_123456"
        for second in ("2_second", "2_third"):
            self.index_set.indexes[1]["result_table_id"] = second
            BkDataCustomESDataSource(index_set_id=12).query(self.body())
            self.assertEqual(self.sent_sql()["index"], f"2_first_123456_*,{second}_*")
        self.meta.assert_called_once_with({"result_table_id": "2_first_123456"}, bk_tenant_id="tenant-a", timeout=3)
        self.route.assert_not_called()

    def test_cache_isolated_by_tenant_and_first_result_table(self):
        for tenant, result_table_id in (
            ("tenant-a", "2_first"),
            ("tenant-b", "2_first"),
            ("tenant-a", "2_other"),
            ("tenant-a", "2_first"),
        ):
            self.tenant.return_value = tenant
            self.index_set.indexes[0]["result_table_id"] = result_table_id
            BkDataCustomESDataSource(index_set_id=12).query(self.body())
        self.assertEqual(self.meta.call_count, 3)
        self.assertEqual(
            [call.kwargs["bk_tenant_id"] for call in self.meta.call_args_list], ["tenant-a", "tenant-b", "tenant-a"]
        )

    def test_probe_failure_uses_legacy_syntax_and_caches_failure(self):
        self.meta.side_effect = RuntimeError("metadata unavailable")
        body = self.body()
        original = copy.deepcopy(body)
        for _ in range(2):
            BkDataCustomESDataSource(index_set_id=12).query(body)
            group = self.sent_sql()["body"]["aggregations"]["group"]
            self.assertEqual(group["terms"]["order"][0], {"_term": "asc"})
            self.assertEqual(group["aggs"]["fixed"]["date_histogram"], {"field": "ts", "interval": "1d"})
        self.meta.assert_called_once()
        self.assertEqual(body, original)
        self.route.assert_not_called()

    def test_cache_failure_does_not_break_query(self):
        with patch.object(
            BkDataCustomESDataSource, "_get_cached_es_version", side_effect=RuntimeError("cache unavailable")
        ):
            BkDataCustomESDataSource(index_set_id=12).query(self.body())
            self.assertEqual(self.sent_sql()["body"]["aggregations"]["group"]["terms"]["order"][0], {"_term": "asc"})
        self.meta.assert_not_called()

    def test_unrelated_queries_skip_version_probe(self):
        for body in (
            {"query": {"term": {"interval": "5m"}}},
            {"aggs": {"group": {"terms": {"field": "host", "order": {"_count": "desc"}}}}},
        ):
            with self.subTest(body=body), patch.object(BkDataCustomESDataSource, "get_es_version") as get_version:
                BkDataCustomESDataSource(index_set_id=12).query(body)
                self.assertEqual(self.sent_sql()["body"], body)
                get_version.assert_not_called()
        self.meta.assert_not_called()

    def test_mapping_preserves_existing_route_and_skips_probe(self):
        with patch.object(BkDataCustomESDataSource, "get_es_version") as get_version:
            self.assertEqual(BkDataCustomESDataSource(index_set_id=12).mapping(), {})
            get_version.assert_not_called()
        self.assertEqual(self.sent_sql(), {"index": "2_first_*,2_second_*", "mapping": True})
        self.assertTrue(self.query.call_args.args[0]["no_request"])
        self.assertEqual(self.query.call_args.args[0]["bkdata_data_token"], "test-token")
        self.assertEqual(self.query.call_args.kwargs, {"request_cookies": False})
        self.meta.assert_not_called()
