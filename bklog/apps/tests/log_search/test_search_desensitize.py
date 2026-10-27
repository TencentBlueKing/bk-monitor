"""
Real-DB integration tests: SearchHandler desensitize for third-party ES index sets.

Covers scenario_id='es' (third-party ES) with and without desensitize config
through the legacy SearchHandler (search_handlers_esquery) _deal_query_result path.

Test strategy
  - Real LogIndexSet + LogIndexSetData + DesensitizeConfig + DesensitizeFieldConfig
    in SQLite (Django TestCase transaction isolation).
  - Only external / network dependencies are mocked:
    * request context (get_request, get_request_username, auth_info)
    * feature toggle (FeatureToggleObject.toggle)
    * CMDB host cache (CmdbHostCache.get)
    * mapping nested-field check (MappingHandlers.is_nested_field)
  - SearchHandler constructor runs with pre_check_enable=False and sort_list
    to avoid mapping_handler / PreSearchHandlers dependencies.
  - _deal_query_result is called directly with fabricated ES-hit-shaped dicts.
"""

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_desensitize.utils import _extract_value_by_path
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData

SPACE_UID = "bkcc__2"

BASE_SEARCH_DICT = {
    "bk_biz_id": 2,
    "keyword": "test",
    "start_time": "2026-09-27 00:00:00",
    "end_time": "2026-09-28 00:00:00",
    "sort_list": [],
    "size": 50,
}

# ---- desensitize payload helpers -------------------------------------------

MASK_CONFIG = {
    "field_name": "message",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}

TEXT_REPLACE_CONFIG = {
    "field_name": "log",
    "rule_id": 0,
    "operator": "text_replace",
    "params": {"template_string": "[FILTERED]"},
    "match_pattern": ".*",
    "sort_index": 0,
}

NESTED_MASK_CONFIG = {
    "field_name": "body.player.id",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}


def fake_hits(*, message="plain message", log="plain log"):
    """Return a result_dict shaped like a legacy ES query response."""
    return {
        "took": 10,
        "hits": {
            "total": 1,
            "hits": [
                {
                    "_index": "v2_2_bklog_test_es_20260927_0",
                    "_source": {
                        "dtEventTimeStamp": 1727452800000,
                        "message": message,
                        "log": log,
                    },
                }
            ],
        },
    }


def fake_hits_nested(*, body="", log="plain log"):
    """Return a result_dict with nested ``body`` field (dict or JSON string)."""
    return {
        "took": 10,
        "hits": {
            "total": 1,
            "hits": [
                {
                    "_index": "v2_2_bklog_test_es_20260927_0",
                    "_source": {
                        "dtEventTimeStamp": 1727452800000,
                        "message": "plain",
                        "log": log,
                        "body": body,
                    },
                }
            ],
        },
    }


@override_settings(
    ESQUERY_WHITE_LIST=["bk_log"],
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
)
class TestSearchHandlerDesensitize(TestCase):
    """
    SearchHandler desensitize with scenario_id='es'.

    ESQUERY_WHITE_LIST contains the mocked caller app code so that an explicit
    is_desensitize=False is honoured (non-whitelisted callers are force-masked
    by _init_desensitize, which is tested implicitly elsewhere).
    """

    def setUp(self):
        # Real model records (shared across all test methods)
        self.index_set = LogIndexSet.objects.create(
            index_set_name="test-es-desensitize-search",
            space_uid=SPACE_UID,
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
        )
        self.index_set_id = self.index_set.index_set_id

        LogIndexSetData.objects.create(
            index_set_id=self.index_set_id,
            bk_biz_id=2,
            result_table_id="2_bklog.test_es_desensitize",
            apply_status="normal",
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
        )

        self._clean()

    def tearDown(self):
        self._clean()

    # ---- helpers -----------------------------------------------------------

    def _clean(self):
        DesensitizeConfig.objects.filter(index_set_id=self.index_set_id).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=self.index_set_id).delete()

    def _put_config(self, field_configs, text_fields=None):
        """Create a desensitize config + field configs in DB."""
        DesensitizeConfig.objects.create(
            index_set_id=self.index_set_id,
            text_fields=text_fields or [],
        )
        for fc in field_configs:
            DesensitizeFieldConfig.objects.create(
                index_set_id=self.index_set_id,
                field_name=fc["field_name"],
                rule_id=fc.get("rule_id", 0),
                operator=fc["operator"],
                params=fc.get("params", {}),
                match_pattern=fc.get("match_pattern", ""),
                sort_index=fc.get("sort_index", 0),
            )

    def _build_handler(self, search_dict_extra=None, **constructor_kw):
        """Build a SearchHandler with request-context mocks.

        ``search_dict_extra`` is merged into the base search dict.
        Extra keyword arguments (e.g. ``export_fields=[...]``) are
        forwarded to the SearchHandler constructor.
        """
        sd = dict(BASE_SEARCH_DICT)
        sd.update(search_dict_extra or {})

        with (
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request",
                return_value=Mock(),
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_username",
                return_value="test_user",
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.Permission.get_auth_info",
                return_value={"bk_app_code": "bk_log", "bk_username": "test_user"},
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.FeatureToggleObject.toggle",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
                return_value=False,
            ),
            patch(
                "apps.utils.core.cache.cmdb_host.CmdbHostCache.get",
                return_value={},
            ),
        ):
            return SearchHandler(
                index_set_id=self.index_set_id,
                search_dict=sd,
                pre_check_enable=False,
                **constructor_kw,
            )

    # ------------------------------------------------------------------
    # Test: with desensitize config → fields are masked
    # ------------------------------------------------------------------

    def test_with_config_message_desensitized(self):
        """scenario_id='es' + desensitize config: message field is masked."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        # "Hello World1234" = 15 chars; mask_shield(2,2) → "He" + 11×"*" + "34"
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "He***********34")
        self.assertEqual(logs[0]["__index_set_id__"], self.index_set_id)

    # ------------------------------------------------------------------
    # Test: without desensitize config → plain text
    # ------------------------------------------------------------------

    def test_without_config_message_unchanged(self):
        """scenario_id='es' + NO desensitize config: message unchanged."""
        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(message="plain message content")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "plain message content")

    # ------------------------------------------------------------------
    # Test: is_desensitize=False → plain text
    # ------------------------------------------------------------------

    def test_is_desensitize_false_skips_desensitize(self):
        """is_desensitize=False on a configured index set: no masking."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"is_desensitize": False})
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: original_search=True → plain text
    # ------------------------------------------------------------------

    def test_original_search_short_circuits_desensitize(self):
        """original_search=True returns plain text even with config."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"original_search": True})
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: export_fields path with desensitize
    # ------------------------------------------------------------------

    def test_export_fields_preserves_desensitize(self):
        """
        export_fields filters origin_log_list but desensitize still applies
        to the log_list entries.
        """
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler(
            export_fields=["message", "dtEventTimeStamp"],
        )
        # Mock the fields() call inside _deal_query_result so it returns the
        # export fields as valid (avoids real mapping_handler dependency).
        with patch.object(handler, "fields", return_value={
            "fields": [{"field_name": "message"}, {"field_name": "dtEventTimeStamp"}],
        }):
            result = handler._deal_query_result(
                fake_hits(message="Hello World1234")
            )

        # origin_log_list is the export-filtered output
        logs = result["origin_log_list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "He***********34")
        # non-exported fields are removed in origin_log_list
        self.assertNotIn("log", logs[0])

    # ------------------------------------------------------------------
    # Test: text_fields — log field gets text-field desensitize
    # ------------------------------------------------------------------

    def test_text_fields_are_desensitized(self):
        """text_fields config causes the 'log' field to be masked."""
        self._put_config(
            field_configs=[TEXT_REPLACE_CONFIG],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(log="sensitive data here")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["log"], "[FILTERED]")

    # ------------------------------------------------------------------
    # Test: _init_desensitize returns expected boolean
    # ------------------------------------------------------------------

    def test_init_desensitize_default_true(self):
        """Default is_desensitize is True when not specified."""
        handler = self._build_handler()
        self.assertIsInstance(handler.is_desensitize, bool)
        self.assertTrue(handler.is_desensitize)

    def test_init_desensitize_original_search_false(self):
        """original_search=True makes is_desensitize=False."""
        handler = self._build_handler({"original_search": True})
        self.assertFalse(handler.is_desensitize)

    # ------------------------------------------------------------------
    # End-to-end: IndexSetHandler (CRUD) → SearchHandler (query)
    # ------------------------------------------------------------------

    def test_end_to_end_via_index_set_handler(self):
        """
        Real CRUD through IndexSetHandler.update_or_create_desensitize_config,
        then query through SearchHandler._deal_query_result.
        Validates that the same payload saved by the config page is correctly
        applied by the search pipeline (linkage between Phase 2 CRUD tests
        and Phase 2 search tests).
        """
        from apps.log_search.handlers.index_set import IndexSetHandler

        INDEX_SET_ID = self.index_set_id

        # ---- Save config via IndexSetHandler (real production code) ----
        handler_instance = IndexSetHandler(index_set_id=INDEX_SET_ID)
        payload = {
            "field_configs": [
                {
                    "field_name": "message",
                    "rules": [
                        {
                            "operator": "mask_shield",
                            "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
                            "match_pattern": ".*",
                            "state": "add",
                        },
                    ],
                }
            ],
            "text_fields": [],
        }
        handler_instance.update_or_create_desensitize_config(payload)

        # ---- Verify config landed in DB ----
        self.assertEqual(
            DesensitizeConfig.objects.filter(index_set_id=INDEX_SET_ID).count(), 1
        )
        self.assertEqual(
            DesensitizeFieldConfig.objects.filter(index_set_id=INDEX_SET_ID).count(), 1
        )

        # ---- Now run SearchHandler to verify the saved config takes effect ----
        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")

    # ------------------------------------------------------------------
    # Phase 4: field selection for ES scenario (V1)
    # ------------------------------------------------------------------

    def test_fields_returns_field_type_for_es_scenario(self):
        """
        The field list built for scenario_id='es' must include a non-empty
        field_type for every entry, since the desensitize operators
        (e.g. mask_shield) are only meaningful for string/text fields.

        BkLogApi.mapping is mocked (external ES call) while all other data
        (index set, field snapshot) uses real model records.
        """
        from apps.log_search.handlers.search.mapping_handlers import MappingHandlers

        # Fabricated ES mapping response — real BkLogApi.mapping shape.
        fake_mapping = [
            {
                "2_bklog.test_es_desensitize": {
                    "mappings": {
                        "properties": {
                            "message": {"type": "text"},
                            "log": {"type": "text"},
                            "server_ip": {"type": "keyword"},
                            "dtEventTimeStamp": {"type": "date"},
                            "bytes": {"type": "long"},
                        }
                    }
                }
            }
        ]

        mapping_handlers = MappingHandlers(
            indices="2_bklog.test_es_desensitize",
            index_set_id=self.index_set_id,
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            start_time="2026-09-27 00:00:00",
            end_time="2026-09-28 00:00:00",
        )

        with patch(
            "apps.log_search.handlers.search.mapping_handlers.BkLogApi.mapping",
            return_value=fake_mapping,
        ):
            fields = mapping_handlers.final_fields

        # Every field must carry a non-empty string field_type.
        self.assertGreater(len(fields), 0)
        expected_types = {
            "message": "text",
            "log": "text",
            "server_ip": "keyword",
            "dtEventTimeStamp": "date",
            "bytes": "long",
        }
        actual_types = {f["field_name"]: f["field_type"] for f in fields}
        for field_name, expected_type in expected_types.items():
            self.assertEqual(actual_types[field_name], expected_type)

        # Explicit: type must be a non-empty string for each entry.
        for field in fields:
            self.assertIsInstance(field["field_type"], str)
            self.assertNotEqual(field["field_type"], "")

    # ------------------------------------------------------------------
    # Test: scroll_search path also applies desensitize
    # ------------------------------------------------------------------

    @patch("apps.log_search.handlers.search.search_handlers_esquery.BkLogApi.scroll")
    def test_scroll_search_desensitized(self, mock_scroll):
        """
        scroll_search() with an existing scroll_id goes through
        BkLogApi.scroll → _deal_query_result.  Verify the desensitize
        transform is applied on that path too.
        """
        self._put_config(field_configs=[MASK_CONFIG])

        mock_scroll.return_value = fake_hits(message="Hello World1234")

        handler = self._build_handler({"scroll_id": "dummy_scroll_id"})
        result = handler.scroll_search()

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")
        self.assertEqual(logs[0]["__index_set_id__"], self.index_set_id)

        mock_scroll.assert_called_once()

    # ------------------------------------------------------------------
    # Test: collector-based (scenario_id='log') regression
    # ------------------------------------------------------------------

    def test_collector_scenario_no_regression(self):
        """
        Regression: collector-based index sets (scenario_id='log') with
        an existing desensitize config must still produce masked results.
        This ensures the ES-focused changes do not break the original path.
        """
        collector_index_set = LogIndexSet.objects.create(
            index_set_name="test-collector-desensitize",
            space_uid=SPACE_UID,
            scenario_id="log",
            collector_config_id=999,
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
        )
        collector_index_set_id = collector_index_set.index_set_id
        self.addCleanup(lambda: LogIndexSet.objects.filter(index_set_id=collector_index_set_id).delete())

        LogIndexSetData.objects.create(
            index_set_id=collector_index_set_id,
            bk_biz_id=2,
            result_table_id="2_bklog.test_collector_desensitize",
            apply_status="normal",
            scenario_id="log",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
        )

        # Put config on the collector index set
        DesensitizeConfig.objects.create(
            index_set_id=collector_index_set_id,
            text_fields=[],
        )
        DesensitizeFieldConfig.objects.create(
            index_set_id=collector_index_set_id,
            field_name="message",
            rule_id=0,
            operator="mask_shield",
            params={"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
            match_pattern=".*",
            sort_index=0,
        )

        sd = dict(BASE_SEARCH_DICT)
        with (
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler._init_indices_str",
                return_value="2_bklog.test_collector_desensitize",
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request",
                return_value=Mock(),
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_username",
                return_value="test_user",
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.Permission.get_auth_info",
                return_value={"bk_app_code": "bk_log", "bk_username": "test_user"},
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.FeatureToggleObject.toggle",
                return_value=None,
            ),
            patch(
                "apps.log_search.handlers.search.mapping_handlers.MappingHandlers.is_nested_field",
                return_value=False,
            ),
            patch(
                "apps.utils.core.cache.cmdb_host.CmdbHostCache.get",
                return_value={},
            ),
            patch(
                "apps.log_search.handlers.search.search_handlers_esquery.SearchHandler.init_time_field",
                return_value=("dtEventTimeStamp", "time", "s"),
            ),
        ):
            handler = SearchHandler(
                index_set_id=collector_index_set_id,
                search_dict=sd,
                pre_check_enable=False,
            )

        result = handler._deal_query_result(fake_hits(message="Hello World1234"))

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "He***********34")

    # ------------------------------------------------------------------
    # End of #9923 test cases
    # ------------------------------------------------------------------

    # ==================================================================
    # Tests for #1010158081138539921: flattened / JSON string subpath
    # ==================================================================

    def test_flattened_object_subpath_desensitized_via_log_desensitize(self):
        """JSON 字符串嵌套 object 子路径脱敏生效，结果仍为字符串（_log_desensitize 验证）"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        log = {"body": '{"player":{"id":"12345"}}'}
        desensitized = handler._log_desensitize(log)

        self.assertIsInstance(desensitized["body"], str)
        parsed = json.loads(desensitized["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")

    def test_json_string_subpath_desensitized_via_log_desensitize(self):
        """JSON 字符串子路径脱敏生效，且结果仍为字符串（_log_desensitize 单元验证）"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        log = {"body": '{"player":{"id":"12345"},"server":{"ip":"10.0.0.1"}}'}
        desensitized = handler._log_desensitize(log)

        self.assertIsInstance(desensitized["body"], str)
        parsed = json.loads(desensitized["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        # 未配置脱敏的子字段保持原值
        self.assertEqual(parsed["server"]["ip"], "10.0.0.1")

    def test_flattened_subpath_via_deal_query_result(self):
        """通过 _deal_query_result 完整链路验证 JSON 字符串子路径脱敏"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(body='{"player":{"id":"12345"}}')
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")

    def test_json_string_subpath_via_deal_query_result(self):
        """通过 _deal_query_result 完整链路验证 JSON 字符串子路径脱敏"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(body='{"player":{"id":"12345"},"server":{"ip":"10.0.0.1"}}')
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        self.assertEqual(parsed["server"]["ip"], "10.0.0.1")

    def test_text_fields_with_subpath_desensitize(self):
        """text_fields 原文替换 + JSON 字符串子路径脱敏同时生效"""
        self._put_config(
            field_configs=[
                NESTED_MASK_CONFIG,
                TEXT_REPLACE_CONFIG,
            ],
            text_fields=["log"],
        )

        handler = self._build_handler()
        log = {
            "body": '{"player":{"id":"12345"}}',
            "log": "user id is 12345",
        }
        desensitized = handler._log_desensitize(log)

        # JSON 字符串子路径脱敏生效，结果仍为字符串
        self.assertIsInstance(desensitized["body"], str)
        parsed = json.loads(desensitized["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        # text_fields 自身脱敏生效（text_replace 整体替换）
        self.assertEqual(desensitized["log"], "[FILTERED]")

    def test_text_fields_with_subpath_via_deal_query_result(self):
        """通过完整链路验证 text_fields + JSON 字符串子路径脱敏同时生效"""
        self._put_config(
            field_configs=[
                NESTED_MASK_CONFIG,
                TEXT_REPLACE_CONFIG,
            ],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(body='{"player":{"id":"12345"}}', log="user id is 12345")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # JSON 字符串子路径脱敏
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        # text_fields 自身脱敏生效
        self.assertEqual(logs[0]["log"], "[FILTERED]")

    def test_no_config_preserves_original_structure(self):
        """无脱敏配置时，JSON 字符串保持原值不被解析"""
        handler = self._build_handler()
        log = {"body": '{"player":{"id":"12345"}}'}
        desensitized = handler._log_desensitize(log)

        # 无配置时 path_aware_expand 不会解析 JSON 字符串（不在祖先路径中），
        # restore_by_metadata 按 scalar 还原，字符串保持原值
        self.assertEqual(desensitized["body"], '{"player":{"id":"12345"}}')

    def test_normal_object_nested_no_regression(self):
        """普通 object 嵌套字段（JSON 字符串形态）的脱敏不回退"""
        normal_config = {
            "field_name": "user.phone",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
            "match_pattern": ".*",
            "sort_index": 0,
        }
        self._put_config(field_configs=[normal_config])

        handler = self._build_handler()
        log = {"user": '{"name":"alice","phone":"13234345678"}'}
        desensitized = handler._log_desensitize(log)

        self.assertIsInstance(desensitized["user"], str)
        parsed = json.loads(desensitized["user"])
        self.assertEqual(parsed["name"], "alice")
        self.assertEqual(parsed["phone"], "13*******78")

    def test_match_pattern_no_match_skips_desensitize(self):
        """正则不匹配时跳过脱敏，JSON 字符串内子路径值保持原值"""
        strict_config = {
            "field_name": "body.player.id",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": "^\\d{10,}$",  # 仅匹配纯数字 10 位以上
            "sort_index": 0,
        }
        self._put_config(field_configs=[strict_config])

        handler = self._build_handler()
        log = {"body": '{"player":{"id":"abc"}}'}  # 非纯数字，不匹配
        desensitized = handler._log_desensitize(log)

        self.assertIsInstance(desensitized["body"], str)
        parsed = json.loads(desensitized["body"])
        self.assertEqual(parsed["player"]["id"], "abc")

    # ==================================================================
    # 补充关键场景：dot 1 缺陷修复验证
    # ==================================================================

    def test_json_string_with_text_fields_end_to_end(self):
        """缺失场景 1：JSON 字符串 + text_fields 原文替换验证。

        当 body 为 JSON 字符串且配置了 text_fields 时，
        body 内部子路径脱敏后，脱敏结果应同步替换到 log 原文中，
        且 body 仍保持为 JSON 字符串。
        """
        self._put_config(
            field_configs=[
                NESTED_MASK_CONFIG,
                TEXT_REPLACE_CONFIG,
            ],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(
                body='{"player":{"id":"12345"}}',
                log="user id is 12345",
            )
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # body 仍为 JSON 字符串，内部值被脱敏
        self.assertIsInstance(logs[0]["body"], str)
        parsed_body = json.loads(logs[0]["body"])
        self.assertEqual(parsed_body["player"]["id"], "1***5")
        # text_fields 原文替换生效：log 中的 12345 被替换为脱敏后的值
        self.assertEqual(logs[0]["log"], "[FILTERED]")

    def test_multi_layer_json_string_nesting_end_to_end(self):
        """多层 JSON 字符串嵌套验证。

        body 是 JSON 字符串，其内部某字段值又是 JSON 字符串（多层嵌套），
        脱敏应递归穿透所有层级，最终 body 仍为 JSON 字符串，
        且内层 inner 仍保持为 JSON 字符串（容器类型不被破坏）。
        """
        inner_config = {
            "field_name": "body.inner.secret",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": ".*",
            "sort_index": 0,
        }
        self._put_config(field_configs=[inner_config])

        handler = self._build_handler()
        # body 是 JSON 字符串，inner 也是 JSON 字符串
        log = {"body": '{"outer":"hello","inner":"{\\"secret\\":\\"99999\\"}"}'}
        desensitized = handler._log_desensitize(log)

        # body 仍为 JSON 字符串
        self.assertIsInstance(desensitized["body"], str)
        parsed_body = json.loads(desensitized["body"])
        # outer 未配置脱敏，保持原值
        self.assertEqual(parsed_body["outer"], "hello")
        # inner 仍为 JSON 字符串（类型未被破坏），secret 被脱敏
        self.assertIsInstance(parsed_body["inner"], str)
        parsed_inner = json.loads(parsed_body["inner"])
        self.assertEqual(parsed_inner["secret"], "9***9")

    def test_json_string_top_level_field_with_regex_partial_match(self):
        """缺失场景 3：JSON 字符串顶层字段 + 正则匹配部分内容。

        配置 field_name 为顶层字段（如 message），值为 JSON 字符串，
        正则匹配 JSON 字符串中部分内容进行脱敏，其余内容保持不变。
        """
        regex_config = {
            "field_name": "message",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 0, "preserve_tail": 0, "replace_mark": "*"},
            "match_pattern": r"\d{5}",  # 匹配连续 5 位数字
            "sort_index": 0,
        }
        self._put_config(field_configs=[regex_config])

        handler = self._build_handler()
        # message 值为 JSON 字符串，内含 5 位数字
        result = handler._deal_query_result(
            fake_hits(message='{"uid":"12345","name":"test"}')
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # 12345 被匹配并脱敏为 *****，JSON 字符串其余内容不变
        self.assertEqual(logs[0]["message"], '{"uid":"*****","name":"test"}')

    def test_json_string_top_level_field_with_text_fields_self_desensitize(self):
        """缺失场景 3 补充：JSON 字符串顶层字段自身在 text_fields 中。

        当 text_field 自身也是 JSON 字符串，且配置了子路径脱敏规则时，
        验证 text_fields 原文替换逻辑对 JSON 字符串顶层字段的处理。
        """
        top_level_config = {
            "field_name": "message",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
            "match_pattern": ".*",
            "sort_index": 0,
        }
        self._put_config(
            field_configs=[top_level_config],
            text_fields=["message"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # message 在 text_fields 中，自身脱敏规则生效
        self.assertEqual(logs[0]["message"], "He***********34")

    def test_oversized_json_fail_closed_end_to_end(self):
        """超大 JSON + 子路径规则：整条字段被遮罩而非明文"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        large_body = '{"player":{"id":"' + "x" * 70000 + '"}}'
        result = handler._deal_query_result(
            fake_hits_nested(body=large_body)
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # 超大 + 子路径规则 → fail-closed
        self.assertEqual(logs[0]["body"], "***MASKED***")

    def test_oversized_json_without_subpath_preserved_end_to_end(self):
        """超大 JSON + 无子路径规则：保持原值"""
        self._put_config(field_configs=[])

        handler = self._build_handler()
        large_body = '{"player":{"id":"' + "x" * 70000 + '"}}'
        result = handler._deal_query_result(
            fake_hits_nested(body=large_body)
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # 无子路径规则时保持原值
        self.assertEqual(logs[0]["body"], large_body)

    def test_deep_json_masked_by_prescan(self):
        """一条极深 JSON 被预扫描拦截后遮罩，不影响同查询中其他日志"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        # 构造包含两条日志的 ES 响应：一条正常、一条极深 JSON
        normal_hit = {
            "_index": "v2_2_bklog_test_es_20260927_0",
            "_source": {
                "dtEventTimeStamp": 1727452800000,
                "message": "normal",
                "body": '{"player":{"id":"12345"}}',
            },
        }
        deep_json = '{"a":' * 1100 + '"secret"' + '}' * 1100
        deep_hit = {
            "_index": "v2_2_bklog_test_es_20260927_0",
            "_source": {
                "dtEventTimeStamp": 1727452800000,
                "message": "deep",
                "body": deep_json,
            },
        }

        result = handler._deal_query_result(
            {
                "took": 10,
                "hits": {"total": 2, "hits": [deep_hit, normal_hit]},
            }
        )

        logs = result["list"]
        # 两条日志都返回（不因一条失败而中断查询）
        self.assertEqual(len(logs), 2)
        # 正常日志正确脱敏
        found_normal = [l for l in logs if l.get("message") == "normal"]
        self.assertEqual(len(found_normal), 1)
        self.assertIsInstance(found_normal[0]["body"], str)
        parsed = json.loads(found_normal[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        # 极深日志被预扫描拦截 → fail-closed 遮罩
        found_deep = [l for l in logs if l.get("message") == "deep"]
        self.assertEqual(len(found_deep), 1)
        self.assertEqual(found_deep[0]["body"], "***MASKED***")

    def test_log_desensitize_exception_isolation(self):
        """_log_desensitize 异常被外层 try/except 捕获，不影响其他日志"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        normal_hit = {
            "_index": "v2_2_bklog_test_es_20260927_0",
            "_source": {
                "dtEventTimeStamp": 1727452800000,
                "message": "normal",
                "body": '{"player":{"id":"12345"}}',
            },
        }
        # 构造超深嵌套 dict，深度截断 + deepcopy 兜底双重保护
        # 确保即使最深路径也不会抛异常，且不影响正常日志脱敏
        deep_dict = {}
        current = deep_dict
        for i in range(15000):
            current["n"] = {}
            current = current["n"]
        current["leaf"] = "target"

        rogue_hit = {
            "_index": "v2_2_bklog_test_es_20260927_0",
            "_source": {
                "dtEventTimeStamp": 1727452800000,
                "message": "rogue",
                "body": deep_dict,
            },
        }

        result = handler._deal_query_result(
            {
                "took": 10,
                "hits": {"total": 2, "hits": [rogue_hit, normal_hit]},
            }
        )

        logs = result["list"]
        # 两条日志都返回
        self.assertEqual(len(logs), 2)
        # 正常日志正确脱敏
        found_normal = [l for l in logs if l.get("message") == "normal"]
        self.assertEqual(len(found_normal), 1)
        self.assertIsInstance(found_normal[0]["body"], str)
        parsed = json.loads(found_normal[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        # 超深日志不中断、不丢失
        found_rogue = [l for l in logs if l.get("message") == "rogue"]
        self.assertEqual(len(found_rogue), 1)
        self.assertIn("body", found_rogue[0])

    def test_json_literal_dot_key_preserved_end_to_end(self):
        """JSON 内字面点号 key 与普通 key 共存都必须保留。

        ``body='{"a":"scalar","a.b":"secret"}'``，配置 ``body.a.b``。
        修复前：``_build_nested_dict`` 盲分 ``body.a.b``，标量 ``"scalar"`` 被覆盖丢失。
        修复后：两个字面/普通 key 都完整保留在还原结果中。
        """
        config = {
            "field_name": "body.a.b",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": ".*",
            "sort_index": 0,
        }
        self._put_config(field_configs=[config])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(body='{"a":"scalar","a.b":"secret"}')
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        # 两个 key 都保留：普通 key "a" 保持原值，字面 key "a.b" 被脱敏
        self.assertEqual(parsed["a"], "scalar")
        self.assertEqual(parsed["a.b"], "s****t")

    def test_json_literal_dot_key_does_not_break_es_flattened_top_level(self):
        """ES-flattened 顶层 dotted key：仍按路径分隔符正常 re-nest 并脱敏"""
        # 顶层 flat key "__ext_json.deployment.pod.name"
        config = {
            "field_name": "__ext_json.deployment.pod.name",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": ".*",
            "sort_index": 0,
        }
        self._put_config(field_configs=[config])

        handler = self._build_handler()
        source = {
            "dtEventTimeStamp": 1727452800000,
            "message": "plain",
            "__ext_json.deployment.pod.name": "secretname",
        }
        result = handler._deal_query_result(
            {
                "took": 10,
                "hits": {
                    "total": 1,
                    "hits": [
                        {
                            "_index": "v2_2_bklog_test_es_20260927_0",
                            "_source": source,
                        }
                    ],
                },
            }
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # ES-flattened dotted key 还原为嵌套结构
        self.assertIsInstance(logs[0]["__ext_json"], dict)
        self.assertEqual(logs[0]["__ext_json"]["deployment"]["pod"]["name"], "s********e")

    def test_json_literal_dot_key_and_nested_object_coexist_end_to_end(self):
        """字面点号 key 与普通嵌套对象共存：两者语义互不混淆"""
        # "a.b" 是字面 key(标量)，"a" 是普通 key(对象)
        config = {
            "field_name": "body.a.c",
            "rule_id": 0,
            "operator": "mask_shield",
            "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
            "match_pattern": ".*",
            "sort_index": 0,
        }
        self._put_config(field_configs=[config])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(body='{"a":{"c":"value1"},"a.b":"value2"}')
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        # "a" 下嵌套的 "c" 被脱敏
        self.assertEqual(parsed["a"]["c"], "v****1")
        # 字面 key "a.b" 完整保留原值（未配置该路径）
        self.assertEqual(parsed["a.b"], "value2")

    def test_deep_dict_subtree_preserved(self):
        """超深嵌套 dict（depth > max_depth=10）子树通过 _log_desensitize 完整
        链路后仍保留为嵌套 dict，且浅层 leaf 正常脱敏。"""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        # 构造 depth=15 的嵌套 dict
        inner = {}
        current = inner
        for i in range(15):
            current["level"] = {}
            current["leaf"] = f"value_{i}"
            current = current["level"]

        log = {"body": inner, "message": "Hello World1234"}
        desensitized = handler._log_desensitize(log)

        # 浅层字段正常脱敏
        self.assertEqual(desensitized["message"], "He***********34")
        # body 仍是 dict，其内部 depth<=10 的 leaf 存在
        self.assertIsInstance(desensitized["body"], dict)
        # depth=11 的 level 子树作为 dict 保留（而非丢失或遮罩）
        deep_level = desensitized["body"]
        for d in range(12):
            self.assertIsInstance(
                deep_level, dict,
                "At restored depth {}, expected dict but got {}".format(d, type(deep_level)),
            )
            self.assertIn("leaf", deep_level,
                          "At restored depth {}, expected 'leaf' key".format(d))
            deep_level = deep_level.get("level", {})


    # ==================================================================
    # 补充场景：text_fields + fail-closed 遮罩的兼容性验证
    # ==================================================================

    def test_text_fields_with_fail_closed_oversized_no_crash(self):
        """text_fields + 超大 JSON + 子路径规则：不崩溃，body 被遮罩"""
        self._put_config(
            field_configs=[NESTED_MASK_CONFIG],
            text_fields=["log", "message"],
        )

        handler = self._build_handler()
        large_body = '{"player":{"id":"' + "x" * 70000 + '"}}'
        result = handler._deal_query_result(
            fake_hits_nested(body=large_body, log="user action")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # fail-closed 遮罩
        self.assertEqual(logs[0]["body"], "***MASKED***")
        # text_fields 自身脱敏不因 fail-closed 异常
        self.assertIn("log", logs[0])

    def test_text_fields_with_fail_closed_parse_error_no_crash(self):
        """text_fields + JSON 解析失败 + 子路径规则：不崩溃，body 被遮罩。

        注意：仅当字符串呈 object 形态（以 { 开头且以 } 结尾）但 JSON 非法时
        才会触发 fail-closed；若形态不符（如 "{bad json]"）则按普通标量处理。
        """
        self._put_config(
            field_configs=[NESTED_MASK_CONFIG],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_hits_nested(body='{"player": bad}', log="user body is bad")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # fail-closed 遮罩（object 形态但解析失败 + 子路径规则）
        self.assertEqual(logs[0]["body"], "***MASKED***")
        # log 字段未被破坏
        self.assertEqual(logs[0]["log"], "user body is bad")


class TestExtractValueByPath(SimpleTestCase):
    """测试 _extract_value_by_path 辅助函数"""

    def test_extract_simple_path(self):
        """从普通嵌套 dict 中提取值"""
        data = {"body": {"player": {"id": "12345"}}}
        result = _extract_value_by_path(data, "body.player.id")
        self.assertEqual(result, "12345")

    def test_extract_top_level(self):
        """提取顶层标量字段"""
        data = {"message": "hello"}
        result = _extract_value_by_path(data, "message")
        self.assertEqual(result, "hello")

    def test_extract_json_string(self):
        """从 JSON 字符串中提取子路径值"""
        data = {"body": '{"player":{"id":"12345"}}'}
        result = _extract_value_by_path(data, "body.player.id")
        self.assertEqual(result, "12345")

    def test_extract_nested_json_string(self):
        """从多层 JSON 字符串嵌套中提取值"""
        data = {"body": '{"auth_info":"{\\"bk_token\\":\\"secret\\"}"}'}
        result = _extract_value_by_path(data, "body.auth_info.bk_token")
        self.assertEqual(result, "secret")

    def test_extract_non_existent_path(self):
        """路径不存在时返回 None"""
        data = {"body": {"player": {"id": "12345"}}}
        result = _extract_value_by_path(data, "body.player.name")
        self.assertIsNone(result)

    def test_extract_from_list_value(self):
        """路径指向数组时返回数组"""
        data = {"body": {"players": [{"id": "1"}]}}
        result = _extract_value_by_path(data, "body.players")
        self.assertEqual(result, [{"id": "1"}])

    def test_extract_bad_json_returns_none(self):
        """无效 JSON 字符串返回 None"""
        data = {"body": "{bad json}"}
        result = _extract_value_by_path(data, "body.player.id")
        self.assertIsNone(result)
