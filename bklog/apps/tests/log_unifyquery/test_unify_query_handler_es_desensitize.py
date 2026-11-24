"""
Real-DB integration tests: UnifyQueryHandler desensitize for third-party ES
index sets.

Covers scenario_id='es' (third-party ES) with and without desensitize config
through the UnifyQueryHandler._deal_query_result path.

This is a separate file (not merged into test_unify_query_handler_desensitize.py)
to keep the existing log-scenario tests untouched.

CmdbHostCache.get is patched at class level: _deal_query_result calls it after
the handler has been constructed, so a patch limited to _build_handler would
not prevent a real Redis connection.
"""

import copy
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


# ---- 嵌套 flattened / JSON 父字段 + 原文同步 ----------------------------------

IP_PATTERN = r"\d{1,3}(?:\.\d{1,3}){3}"

# 用户实际数据：字段值为 JSON 字符串，location 的 key 顺序与原文不同
CLIENT_JSON = (
    '{"ip":"10.20.30.40","port":12345,"user_agent":"user-agent-test0/1.2.3",'
    '"location":{"city":"北京市","country":"CN","district":"海淀区","province":"北京市"}}'
)
LOG_TEXT = (
    'request done {"client":{"ip":"10.20.30.40","port":12345,"user_agent":"user-agent-test0/1.2.3",'
    '"location":{"country":"CN","province":"北京市","city":"北京市","district":"海淀区"}}} status=200'
)
LOG_TEXT_MASKED = LOG_TEXT.replace("10.20.30.40", "[IP]")


def ip_replace_config(field_name, match_pattern=IP_PATTERN, template="[IP]"):
    """IP 正则替换配置；match_pattern 为空时为整字段规则。"""
    return {
        "field_name": field_name,
        "rule_id": 0,
        "operator": "text_replace",
        "params": {"template_string": template},
        "match_pattern": match_pattern,
        "sort_index": 0,
    }


def fake_unify_result_record(record):
    """Return a UnifyQuery response with a single record (UQ 返回的嵌套对象已展开为点号 key)."""
    base = {"__index": "v2_2_bklog_test_es_20260927_0", "__doc_id": "abc123", "dtEventTimeStamp": 1727452800000}
    base.update(record)
    return {"total": 1, "took": 10, "list": [base]}


def empty_cmdb_host_info(*args, **kwargs):
    """Return a fresh empty CMDB host info mapping for tests."""
    return {}


@patch("apps.utils.core.cache.cmdb_host.CmdbHostCache.get", empty_cmdb_host_info)
class TestUnifyQueryHandlerEsDesensitize(TestCase):
    """UnifyQueryHandler desensitize with scenario_id='es'."""

    # FeatureToggleObject.toggle 的返回值，None 表示未配置特权白名单
    feature_toggle = None

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
                return_value=self.feature_toggle,
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

    # ------------------------------------------------------------------
    # 嵌套 flattened / JSON 父字段规则 + 原文字段同步（与 SearchHandler 用例预期一致）
    # ------------------------------------------------------------------

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_nested_object_parent_rule_desensitized_and_synced(self):
        """父字段值为对象：子字段命中父字段规则，原文同步命中片段。"""
        self._put_config(field_configs=[ip_replace_config("__ext_json.http.client")], text_fields=["log"])
        handler = self._build_handler()
        record = {
            "__ext_json.http.client.ip": "10.20.30.40",
            "__ext_json.http.client.port": 12345,
            "log": LOG_TEXT,
        }

        log = handler._deal_query_result(fake_unify_result_record(record))["list"][0]

        self.assertEqual(log["__ext_json"], {"http": {"client": {"ip": "[IP]", "port": "12345"}}})
        self.assertEqual(log["log"], LOG_TEXT_MASKED)

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_nested_json_string_key_order_differs_synced(self):
        """父字段值为 JSON 字符串且 key 顺序与原文不同：字段与原文均脱敏。"""
        self._put_config(field_configs=[ip_replace_config("__ext_json.http.client")], text_fields=["log"])
        handler = self._build_handler()
        record = {"__ext_json.http.client": CLIENT_JSON, "log": LOG_TEXT}

        log = handler._deal_query_result(fake_unify_result_record(record))["list"][0]

        self.assertEqual(log["__ext_json"], {"http": {"client": CLIENT_JSON.replace("10.20.30.40", "[IP]")}})
        self.assertEqual(log["log"], LOG_TEXT_MASKED)

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_top_level_field_text_sync_no_regression(self):
        """普通顶层字段 + 原文同步行为不变。"""
        self._put_config(field_configs=[ip_replace_config("serverIp")], text_fields=["log"])
        handler = self._build_handler()

        log = handler._deal_query_result(
            fake_unify_result_record({"serverIp": "0.1.0.1", "log": "from 0.1.0.1 ok"})
        )["list"][0]

        self.assertEqual(log["serverIp"], "[IP]")
        self.assertEqual(log["log"], "from [IP] ok")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_whole_rule_partial_leaves_fail_closed(self):
        """整字段规则 + JSON 叶子只有部分出现在原文中：原文整体遮罩。"""
        self._put_config(
            field_configs=[ip_replace_config("__ext_json.http.client", match_pattern="", template="[CLIENT]")],
            text_fields=["log"],
        )
        handler = self._build_handler()
        record = {"__ext_json.http.client": '{"ip":"10.20.30.40","token":"abc123"}', "log": "client ip 10.20.30.40"}

        log = handler._deal_query_result(fake_unify_result_record(record))["list"][0]

        self.assertEqual(log["__ext_json"], {"http": {"client": "[CLIENT]"}})
        self.assertEqual(log["log"], "***MASKED***")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_privileged_user_desensitize_disabled(self):
        """特权白名单用户关闭检索脱敏（保持既有行为）。"""
        self._put_config(field_configs=[MASK_CONFIG])
        self.feature_toggle = Mock(feature_config={"user_white_list": {"2": ["test_user"]}})
        handler = self._build_handler()

        self.assertFalse(handler.is_desensitize)
        log = handler._deal_query_result(fake_unify_result(message="Hello World1234"))["list"][0]
        self.assertEqual(log["message"], "Hello World1234")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_no_text_fields_keeps_nested_structure(self):
        """未配置原文字段：点号字段脱敏后返回结构仍为嵌套对象。"""
        self._put_config(field_configs=[ip_replace_config("__ext_json.http.client")])
        handler = self._build_handler()
        record = {
            "__ext_json.http.client.ip": "10.20.30.40",
            "__ext_json.http.client.port": 12345,
            "log": LOG_TEXT,
        }

        log = handler._deal_query_result(fake_unify_result_record(record))["list"][0]

        self.assertEqual(log["__ext_json"], {"http": {"client": {"ip": "[IP]", "port": "12345"}}})
        self.assertNotIn("__ext_json.http.client.ip", log)
        # 未配置原文字段，log 不做原文同步
        self.assertEqual(log["log"], LOG_TEXT)

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_conflict_log_still_returned(self):
        """日志同时存在标量键与前缀子路径：入口折叠降级，不中断检索。"""
        self._put_config(field_configs=[ip_replace_config("a.b")])
        handler = self._build_handler()
        record = {"a": "10.20.30.40", "a.b": "10.20.30.41"}

        log = handler._deal_query_result(fake_unify_result_record(record))["list"][0]

        self.assertEqual(log["a"], "10.20.30.40")
        self.assertEqual(log["a.b"], "[IP]")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_export_rows_without_export_fields_are_nested(self):
        """未配置 export_fields 时，导出行为脱敏后的嵌套结构（导出契约）。"""
        self._put_config(field_configs=[ip_replace_config("__ext_json.http.client")])
        handler = self._build_handler()
        record = {"__ext_json.http.client.ip": "10.20.30.40", "log": LOG_TEXT}

        rows = handler.project_export_rows(fake_unify_result_record(record))

        self.assertEqual(rows[0]["__ext_json"], {"http": {"client": {"ip": "[IP]"}}})
        self.assertNotIn("__ext_json.http.client.ip", rows[0])
