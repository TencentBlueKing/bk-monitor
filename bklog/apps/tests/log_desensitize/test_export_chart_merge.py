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
INDEX_SET_ID = 2002

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

NESTED_MASK_CONFIG = {
    "field_name": "body.player.id",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 1, "preserve_tail": 1, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}

MASK_CONFIG = {
    "field_name": "message",
    "rule_id": 0,
    "operator": "mask_shield",
    "params": {"preserve_head": 2, "preserve_tail": 2, "replace_mark": "*"},
    "match_pattern": ".*",
    "sort_index": 0,
}

RESULT_TABLE_ID = "2_bklog.scene_export_chart_rt"


def _fake_scroll_result_flattened(*, message="Hello World1234", body_player_id="12345"):
    """
    构造伪造的 query_ts_raw_with_scroll 返回值，使用 flattened 格式。

    真实 ES/unify-query 可能返回 dotted-key 格式（如 body.player.id），
    而非嵌套 dict 格式。export_chart_data 需先 merge_nested_data 才能正确脱敏。
    """
    return {
        "total": 1,
        "took": 10,
        "list": [
            {
                "__index": "v2_2_bklog_test_es_20260927_0",
                "__doc_id": "export_doc_1",
                "dtEventTimeStamp": 1727452800000,
                "message": message,
                "body.player.id": body_player_id,
                "log": "plain log content",
            }
        ],
        "result_table_id": [RESULT_TABLE_ID],
        "result_table_options": {
            RESULT_TABLE_ID: {
                "result_schema": [
                    {"field_name": "dtEventTimeStamp", "field_alias": "dtEventTimeStamp"},
                    {"field_name": "message", "field_alias": "message"},
                    {"field_name": "body.player.id", "field_alias": "body.player.id"},
                    {"field_name": "log", "field_alias": "log"},
                ]
            }
        },
        "done": True,
    }


def _fake_scroll_result_nested(*, message="Hello World1234", body_player_id="12345"):
    """
    构造伪造的 query_ts_raw_with_scroll 返回值，使用嵌套 dict 格式。

    验证嵌套格式数据在 export_chart_data 中也能正常脱敏。
    """
    return {
        "total": 1,
        "took": 10,
        "list": [
            {
                "__index": "v2_2_bklog_test_es_20260927_0",
                "__doc_id": "export_doc_1",
                "dtEventTimeStamp": 1727452800000,
                "message": message,
                "body": {"player": {"id": body_player_id}},
                "log": "plain log content",
            }
        ],
        "result_table_id": [RESULT_TABLE_ID],
        "result_table_options": {
            RESULT_TABLE_ID: {
                "result_schema": [
                    {"field_name": "dtEventTimeStamp", "field_alias": "dtEventTimeStamp"},
                    {"field_name": "message", "field_alias": "message"},
                    {"field_name": "body.player.id", "field_alias": "body.player.id"},
                    {"field_name": "log", "field_alias": "log"},
                ]
            }
        },
        "done": True,
    }


class TestExportChartDataMergeNestedData(TestCase):
    """
    验证 export_chart_data 中 merge_nested_data 预处理：

    1. flattened 格式数据经 merge 后子路径脱敏生效
    2. 嵌套格式数据脱敏行为不变（回归）
    3. merge 异常时 fail-closed 兜底
    """

    @classmethod
    def setUpTestData(cls):
        cls.scene_tag_id = IndexSetTag.get_tag_id(
            name="scene", value=SCENE_TAG, tag_type="scene"
        )
        cls.cluster_tag_id = IndexSetTag.get_tag_id(
            name="cluster_id", value=CLUSTER_TAG, tag_type="scene"
        )
        cls.index_set = LogIndexSet.objects.create(
            index_set_id=INDEX_SET_ID,
            index_set_name="test-scene-export-chart",
            space_uid=SPACE_UID,
            scenario_id="log",
            tag_ids=[str(cls.scene_tag_id), str(cls.cluster_tag_id)],
            is_active=True,
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

    def _build_handler(self, extra_params=None):
        """构造 SceneUnifyQueryHandler。"""
        params = {**(SEARCH_PARAMS or {}), **(extra_params or {})}
        with ExitStack() as stack:
            stack.enter_context(patch.object(SceneUnifyQueryHandler, "_enhance"))
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.scene_search.get_request_external_username",
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

    def _run_export_chart_data(self, handler, fake_scroll_result):
        """执行 export_chart_data，注入 mock。"""
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    handler,
                    "query_ts_raw_with_scroll",
                    return_value=fake_scroll_result,
                )
            )
            stack.enter_context(
                patch(
                    "apps.log_unifyquery.handler.scene_search.IndexSetHandler"
                    ".get_all_related_space_uids",
                    return_value=[SPACE_UID],
                )
            )
            # 收集所有 yield 的 CSV chunk
            chunks = list(handler.export_chart_data())
            return "".join(chunks)

    def _parse_csv(self, csv_text):
        """解析 CSV 文本为 list of dict。"""
        import csv
        from io import StringIO

        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        if len(rows) < 2:
            return []
        headers = rows[0]
        return [dict(zip(headers, row)) for row in rows[1:]]

    # ==================================================================
    # Tests
    # ==================================================================

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_flattened_data_desensitize_in_export_chart(self):
        """
        flattened 格式数据：export_chart_data 应先 merge_nested_data 再脱敏。

        输入 body.player.id = "12345"（flattened dotted key），
        配置 body.player.id 脱敏规则，
        期望 CSV 输出中 body.player.id 被脱敏为 "1***5"。
        """
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        # 手动初始化脱敏配置（模拟 search 中的 _init_scene_desensitize）
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        csv_output = self._run_export_chart_data(
            handler,
            _fake_scroll_result_flattened(body_player_id="12345"),
        )

        rows = self._parse_csv(csv_output)
        self.assertEqual(len(rows), 1)
        # mask_shield(1, 1) on "12345" → "1***5"
        self.assertEqual(rows[0]["body.player.id"], "1***5")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_nested_data_desensitize_in_export_chart(self):
        """
        嵌套 dict 格式数据：export_chart_data 脱敏行为不变。

        输入 body = {"player": {"id": "12345"}}（嵌套 dict），
        配置 body.player.id 脱敏规则，
        期望 CSV 输出中 body.player.id 被脱敏为 "1***5"。
        """
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        csv_output = self._run_export_chart_data(
            handler,
            _fake_scroll_result_nested(body_player_id="12345"),
        )

        rows = self._parse_csv(csv_output)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["body.player.id"], "1***5")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_no_text_fields_keeps_nested_structure(self):
        """
        场景检索主链路（_deal_query_result）：未配置原文字段时脱敏后仍返回嵌套结构。

        修复前 text_fields 为空会在 expand_nested_data 后提前返回 dotted key 形态，
        与白名单账号、非脱敏链路返回的结构不一致。
        """
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        result = handler._deal_query_result(_fake_scroll_result_nested(body_player_id="12345"))

        log = result["list"][0]
        # mask_shield(1, 1) on "12345" → "1***5"，且结构保持嵌套
        self.assertEqual(log["body"], {"player": {"id": "1***5"}})
        self.assertNotIn("body.player.id", log)

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_conflict_log_still_returned(self):
        """日志同时存在标量键与前缀子路径：场景检索入口折叠降级，不中断检索。"""
        self._put_config(field_configs=[NESTED_MASK_CONFIG])

        handler = self._build_handler()
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        result = handler._deal_query_result(
            {
                "total": 1,
                "took": 1,
                "list": [
                    {
                        "__index": "v2_2_bklog_test_es_20260927_0",
                        "__doc_id": "conflict_doc",
                        "dtEventTimeStamp": 1727452800000,
                        "body": "plain",
                        "body.player.id": "12345",
                    }
                ],
                "result_table_id": [RESULT_TABLE_ID],
                "result_table_options": {RESULT_TABLE_ID: {"result_schema": []}},
                "done": True,
            }
        )

        log = result["list"][0]
        # 冲突字段保留扁平键，标量键未被覆盖
        self.assertEqual(log["body"], "plain")
        self.assertEqual(log["body.player.id"], "1***5")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_text_fields_nested_alias_in_export_chart(self):
        """
        配置原文字段（导出阶段记录会被折叠为嵌套结构）时，nested alias 列不会变空。

        text_fields 非空时 _log_desensitize 末尾会 merge_nested_data，
        record 变为 {"body": {"player": {"id": ...}}}，
        导出需按 field_alias 的点号路径取值，否则该列为空串。
        """
        self._put_config(field_configs=[NESTED_MASK_CONFIG], text_fields=["log"])

        handler = self._build_handler()
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        csv_output = self._run_export_chart_data(
            handler,
            _fake_scroll_result_flattened(body_player_id="12345"),
        )

        rows = self._parse_csv(csv_output)
        self.assertEqual(len(rows), 1)
        # mask_shield(1, 1) on "12345" → "1***5"
        self.assertEqual(rows[0]["body.player.id"], "1***5")
        self.assertEqual(rows[0]["message"], "Hello World1234")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_message_field_desensitize_in_export_chart(self):
        """
        顶层字段脱敏：message 字段 mask_shield 正常工作。

        验证 merge_nested_data 不影响顶层字段的脱敏。
        """
        self._put_config(field_configs=[MASK_CONFIG])

        handler = self._build_handler()
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        csv_output = self._run_export_chart_data(
            handler,
            _fake_scroll_result_flattened(message="Hello World1234"),
        )

        rows = self._parse_csv(csv_output)
        self.assertEqual(len(rows), 1)
        # mask_shield(2, 2) on 15-char string → "He***********34"
        self.assertEqual(rows[0]["message"], "He***********34")

    @override_settings(ESQUERY_WHITE_LIST=["bk_log"])
    def test_no_config_preserves_original_in_export_chart(self):
        """
        无脱敏配置：export_chart_data 输出原始数据。

        验证无配置时数据不被遮罩。
        """
        handler = self._build_handler()
        handler._init_scene_desensitize([RESULT_TABLE_ID])

        csv_output = self._run_export_chart_data(
            handler,
            _fake_scroll_result_flattened(message="Hello World1234", body_player_id="12345"),
        )

        rows = self._parse_csv(csv_output)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["message"], "Hello World1234")
        self.assertEqual(rows[0]["body.player.id"], "12345")
