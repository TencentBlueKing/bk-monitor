from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.exceptions import ValidationError
from apps.log_databus.constants import ExtJsonOverflowStrategy
from apps.log_databus.handlers.etl_storage.bk_log_json import BkLogJsonEtlStorage
from apps.log_databus.serializers import CollectorEtlStorageSerializer


class TestExtJsonConfigSerializer(SimpleTestCase):
    @staticmethod
    def _payload(ext_json_config, etl_config="bk_log_json", retain_extra_json=True):
        return {
            "table_id": "ext_json_test",
            "etl_config": etl_config,
            "etl_params": {
                "retain_extra_json": retain_extra_json,
                "ext_json_config": ext_json_config,
            },
            "fields": [
                {
                    "field_name": "message",
                    "field_type": "string",
                    "is_delete": False,
                }
            ],
            "storage_cluster_id": 1,
            "retention": 7,
            "allocation_min_days": 0,
        }

    def test_accepts_supported_depths_and_null(self):
        for depth in (1, 2, 3, None):
            serializer = CollectorEtlStorageSerializer(data=self._payload({"expand_depth": depth}))
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data["etl_params"]["ext_json_config"]["expand_depth"], depth)

    def test_explicit_new_config_defaults_to_depth_two(self):
        serializer = CollectorEtlStorageSerializer(data=self._payload({}))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["etl_params"]["ext_json_config"]["expand_depth"], 2)

    def test_rejects_unsupported_depth(self):
        for depth in (0, 4):
            serializer = CollectorEtlStorageSerializer(data=self._payload({"expand_depth": depth}))
            self.assertFalse(serializer.is_valid())

    def test_rejects_non_json_or_disabled_extra_json(self):
        serializer = CollectorEtlStorageSerializer(data=self._payload({"expand_depth": 2}, "bk_log_text"))
        with self.assertRaises(ValidationError):
            serializer.is_valid()

        serializer = CollectorEtlStorageSerializer(data=self._payload({"expand_depth": 2}, retain_extra_json=False))
        with self.assertRaises(ValidationError):
            serializer.is_valid()

    def test_public_serializer_does_not_accept_overflow_strategy(self):
        serializer = CollectorEtlStorageSerializer(
            data=self._payload({"expand_depth": 2, "overflow_strategy": "source_only"})
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("overflow_strategy", serializer.validated_data["etl_params"]["ext_json_config"])


class TestExtJsonResultTableConfig(SimpleTestCase):
    def setUp(self):
        self.storage = BkLogJsonEtlStorage()
        feature_toggle_patcher = patch(
            "apps.log_databus.handlers.etl_storage.bk_log_json.FeatureToggleObject.switch",
            return_value=True,
        )
        self.feature_toggle_switch = feature_toggle_patcher.start()
        self.addCleanup(feature_toggle_patcher.stop)

    @staticmethod
    def _params():
        return {
            "option": {},
            "field_list": [
                {
                    "field_name": "__ext_json",
                    "field_type": "object",
                    "option": {"es_type": "object"},
                }
            ],
            "default_storage_config": {
                "mapping_settings": {
                    "dynamic_templates": [
                        {
                            "strings_as_keywords": {
                                "match_mapping_type": "string",
                                "mapping": {"type": "keyword"},
                            }
                        }
                    ]
                }
            },
        }

    def _customize(
        self,
        ext_json_config_marker=True,
        ext_json_config=None,
        current_config=None,
        es_version="7.10.0",
        storage_cluster_type="elasticsearch",
    ):
        params = self._params()
        etl_params = {"retain_extra_json": True}
        if ext_json_config_marker:
            etl_params["ext_json_config"] = ext_json_config
        current = {"option": {}}
        if current_config is not None:
            current["option"]["ext_json_config"] = current_config
        self.storage.customize_result_table_config(
            params=params,
            etl_params=etl_params,
            current_result_table_config=current,
            es_version=es_version,
            storage_cluster_type=storage_cluster_type,
        )
        return params, etl_params

    def test_generates_exact_flattened_template_for_each_depth(self):
        for depth in (1, 2, 3):
            params, etl_params = self._customize(ext_json_config={"expand_depth": depth})
            template = params["default_storage_config"]["mapping_settings"]["dynamic_templates"][0]
            rule = template[f"ext_json_objects_at_depth_{depth}_as_flattened"]
            expected_path_suffix = r"\.[^.]+" * depth
            self.assertEqual(rule["path_match"], f"^__ext_json{expected_path_suffix}$")
            self.assertEqual(rule["match_pattern"], "regex")
            self.assertEqual(rule["match_mapping_type"], "object")
            self.assertEqual(rule["mapping"], {"type": "flattened"})
            self.assertEqual(etl_params["ext_json_config"]["overflow_strategy"], "flattened")

    def test_empty_new_config_defaults_to_depth_two(self):
        params, etl_params = self._customize(ext_json_config={})
        template = params["default_storage_config"]["mapping_settings"]["dynamic_templates"][0]
        self.assertIn("ext_json_objects_at_depth_2_as_flattened", template)
        self.assertEqual(etl_params["ext_json_config"]["expand_depth"], 2)

    def test_unlimited_depth_keeps_original_object_mapping(self):
        params, _ = self._customize(ext_json_config={"expand_depth": None})
        templates = params["default_storage_config"]["mapping_settings"]["dynamic_templates"]
        self.assertEqual(len(templates), 1)

    def test_source_only_disables_root_object_and_preserves_strategy(self):
        current_config = {"expand_depth": 1, "overflow_strategy": "source_only"}
        params, etl_params = self._customize(
            ext_json_config={"expand_depth": 2},
            current_config=current_config,
        )
        self.assertFalse(params["field_list"][0]["option"]["es_enabled"])
        self.assertEqual(etl_params["ext_json_config"]["overflow_strategy"], "source_only")

    def test_hidden_source_only_can_be_set_by_internal_call(self):
        params, _ = self._customize(
            ext_json_config={
                "expand_depth": 2,
                "overflow_strategy": ExtJsonOverflowStrategy.SOURCE_ONLY,
            }
        )
        self.assertFalse(params["field_list"][0]["option"]["es_enabled"])

    def test_existing_hidden_strategy_is_preserved_when_public_config_is_absent(self):
        current_config = {"expand_depth": 2, "overflow_strategy": "source_only"}
        params, etl_params = self._customize(
            ext_json_config_marker=False,
            current_config=current_config,
        )
        self.assertEqual(etl_params["ext_json_config"], current_config)
        self.assertFalse(params["field_list"][0]["option"]["es_enabled"])

    def test_disabled_feature_toggle_rejects_new_or_changed_config(self):
        self.feature_toggle_switch.return_value = False
        with self.assertRaises(ValidationError):
            self._customize(ext_json_config={"expand_depth": 2})
        with self.assertRaises(ValidationError):
            self._customize(
                ext_json_config={"expand_depth": 3},
                current_config={"expand_depth": 2, "overflow_strategy": "flattened"},
            )

    def test_disabled_feature_toggle_allows_unchanged_existing_config(self):
        self.feature_toggle_switch.return_value = False
        current_config = {"expand_depth": 2, "overflow_strategy": "flattened"}
        params, etl_params = self._customize(
            ext_json_config={"expand_depth": 2},
            current_config=current_config,
        )
        self.assertEqual(etl_params["ext_json_config"], current_config)
        self.assertIn(
            "ext_json_objects_at_depth_2_as_flattened",
            params["default_storage_config"]["mapping_settings"]["dynamic_templates"][0],
        )

    def test_rejects_unsupported_storage_and_es_version(self):
        cases = (
            {"storage_cluster_type": "doris"},
            {"es_version": "7.2.0"},
        )
        for kwargs in cases:
            with self.assertRaises(ValidationError):
                self._customize(ext_json_config={"expand_depth": 2}, **kwargs)

    def test_no_config_preserves_legacy_unlimited_behavior(self):
        params = self._params()
        original = deepcopy(params)
        etl_params = {"retain_extra_json": True}
        self.storage.customize_result_table_config(
            params=params,
            etl_params=etl_params,
            current_result_table_config={"option": {}},
            es_version="7.10.0",
            storage_cluster_type="elasticsearch",
        )
        self.assertEqual(params, original)


class TestExtJsonResultTableUpdate(SimpleTestCase):
    def setUp(self):
        self.storage = BkLogJsonEtlStorage()
        self.instance = SimpleNamespace(
            bk_data_id=1001,
            category_id="host_process",
            collector_scenario_id="host_process",
            enable_v4=True,
            index_set_id=0,
            is_nanos=False,
            storage_replies=1,
            storage_shards_nums=1,
            storage_shards_size=10,
            table_id="2_ext_json_test",
            get_bk_biz_id=lambda: 2,
            get_name=lambda: "ext json test",
            save=Mock(),
        )

    @staticmethod
    def _result_table_config():
        return {
            "option": {},
            "field_list": [
                {
                    "field_name": "__ext_json",
                    "field_type": "object",
                    "option": {"es_type": "object"},
                }
            ],
        }

    def _run_update(self, etl_params, current_option=None, feature_enabled=True):
        current_result_table = {
            "table_id": "2_ext_json_test",
            "option": current_option or {},
        }
        scenario = Mock()
        scenario.get_built_in_config.return_value = {}

        with (
            patch(
                "apps.log_databus.handlers.etl_storage.base.get_es_config",
                return_value={
                    "ES_DATE_FORMAT": "yyyy.MM.dd",
                    "ES_SHARDS_SIZE": 10,
                    "ES_SLICE_GAP": 1440,
                },
            ),
            patch(
                "apps.log_databus.handlers.etl_storage.base.TransferApi.get_result_table",
                return_value=current_result_table,
            ),
            patch(
                "apps.log_databus.handlers.etl_storage.base.CollectorScenario.get_instance",
                return_value=scenario,
            ),
            patch(
                "apps.log_databus.handlers.collector.CollectorHandler.build_result_table_id",
                return_value="2_ext_json_test",
            ),
            patch(
                "apps.log_databus.handlers.etl_storage.bk_log_json.FeatureToggleObject.switch",
                return_value=feature_enabled,
            ) as feature_toggle_switch,
            patch("apps.log_databus.tasks.collector.modify_result_table.delay") as modify_result_table_delay,
            patch.object(self.storage, "generate_fields_analysis", return_value={}),
            patch.object(
                self.storage,
                "get_result_table_config",
                return_value=self._result_table_config(),
            ),
        ):
            result = self.storage.update_or_create_result_table(
                instance=self.instance,
                table_id="ext_json_test",
                storage_cluster_id=1,
                retention=7,
                allocation_min_days=0,
                storage_replies=1,
                fields=[],
                etl_params=etl_params,
                es_version="7.10.0",
            )

        modify_result_table_delay.assert_called_once()
        return result["params"], feature_toggle_switch

    def test_update_payload_contains_config_and_template_without_rotation_flags(self):
        params, feature_toggle_switch = self._run_update(
            {
                "retain_extra_json": True,
                "ext_json_config": {"expand_depth": 2},
            }
        )

        self.assertEqual(
            params["option"]["ext_json_config"],
            {"expand_depth": 2, "overflow_strategy": "flattened"},
        )
        first_template = params["default_storage_config"]["mapping_settings"]["dynamic_templates"][0]
        self.assertIn("ext_json_objects_at_depth_2_as_flattened", first_template)
        self.assertNotIn("force_rotate", params)
        self.assertNotIn("is_sync", params)
        feature_toggle_switch.assert_called_once_with("ext_json_expand_depth", 2)

    def test_update_payload_supports_legacy_data_link(self):
        self.instance.enable_v4 = False

        params, _ = self._run_update(
            {
                "retain_extra_json": True,
                "ext_json_config": {"expand_depth": 2},
            }
        )

        first_template = params["default_storage_config"]["mapping_settings"]["dynamic_templates"][0]
        self.assertIn("ext_json_objects_at_depth_2_as_flattened", first_template)

    def test_disabling_extra_json_clears_existing_config_on_update_path(self):
        params, feature_toggle_switch = self._run_update(
            {"retain_extra_json": False},
            current_option={"ext_json_config": {"expand_depth": 2, "overflow_strategy": "flattened"}},
            feature_enabled=False,
        )

        self.assertNotIn("ext_json_config", params["option"])
        self.assertEqual(
            len(params["default_storage_config"]["mapping_settings"]["dynamic_templates"]),
            1,
        )
        feature_toggle_switch.assert_not_called()

    def test_result_table_option_is_returned_for_frontend_backfill(self):
        ext_json_config = {"expand_depth": 2, "overflow_strategy": "flattened"}
        collector_config = self.storage.parse_result_table_config(
            {
                "option": {"ext_json_config": ext_json_config},
                "field_list": [
                    {
                        "field_name": "dtEventTimeStamp",
                        "alias_name": "timestamp",
                        "option": {
                            "es_type": "date",
                            "time_zone": "8",
                        },
                    }
                ],
            }
        )

        self.assertEqual(collector_config["etl_params"]["ext_json_config"], ext_json_config)
