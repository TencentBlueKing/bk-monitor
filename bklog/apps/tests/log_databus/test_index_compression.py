from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.log_databus.constants import DORIS_CLUSTER_TYPE, STORAGE_CLUSTER_TYPE
from apps.log_databus.handlers.collector_plugin.bkbase import BKBaseCollectorPluginHandler
from apps.log_databus.handlers.etl_storage.bk_log_text import BkLogTextEtlStorage
from apps.log_databus.models import CollectorPlugin
from apps.tests.log_databus.v4_clean.testdata.built_in_configs import get_fresh_config


class TestIndexCompression(SimpleTestCase):
    def setUp(self):
        self.storage = BkLogTextEtlStorage()
        self.es_config = {
            "ES_DATE_FORMAT": "%Y%m%d",
            "ES_SHARDS_SIZE": 30,
            "ES_SLICE_GAP": 1440,
        }
        self.feature_config = {"global_es_config": self.es_config}
        self.instance = SimpleNamespace(
            bk_data_id=1,
            storage_shards_size=30,
            category_id="application",
            collector_scenario_id="row",
            table_id="2_codec_test",
            enable_v4=False,
            get_bk_biz_id=lambda: 2,
            get_name=lambda: "codec test",
            save=Mock(),
        )
        scenario = Mock()
        scenario.get_built_in_config.side_effect = lambda *args, **kwargs: get_fresh_config()
        patches = {
            "apps.log_databus.utils.es_config.FeatureToggleObject.toggle": {
                "return_value": SimpleNamespace(feature_config=self.feature_config)
            },
            "apps.log_databus.handlers.etl_storage.base.FeatureToggleObject.switch": {"return_value": False},
            "apps.log_databus.handlers.etl_storage.base.CollectorScenario.get_instance": {"return_value": scenario},
            "apps.log_databus.handlers.etl_storage.base.TransferApi.get_result_table": {
                "return_value": {"table_id": "2_codec_test"}
            },
            "apps.log_databus.handlers.etl_storage.base.TransferApi.create_result_table": {
                "return_value": {"table_id": "2_codec_test"}
            },
            "apps.log_databus.tasks.collector.modify_result_table.delay": {},
            "apps.log_databus.models.FieldDateFormat.get_field_date_format": {"return_value": []},
        }
        self.mocks = {}
        for target, kwargs in patches.items():
            patcher = patch(target, **kwargs)
            self.mocks[target.rsplit(".", 1)[-1]] = patcher.start()
            self.addCleanup(patcher.stop)

    def build_params(self, es_version="9.4.3", index_settings=None, storage_cluster_type=STORAGE_CLUSTER_TYPE):
        return self.storage.update_or_create_result_table(
            instance=self.instance,
            table_id="codec_test",
            storage_cluster_id=1,
            retention=7,
            allocation_min_days=0,
            storage_replies=1,
            fields=[],
            etl_params={},
            es_version=es_version,
            index_settings=index_settings,
            total_shards_per_node=3,
            storage_cluster_type=storage_cluster_type,
        )["params"]

    def test_new_and_existing_result_tables_default_to_compression_on_es8_and_es9(self):
        for version in ("8.0.0", "8.x", "9.4.3", "9.X"):
            for existing_table in ({}, {"table_id": "2_codec_test"}):
                with self.subTest(version=version, existing_table=bool(existing_table)):
                    self.mocks["get_result_table"].return_value = existing_table
                    params = self.build_params(version)
                    index_settings = params["default_storage_config"]["index_settings"]
                    self.assertEqual(index_settings["index.codec"], "best_compression")
                    self.assertEqual(index_settings["number_of_shards"], self.instance.storage_shards_nums)
                    self.assertEqual(index_settings["index.routing.allocation.total_shards_per_node"], 3)
                    if existing_table:
                        self.mocks["delay"].assert_called_with(params)
                    else:
                        self.mocks["create_result_table"].assert_called_with(params)
                    self.assertNotIn("force_rotate", params)

    def test_old_or_unknown_versions_keep_existing_defaults(self):
        for version in ("5.X", "6.8.0", "7.14.2", "7.x", "", "unknown"):
            with self.subTest(version=version):
                self.assertNotIn("index.codec", self.build_params(version)["default_storage_config"]["index_settings"])

    def test_explicit_index_settings_take_precedence_and_are_not_mutated(self):
        for version in ("8.19.0", "9.0.0"):
            for explicit_settings in (
                {"index.codec": "default"},
                {"codec": "default"},
                {"index": {"codec": "default"}},
            ):
                with self.subTest(version=version, index_settings=explicit_settings):
                    original = deepcopy(explicit_settings)
                    index_settings = self.build_params(version, index_settings=explicit_settings)[
                        "default_storage_config"
                    ]["index_settings"]
                    self.assertEqual(explicit_settings, original)
                    for key, value in original.items():
                        self.assertEqual(index_settings[key], value)
                    if "index.codec" not in original:
                        self.assertNotIn("index.codec", index_settings)

    def test_v4_uses_the_same_result_table_index_settings(self):
        self.instance.enable_v4 = True
        params = self.build_params()
        self.assertTrue(params["option"]["enable_log_v4_data_link"])
        self.assertIn("es_storage_config", params["option"]["log_v4_data_link"])
        self.assertEqual(params["default_storage_config"]["index_settings"]["index.codec"], "best_compression")

    def test_doris_does_not_receive_default_codec(self):
        params = self.build_params(storage_cluster_type=DORIS_CLUSTER_TYPE)
        self.assertNotIn("index.codec", params["default_storage_config"]["index_settings"])
        self.assertIn("doris_storage_config", params["option"]["log_v4_data_link"])

    def test_collector_plugin_explicit_codec_is_preserved(self):
        plugin = CollectorPlugin(
            bk_biz_id=2,
            collector_plugin_name="codec test",
            collector_plugin_name_en="codec_test",
            bk_data_id=1,
            table_id="2_codec_test",
            collector_scenario_id="row",
            etl_config="bk_log_text",
            fields=[],
            etl_params={},
            storage_cluster_id=1,
            retention=7,
            storage_replies=1,
            storage_shards_nums=2,
            storage_shards_size=30,
            allocation_min_days=0,
            is_allow_alone_storage=False,
            index_settings={"index.codec": "default"},
        )
        handler = BKBaseCollectorPluginHandler()
        handler.collector_plugin = plugin
        with patch("apps.log_databus.handlers.collector_plugin.bkbase.StorageHandler") as storage_handler:
            storage_handler.return_value.get_cluster_info_by_id.return_value = {"cluster_config": {"version": "9.4.3"}}
            handler._create_metadata_result_table()
        index_settings = self.mocks["delay"].call_args.args[0]["default_storage_config"]["index_settings"]
        self.assertEqual(index_settings["index.codec"], "default")
        self.assertEqual(plugin.index_settings, {"index.codec": "default"})
