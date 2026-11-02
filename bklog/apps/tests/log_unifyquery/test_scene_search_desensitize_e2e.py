# -*- coding: utf-8 -*-
"""
端到端脱敏测试：SceneUnifyQueryHandler 完整链路。

覆盖场景（对应 SearchHandler / UnifyQueryHandler base 已有覆盖的同款测试）：
  1. 正常脱敏生效
  2. JSON 字符串子路径脱敏
  3. text_fields + 子路径同时生效
  4. 无配置时结构保持（不平铺）
  5. _log_desensitize 单元路径
  6. 异常隔离（复用 test_scene_search_desensitize.py）

测试策略：
  - 真实 DB 记录：LogIndexSet / LogIndexSetData / IndexSetTag /
    DesensitizeConfig / DesensitizeFieldConfig
  - SceneUnifyQueryHandler(params) 完整构造函数
  - _init_scene_desensitize 走真实 DB 查询（从 result_table_id 映射到
    index_set_id 再到 config 的完整回路）
  - 仅 mock 网络/外部依赖：query_ts_raw / _enhance / 请求上下文

遵循 AGENTS.md：
  - 使用真实 model 记录，不 mock QuerySet
  - 需要数据库，使用 TestCase
  - 断言精确控制字段值、类型、数量
"""
import json
from contextlib import ExitStack
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from apps.log_desensitize.models import DesensitizeConfig, DesensitizeFieldConfig
from apps.log_search.constants import IndexSetDataType
from apps.log_search.models import IndexSetTag, LogIndexSet, LogIndexSetData
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

SPACE_UID = "bkcc__2"
SCENE_TAG = "k8s"
CLUSTER_TAG = "BCS-SCENE-CI-001"
INDEX_SET_ID = 2001

SEARCH_PARAMS = {
    "space_uid": SPACE_UID,
    "table_id_conditions": [
        [
            {"field_name": "scene", "value": [SCENE_TAG], "op": "eq"},
            {"field_name": "cluster_id", "value": [CLUSTER_TAG], "op": "eq"},
        ]
    ],
    "keyword": "test",
    "start_time": "2026-09-27 00:00:00",
    "end_time": "2026-09-28 00:00:00",
    "sort_list": [["dtEventTimeStamp", "desc"]],
    "size": 50,
    "begin": 0,
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

RESULT_TABLE_ID = "2_bklog.scene_desensitize_rt"


def _fake_ts_raw_result(*, body="", message="plain", log="plain log", result_table=None):
    """构造伪造的 query_ts_raw 返回值，形状与真实 unify-query 响应一致。"""
    record = {
        "__index": "v2_2_bklog_test_es_20260927_0",
        "__doc_id": "scene_doc_1",
        "dtEventTimeStamp": 1727452800000,
        "message": message,
        "log": log,
    }
    if body is not None:
        record["body"] = body
    if result_table is not None:
        # 真实响应中每条日志带 __result_table，用于回填 __index_set_id__
        record["__result_table"] = result_table
    return {
        "total": 1,
        "took": 10,
        "list": [record],
        # 真实 unify-query 响应中 result_table_id 是列表，逐字符迭代会破坏映射
        "result_table_id": [RESULT_TABLE_ID],
    }


class SceneUnifyQueryHandlerDesensitizeEndToEnd(TestCase):
    """SceneUnifyQueryHandler 脱敏完整链路端到端测试。"""

    @classmethod
    def setUpTestData(cls):
        # ---- 索引集与标签：让 result_table_id → index_set_id 映射可用 ----
        cls.scene_tag_id = IndexSetTag.get_tag_id(
            name="scene", value=SCENE_TAG, tag_type="scene"
        )
        cls.cluster_tag_id = IndexSetTag.get_tag_id(
            name="cluster_id", value=CLUSTER_TAG, tag_type="scene"
        )
        cls.index_set = LogIndexSet.objects.create(
            index_set_id=INDEX_SET_ID,
            index_set_name="test-scene-desensitize-e2e",
            space_uid=SPACE_UID,
            scenario_id="log",
            tag_ids=[str(cls.scene_tag_id), str(cls.cluster_tag_id)],
            is_active=True,
            # 显式声明以免模型默认值变化时静默失效
            is_group=False,
        )
        LogIndexSetData.objects.create(
            index_set_id=INDEX_SET_ID,
            bk_biz_id=2,
            result_table_id=RESULT_TABLE_ID,
            apply_status="normal",
            scenario_id="log",
            storage_cluster_id=1,
            time_field="dtEventTimeStamp",
            type=IndexSetDataType.RESULT_TABLE.value,
        )

    def setUp(self):
        self._clean_configs()

    def tearDown(self):
        self._clean_configs()

    def _clean_configs(self):
        DesensitizeConfig.objects.filter(index_set_id=INDEX_SET_ID).delete()
        DesensitizeFieldConfig.objects.filter(index_set_id=INDEX_SET_ID).delete()

    def _put_config(self, field_configs, text_fields=None):
        """写入脱敏配置到 DB（真实模型记录）。"""
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

    def _build_handler(self, extra_params=None, search_params=None):
        """
        构造 SceneUnifyQueryHandler（仅限构造期需要的 mock）。

        ``query_ts_raw`` 和 ``IndexSetHandler.get_all_related_space_uids``
        调用 search() 时才需要，由 ``_run_search`` 统一注入。
        """
        params = {**(search_params or SEARCH_PARAMS), **(extra_params or {})}
        with ExitStack() as stack:
            stack.enter_context(patch.object(SceneUnifyQueryHandler, "_enhance"))
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.scene_search."
                    "get_request_external_username",
                    return_value="",
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.scene_search.get_request_username",
                    return_value="admin",
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.scene_search.get_local_param",
                    return_value="UTC",
                )
            )
            # _init_desensitize 中需要的
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.base.get_request",
                    return_value=Mock(),
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.base.get_request_username",
                    return_value="admin",
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.base.get_request_external_username",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.base.FeatureToggleObject.toggle",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_search.permission.Permission.get_auth_info",
                    return_value={
                        "bk_app_code": "bk_log",
                        "bk_username": "test_user",
                    },
                )
            )
            handler = SceneUnifyQueryHandler(params)
        return handler

    def _run_search(self, handler, fake_raw_result):
        """
        以 handler 执行 search()，注入运行时 mock。

        IndexSetHandler.get_all_related_space_uids 调用 SpaceApi（外部 API），
        未 mock 时会抛异常被 _deal_query_result 消化，但导致
        __index_set_id__ 未被真正赋值。
        """
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(handler, "query_ts_raw", return_value=fake_raw_result)
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.scene_search.IndexSetHandler"
                    ".get_all_related_space_uids",
                    return_value=[SPACE_UID],
                )
            )
            return handler.search()

    # ==================================================================
    # Tests — 每条独立 mock query_ts_raw
    # ==================================================================

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_desensitize_normal(self):
        """完整链路：message 字段脱敏生效 + __index_set_id__ 回填正确。"""
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        result = self._run_search(
            handler,
            _fake_ts_raw_result(
                message="Hello World1234",
                result_table=RESULT_TABLE_ID,
            ),
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # mask_shield(2, 2) on 15-char string
        self.assertEqual(logs[0]["message"], "He***********34")
        # __index_set_id__ 由 _get_result_table_index_set_map 正确回填
        self.assertEqual(logs[0]["__index_set_id__"], INDEX_SET_ID)

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_json_subpath_desensitize(self):
        """完整链路：JSON 字符串子路径 body.player.id 脱敏生效。"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        result = self._run_search(
            handler,
            _fake_ts_raw_result(body='{"player":{"id":"12345"}}'),
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # 结果仍是 JSON 字符串
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_text_fields_with_subpath(self):
        """完整链路：text_fields 原文替换 + 子路径脱敏同时生效。

        log 字段的值使用纯文本而非 JSON 字符串，避免被误解为
        path_aware_expand 的容器类型（实际因 log 属于 text_fields 而走
        text_fields_field_configs 路径，不会被尝试展开，但纯文本让阅读者
        无需追踪配置路由即可确信无干扰）。
        """
        self._put_config(
            field_configs=[NESTED_MASK_CONFIG, TEXT_REPLACE_CONFIG],
            text_fields=["log"],
        )

        handler = self._build_handler()
        result = self._run_search(
            handler,
            _fake_ts_raw_result(
                body='{"player":{"id":"12345"}}',
                message="plain",
                log="raw text line",
            ),
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # body 子路径脱敏
        self.assertIsInstance(logs[0]["body"], str)
        parsed_body = json.loads(logs[0]["body"])
        self.assertEqual(parsed_body["player"]["id"], "1***5")
        # log 原文字段被 text_replace 替换
        self.assertEqual(logs[0]["log"], "[FILTERED]")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_no_config_preserves_structure(self):
        """无脱敏配置时：原值不变，结构保持嵌套（不平铺）。

        注意：_deal_query_result 首先调用 merge_nested_data(log)，该函数只
        拆分带 ``.`` 的 dotted key（如 {"a.b": 1} → {"a": {"b": 1}}），
        对 JSON 字符串值原样保留。此测试隐含依赖该行为。
        """
        handler = self._build_handler(
            search_params={**SEARCH_PARAMS, "is_desensitize": False}
        )
        result = self._run_search(
            handler,
            _fake_ts_raw_result(body='{"player":{"id":"12345"}}'),
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # body 不应被平铺
        self.assertIsInstance(logs[0]["body"], str)
        parsed = json.loads(logs[0]["body"])
        self.assertEqual(parsed["player"]["id"], "12345")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_log_desensitize_unit(self):
        """_log_desensitize 单元路径：直接调用并断言子路径脱敏。"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        # 手动触发 config 加载，模拟 _init_scene_desensitize 调用后的状态
        # （search 中 query_ts_raw 之后自动调用，但单元路径不经过 search）
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        log_entry = {"body": '{"player":{"id":"12345"}}'}
        desensitized = handler._log_desensitize(log_entry)

        self.assertIsInstance(desensitized["body"], str)
        parsed = json.loads(desensitized["body"])
        self.assertEqual(parsed["player"]["id"], "1***5")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_deep_dict_subtree_preserved(self):
        """
        场景化检索链路：result_table_id → index_set_id → config 懒加载 →
        _deal_query_result → _log_desensitize。深度 > max_depth=10 的子树
        必须完整保留（作为 dict 原子值），不得从响应中消失。
        """
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        # 构造 depth=15 的嵌套 dict
        inner = {}
        current = inner
        for i in range(15):
            current["level"] = {}
            current["leaf"] = f"value_{i}"
            current = current["level"]

        result = self._run_search(
            handler,
            _fake_ts_raw_result(body=inner, message="Hello World1234"),
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # 浅层字段正常脱敏
        self.assertEqual(logs[0]["message"], "He***********34")
        # body 仍是 dict，深度<=10 的 leaf 存在
        self.assertIsInstance(logs[0]["body"], dict)
        deep_level = logs[0]["body"]
        for d in range(12):
            self.assertIsInstance(
                deep_level, dict,
                "At restored depth {}, expected dict but got {}".format(d, type(deep_level)),
            )
            self.assertIn("leaf", deep_level,
                          "At restored depth {}, expected 'leaf' key".format(d))
            deep_level = deep_level.get("level", {})

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_full_multi_layer_json_string_nesting(self):
        """多层 JSON 字符串嵌套通过完整 search() 链路后类型不被破坏。

        body 是 JSON 字符串，其内部 inner 也是 JSON 字符串；配置
        body.inner.secret。脱敏后 body 仍是 JSON 字符串，inner 仍是
        JSON 字符串（不是 dict），secret 被脱敏。
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
        result = self._run_search(
            handler,
            _fake_ts_raw_result(
                body='{"outer":"hello","inner":"{\\"secret\\":\\"99999\\"}"}',
            ),
        )

        logs = result["list"]
        self.assertEqual(len(logs), 1)
        # body 仍为 JSON 字符串
        self.assertIsInstance(logs[0]["body"], str)
        parsed_body = json.loads(logs[0]["body"])
        self.assertEqual(parsed_body["outer"], "hello")
        # inner 仍为 JSON 字符串（类型未被破坏）
        self.assertIsInstance(parsed_body["inner"], str)
        parsed_inner = json.loads(parsed_body["inner"])
        self.assertEqual(parsed_inner["secret"], "9***9")
