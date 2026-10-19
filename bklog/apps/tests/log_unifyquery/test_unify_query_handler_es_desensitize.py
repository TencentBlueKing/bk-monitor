"""
Real-DB integration tests: UnifyQueryHandler desensitize for third-party ES
index sets.

Covers scenario_id='es' (third-party ES) with and without desensitize config
through the UnifyQueryHandler._deal_query_result path.

This is a separate file (not merged into test_unify_query_handler_desensitize.py)
to keep the existing log-scenario tests untouched.
"""

import copy
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_unifyquery.handler.base import UnifyQueryHandler

SPACE_UID = "bkcc__2"

INDEX_SET_ID = 1001

SEARCH_PARAMS = {
    "index_set_ids": [INDEX_SET_ID],
    "bk_biz_id": 2,
    "keyword": "test",
    "start_time": "2026-09-27 00:00:00",
    "end_time": "2026-09-28 00:00:00",
    "sort_list": [["dtEventTimeStamp", "desc"]],
    "size": 50,
    "search_mode": "sql",
    "is_desensitize": True,
}

MASK_CONFIG = {
    "field_name": "message",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
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

TEXT_REPLACE_CONFIG = {
    "field_name": "log",
    "rule_id": 0,
    "operator": "text_replace",
    "params": {"template_string": "[FILTERED]"},
    "match_pattern": ".*",
    "sort_index": 0,
}


def fake_unify_result(*, message="plain message"):
    """Return a result_dict shaped like a UnifyQuery response."""
    return {
        "total": 1,
        "took": 10,
        "list": [
            {
                "__index": "v2_2_bklog_test_es_20260927_0",
                "__doc_id": "abc123",
                "dtEventTimeStamp": 1727452800000,
                "message": message,
                "log": "plain log",
            }
        ],
    }


def fake_unify_result_nested(*, body="", log="plain log"):
    """Return a UnifyQuery response with nested ``body`` field (dict or JSON string)."""
    return {
        "total": 1,
        "took": 10,
        "list": [
            {
                "__index": "v2_2_bklog_test_es_20260927_0",
                "__doc_id": "abc123",
                "dtEventTimeStamp": 1727452800000,
                "message": "plain",
                "log": log,
                "body": body,
            }
        ],
    }


class TestUnifyQueryHandlerEsDesensitize(TestCase):
    """UnifyQueryHandler desensitize with scenario_id='es'."""

    def setUp(self):
        # Real model records
        self.index_set = LogIndexSet.objects.create(
            index_set_id=INDEX_SET_ID,
            index_set_name="test-es-unify-desensitize",
            space_uid=SPACE_UID,
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            time_field_type="date",
            time_field_unit="millisecond",
        )

        LogIndexSetData.objects.create(
            index_set_id=INDEX_SET_ID,
            bk_biz_id=2,
            result_table_id="2_bklog.test_es_unify_desensitize",
            apply_status="normal",
            scenario_id="es",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
        )

        self._clean()

    def tearDown(self):
        self._clean()

    def _clean(self):
        DesensitizeConfig.objects.filter(index_set_id=INDEX_SET_ID).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=INDEX_SET_ID).delete()

    def _put_config(self, field_configs, text_fields=None):
        """Create a desensitize config + field configs in DB."""
        DesensitizeConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            text_fields=text_fields or [],
        )
        for fc in field_configs:
            DesensitizeFieldConfig.objects.create(
                index_set_id=INDEX_SET_ID,
                field_name=fc["field_name"],
                rule_id=fc.get("rule_id", 0),
                operator=fc["operator"],
                params=fc.get("params", {}),
                match_pattern=fc.get("match_pattern", ""),
                sort_index=fc.get("sort_index", 0),
            )

    def _build_handler(self, params_extra=None):
        """Build UnifyQueryHandler with external dependencies mocked."""
        p = copy.deepcopy(SEARCH_PARAMS)
        if params_extra:
            p.update(params_extra)

        with (
            patch.object(UnifyQueryHandler, "init_base_dict", return_value={}),
            patch(
                "apps.log_unifyquery.handler.base.get_request",
                return_value=Mock(),
            ),
            patch(
                "apps.log_unifyquery.handler.base.get_request_username",
                return_value="test_user",
            ),
            patch(
                "apps.log_unifyquery.handler.base.get_request_external_username",
                return_value=None,
            ),
            patch(
                "apps.log_search.permission.Permission.get_auth_info",
                return_value={"bk_app_code": "bk_log", "bk_username": "test_user"},
            ),
            patch(
                "apps.log_unifyquery.handler.base.FeatureToggleObject.toggle",
                return_value=None,
            ),
            patch(
                "apps.utils.core.cache.cmdb_host.CmdbHostCache.get",
                return_value={},
            ),
        ):
            return UnifyQueryHandler(p)

    # ------------------------------------------------------------------
    # Test: ES index set with config → masked
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_es_with_config_message_desensitized(self):
        """scenario_id='es' + desensitize config: message masked."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")

    # ------------------------------------------------------------------
    # Test: ES index set without config → unchanged
    # ------------------------------------------------------------------

    def test_es_without_config_message_unchanged(self):
        """scenario_id='es' + NO config: message unchanged."""
        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result(message="something secret")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "something secret")

    # ------------------------------------------------------------------
    # Test: ES index set, is_desensitize=False → original (whitelisted)
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_es_is_desensitize_false_skips_desensitize(self):
        """is_desensitize=False with whitelisted caller: no masking."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"is_desensitize": False})
        result = handler._deal_query_result(
            fake_unify_result(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: original_search=True → original text
    # ------------------------------------------------------------------

    def test_es_original_search_short_circuits_desensitize(self):
        """original_search=True returns original even with config."""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler({"original_search": True})
        result = handler._deal_query_result(
            fake_unify_result(message="Hello World1234")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Hello World1234")

    # ------------------------------------------------------------------
    # Test: _init_desensitize returns expected bool
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_es_init_desensitize_default_true(self):
        """Default is_desensitize is True for ES index set."""
        handler = self._build_handler()
        self.assertIsInstance(handler.is_desensitize, bool)
        self.assertTrue(handler.is_desensitize)

    def test_es_init_desensitize_original_search_false(self):
        """original_search=True makes is_desensitize=False."""
        handler = self._build_handler({"original_search": True})
        self.assertFalse(handler.is_desensitize)

    # ==================================================================
    # Tests for #1010158081138539921: flattened / JSON string subpath
    # ==================================================================

    def test_flattened_object_subpath_desensitized(self):
        """flattened 嵌套 object 子路径脱敏生效"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        log = {"body": {"player": {"id": "12345"}}}
        desensitized = handler._log_desensitize(log)

        self.assertIsInstance(desensitized["body"], dict)
        self.assertEqual(desensitized["body"]["player"]["id"], "1***5")

    def test_json_string_subpath_desensitized(self):
        """JSON 字符串子路径脱敏生效，且结果仍为字符串"""
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
        """通过 _deal_query_result 完整链路验证 flattened 子路径脱敏"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result_nested(body={"player": {"id": "12345"}})
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], dict)
        self.assertEqual(logs[0]["body"]["player"]["id"], "1***5")

    def test_json_string_subpath_via_deal_query_result(self):
        """通过 _deal_query_result 完整链路验证 JSON 字符串子路径脱敏"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result_nested(body='{"player":{"id":"12345"},"server":{"ip":"10.0.0.1"}}')
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")
        self.assertEqual(parsed["server"]["ip"], "10.0.0.1")

    def test_text_fields_with_subpath_desensitize(self):
        """text_fields 原文替换 + 子路径脱敏同时生效"""
        self._put_config(
            field_configs=[
                NESTED_MASK_CONFIG,
                TEXT_REPLACE_CONFIG,
            ],
            text_fields=["log"],
        )

        handler = self._build_handler()
        log = {
            "body": {"player": {"id": "12345"}},
            "log": "user id is 12345",
        }
        desensitized = handler._log_desensitize(log)

        # 子路径脱敏生效
        self.assertIsInstance(desensitized["body"], dict)
        self.assertEqual(desensitized["body"]["player"]["id"], "1***5")
        # text_fields 自身脱敏生效（text_replace 整体替换）
        self.assertEqual(desensitized["log"], "[FILTERED]")

    def test_text_fields_with_subpath_via_deal_query_result(self):
        """通过完整链路验证 text_fields + 子路径脱敏同时生效"""
        self._put_config(
            field_configs=[
                NESTED_MASK_CONFIG,
                TEXT_REPLACE_CONFIG,
            ],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = handler._deal_query_result(
            fake_unify_result_nested(body={"player": {"id": "12345"}}, log="user id is 12345")
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        self.assertIsInstance(logs[0]["body"], dict)
        self.assertEqual(logs[0]["body"]["player"]["id"], "1***5")
        self.assertEqual(logs[0]["log"], "[FILTERED]")

    def test_no_config_preserves_original_structure(self):
        """无脱敏配置时，嵌套结构保持不变"""
        handler = self._build_handler()
        log = {"body": {"player": {"id": "12345"}}}
        desensitized = handler._log_desensitize(log)

        self.assertIsInstance(desensitized["body"], dict)
        self.assertEqual(desensitized["body"]["player"]["id"], "12345")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_consistency_with_search_handler(self):
        """同一输入在 UnifyQueryHandler 和 SearchHandler 中得到同一脱敏结果"""
        from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler

        # 配置写入 DB，两个 handler 共用
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        # UnifyQueryHandler
        unify_handler = self._build_handler()
        log = {"body": '{"player":{"id":"12345"}}'}
        unify_result = unify_handler._log_desensitize(log)

        # SearchHandler（使用同一 index_set_id 和 DB 配置）

        sd = {
            "bk_biz_id": 2,
            "keyword": "test",
            "start_time": "2026-09-27 00:00:00",
            "end_time": "2026-09-28 00:00:00",
            "sort_list": [],
            "size": 50,
        }
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
            search_handler = SearchHandler(
                index_set_id=INDEX_SET_ID,
                search_dict=sd,
                pre_check_enable=False,
            )

        search_result = search_handler._log_desensitize(log)

        # 两个 handler 对同一 JSON 字符串输入应得到相同结果
        unify_parsed = json.loads(unify_result["body"])
        search_parsed = json.loads(search_result["body"])
        self.assertEqual(unify_parsed["player"]["id"], search_parsed["player"]["id"])
        self.assertEqual(unify_parsed["player"]["id"], "1***5")
