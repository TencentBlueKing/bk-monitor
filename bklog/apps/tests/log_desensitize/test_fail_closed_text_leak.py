"""
超限 JSON 触发 fail-closed 时，原文字段被展开导致遮罩跳过的验证。

测试策略：
  - 真实 DB 记录：LogIndexSet / LogIndexSetData / DesensitizeConfig / DesensitizeFieldConfig
  - UnifyQueryHandler 完整构造函数
  - 直接调用 handler._log_desensitize(log) 验证返回结果
  - 仅 mock 外部依赖：请求上下文 / FeatureToggle / CMDB
"""

import copy
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_desensitize.utils import _MASKED_VALUE
from apps.log_search.models import LogIndexSet, LogIndexSetData
from apps.log_unifyquery.handler.base import UnifyQueryHandler

SPACE_UID = "bkcc__2"
INDEX_SET_ID = 1002

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

# body.player.id + log.player.id 双子路径配置（触发 log 被展开）
DUAL_SUBPATH_MASK_CONFIG = [
    {
        "field_name": "body.player.id",
        "rule_id": 0,
        "operator": "mask_shield",
        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
        "match_pattern": ".*",
        "sort_index": 0,
    },
    {
        "field_name": "log.player.id",
        "rule_id": 0,
        "operator": "mask_shield",
        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
        "match_pattern": ".*",
        "sort_index": 0,
    },
]

# 仅 body.player.id（log 不在配置路径祖先中）
SINGLE_SUBPATH_MASK_CONFIG = [
    {
        "field_name": "body.player.id",
        "rule_id": 0,
        "operator": "mask_shield",
        "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
        "match_pattern": ".*",
        "sort_index": 0,
    },
]

MASK_CONFIG = {
    "field_name": "message",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}


class TestFailClosedTextLeak(TestCase):
    """
    通过真实 UnifyQueryHandler._log_desensitize 验证 fail-closed 原文遮罩。

    场景：body 超限触发 fail-closed → log 是 text_field 且同时是配置路径祖先
    → log 被 path_aware_expand 展开为子路径 → 修复后应整体遮罩。
    """

    def setUp(self):
        self.index_set = LogIndexSet.objects.create(
            index_set_id=INDEX_SET_ID,
            index_set_name="test-fail-closed-text-leak",
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
            result_table_id="2_bklog.test_fail_closed_text",
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
        """写入脱敏配置到 DB。"""
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
        """构造 UnifyQueryHandler，mock 仅限外部依赖。"""
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

    # ==================================================================
    # Tests
    # ==================================================================

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_fail_closed_text_field_expanded_masked(self):
        """
        核心修复验证：log 是 text_field 且同时是配置路径祖先时，
        body 超限触发 fail-closed，log 被展开为子路径后仍应整体遮罩。

        输入：
          - body = 超限 JSON 字符串（> 65536 bytes）
          - log = '{"player":{"id":"67890"},"api_key":"SK-SECRET-KEY-12345"}'
          - 配置：body.player.id + log.player.id 脱敏，text_fields=["log"]

        期望：
          - result["log"] == "***MASKED***"
          - 不含 "SK-SECRET-KEY-12345" 明文
        """
        self._put_config(field_configs=DUAL_SUBPATH_MASK_CONFIG, text_fields=["log"])

        handler = self._build_handler()

        oversized_body = '{"player":{"id":"12345"},"overflow":"' + "A" * 70000 + '"}'
        log_input = {
            "body": oversized_body,
            "log": '{"player":{"id":"67890"},"api_key":"SK-SECRET-KEY-12345"}',
        }

        result = handler._log_desensitize(log_input)

        # log 应被整体遮罩
        self.assertEqual(result["log"], _MASKED_VALUE)
        # api_key 明文不应泄漏
        self.assertNotIn("SK-SECRET-KEY-12345", str(result))

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_fail_closed_text_field_not_expanded_masked(self):
        """
        回归测试：log 是 text_field 但不是配置路径祖先（纯文本），
        body 超限触发 fail-closed，log 直接整体遮罩（原有行为不变）。

        输入：
          - body = 超限 JSON 字符串
          - log = "User login: api_key=SK-SECRET"（纯文本，非 JSON）
          - 配置：仅 body.player.id，text_fields=["log"]

        期望：
          - result["log"] == "***MASKED***"
        """
        self._put_config(field_configs=SINGLE_SUBPATH_MASK_CONFIG, text_fields=["log"])

        handler = self._build_handler()

        oversized_body = '{"player":{"id":"12345"},"overflow":"' + "A" * 70000 + '"}'
        log_input = {
            "body": oversized_body,
            "log": "User login: api_key=SK-SECRET",
        }

        result = handler._log_desensitize(log_input)

        # log 应被整体遮罩（原有行为不变）
        self.assertEqual(result["log"], _MASKED_VALUE)

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_no_fail_closed_text_replace_normal(self):
        """
        回归测试：无超限（非 fail-closed），原文字段替换逻辑正常工作。

        输入：
          - body = {"player": {"id": "12345"}}（正常 dict，不超限）
          - log = "player id is 12345"
          - 配置：body.player.id 脱敏，text_fields=["log"]

        期望：
          - result["log"] 中 "12345" 被替换为脱敏后的值 "1***5"
          - result["body"]["player"]["id"] == "1***5"
        """
        self._put_config(field_configs=SINGLE_SUBPATH_MASK_CONFIG, text_fields=["log"])

        handler = self._build_handler()

        log_input = {
            "body": {"player": {"id": "12345"}},
            "log": "player id is 12345",
        }

        result = handler._log_desensitize(log_input)

        # body.player.id 被脱敏
        self.assertEqual(result["body"]["player"]["id"], "1***5")
        # log 中 "12345" 被替换为脱敏值
        self.assertEqual(result["log"], "player id is 1***5")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_fail_closed_body_masked_log_json_preserved_no_subpath_config(self):
        """
        log 是 JSON 字符串但不在配置路径祖先中（无 log.player.id 配置），
        body 超限触发 fail-closed → log 整体遮罩（走原有 if 分支）。

        输入：
          - body = 超限 JSON 字符串
          - log = '{"player":{"id":"67890"},"api_key":"SK-SECRET"}'（JSON 但无子路径配置）
          - 配置：仅 body.player.id，text_fields=["log"]

        期望：
          - result["log"] == "***MASKED***"
        """
        self._put_config(field_configs=SINGLE_SUBPATH_MASK_CONFIG, text_fields=["log"])

        handler = self._build_handler()

        oversized_body = '{"player":{"id":"12345"},"overflow":"' + "A" * 70000 + '"}'
        log_input = {
            "body": oversized_body,
            "log": '{"player":{"id":"67890"},"api_key":"SK-SECRET"}',
        }

        result = handler._log_desensitize(log_input)

        # log 不在配置路径祖先中，作为标量保留，fail-closed 直接遮罩
        self.assertEqual(result["log"], _MASKED_VALUE)
        self.assertNotIn("SK-SECRET", str(result))
