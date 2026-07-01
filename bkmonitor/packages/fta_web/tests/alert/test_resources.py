import json
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from fta_web.alert import resources as alert_resources
from fta_web.alert.resources import AlertDetailResource, AlertTopNResource, SearchAlertResource


class TestAlertTopNResource:
    def test_request_serializer_rejects_too_many_nested_fields(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"tags.field_{index}" for index in range(21)],
                "size": 10,
            }
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_request_serializer_allows_nested_fields_within_limit(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"tags.field_{index}" for index in range(20)],
                "size": 10,
            }
        )

        serializer.is_valid(raise_exception=True)
        assert len(serializer.validated_data["fields"]) == 20

    def test_request_serializer_rejects_prefixed_nested_fields(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"-tags.field_{index}" for index in range(21)],
                "size": 10,
            }
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)


class TestAlertDetailResource:
    @pytest.mark.parametrize(
        ("relation_info", "expected_relation_info", "expected_relation_data"),
        [
            ("recent", "topo recent", None),
            ('{"logText": "error"}', None, {"logText": "error", "topo_info": "topo"}),
        ],
    )
    def test_perform_request_allows_empty_graph_panel(
        self, monkeypatch, relation_info, expected_relation_info, expected_relation_data
    ):
        alert_id = "17742505258462064"
        fake_alert = SimpleNamespace(event=SimpleNamespace(bk_biz_id=8))

        monkeypatch.setattr(alert_resources.AlertDocument, "get", lambda _alert_id: fake_alert)
        monkeypatch.setattr(alert_resources.AIOPSManager, "get_graph_panel", lambda _alert: None)
        monkeypatch.setattr(
            AlertDetailResource, "get_relation_info", lambda self, alert, length_limit=True: relation_info
        )
        monkeypatch.setattr(
            alert_resources.AlertQueryHandler,
            "clean_document",
            lambda alert: {"plugin_id": "test_plugin", "dimensions": []},
        )
        monkeypatch.setattr(
            alert_resources.PluginTranslator,
            "translate",
            lambda self, plugin_ids: {"test_plugin": "Test Plugin"},
        )
        monkeypatch.setattr(
            alert_resources,
            "resource",
            SimpleNamespace(
                alert=SimpleNamespace(
                    alert_related_info=lambda ids=None, alerts=None: {alert_id: {"topo_info": "topo"}}
                )
            ),
        )

        result = AlertDetailResource().perform_request({"id": alert_id, "bk_biz_id": 8})

        assert result["graph_panel"] is None
        assert result["plugin_display_name"] == "Test Plugin"
        if expected_relation_data is None:
            assert result["relation_info"] == expected_relation_info
        else:
            assert json.loads(result["relation_info"]) == expected_relation_data


class TestSearchAlertResourceDetectActionIdQuery:
    """detect_action_id_query 需同时识别 query_string 内的英文 action_id 与中英文 i18n 显示名。

    背景：前端从企微通知点击告警链接时实际发送英文字段名 action_id，原 regex 仅匹配中文
    "处理记录ID"，导致 adjust_time_range_for_action_id 不触发、时间窗未扩展、长生命周期
    告警查不到（TAPD #1010158081134388517）。
    """

    def test_query_string_with_english_action_id_is_detected(self):
        request_data = {"query_string": "action_id : 17790733296960932147"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert "17790733296960932147" in detect_result["action_ids_in_query"]

    def test_query_string_with_chinese_display_name_is_detected(self):
        request_data = {"query_string": "处理记录ID : 17790733296960932147"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert "17790733296960932147" in detect_result["action_ids_in_query"]

    def test_query_string_with_english_i18n_display_name_is_not_detected(self):
        """英文 i18n 显示名 "Handling Record ID" 含空格，luqum parser 不接受这种字段名
        （会被切碎为 UnknownOperation + SearchField('ID', ...)），下游 Path B 永远不会
        命中 action_id 白名单。因此 Path A 也不应识别它——否则会触发时间窗扩展但下游
        改写失败，形成"看似支持实际无效"的死代码（参见 PR review P1）。
        """
        request_data = {"query_string": "Handling Record ID : 17790733296960932147"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is False
        assert detect_result["action_ids_in_query"] == []

    def test_query_string_with_unrelated_field_is_not_detected(self):
        request_data = {"query_string": "alert_name : foo"}
        has_action_id, _ = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is False

    def test_action_id_in_conditions_still_detected_after_regex_change(self):
        request_data = {
            "query_string": "",
            "conditions": [{"key": "action_id", "value": ["17790733296960932147"]}],
        }
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert "17790733296960932147" in detect_result["action_ids_in_conditions"]

    def test_parent_action_id_not_falsely_detected(self):
        """regex 必须用负向 lookbehind，避免合法字段 parent_action_id / alert_action_id 被误识别为 action_id"""
        request_data = {"query_string": "parent_action_id : 999"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is False
        assert detect_result["action_ids_in_query"] == []

    def test_multiple_action_ids_in_query_string_collected(self):
        request_data = {"query_string": "action_id : 17790733296960932147 OR action_id : 17790733296960932148"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert set(detect_result["action_ids_in_query"]) == {
            "17790733296960932147",
            "17790733296960932148",
        }

    def test_action_id_combined_with_other_fields_in_query_string(self):
        request_data = {"query_string": "alert_name : foo AND action_id : 12345"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert "12345" in detect_result["action_ids_in_query"]

    def test_action_id_with_scalar_condition_value_handled(self):
        """conditions.value 可以是标量（非 list），需走 L1605 的 else 分支正确收集"""
        request_data = {
            "query_string": "",
            "conditions": [{"key": "action_id", "value": "17790733296960932147"}],
        }
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert "17790733296960932147" in detect_result["action_ids_in_conditions"]

    def test_quoted_value_not_supported_current_behavior(self):
        """当前不支持 Lucene 引号包裹值形式 'action_id : "123"'。
        前端实测裸值发送，不支持也不影响业务。本测试锁定当前行为，
        若未来需要支持引号形式，扩 regex 时此测试应同步更新。
        """
        request_data = {"query_string": 'action_id : "17790733296960932147"'}
        has_action_id, _ = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is False


class TestAlertQueryTransformerProcessActionId:
    """端到端验证：Path A (detect_action_id_query) + Path B (AlertQueryTransformer.transform_query_string)
    必须对 action_id 识别口径完全对称——前者识别后扩时间窗，后者识别后改写 query_string 为 id 查询。
    任何一方识别另一方不识别，都会导致用户看到"查不到告警"或语义异常。

    这一组测试填补 PR review 发现的盲点：原 detect_action_id_query 单元测试只覆盖 Path A regex，
    没验证 Path B 的 luqum AST 改写是否真的命中。
    """

    @staticmethod
    def _transform(query_string: str) -> str:
        from fta_web.alert.handlers.alert import AlertQueryTransformer

        # transform_query_string 内部调用 luqum parser + transformer，最终输出改写后的字符串
        return AlertQueryTransformer.transform_query_string(query_string)

    def test_english_action_id_is_rewritten_to_id_query(self, monkeypatch):
        """action_id : X → 经过 Path B 改写为 id:( <alert_id> )"""
        from fta_web.alert.handlers import alert as alert_handler

        # mock get_alert_ids_by_action_id 避免依赖 ES
        monkeypatch.setattr(
            alert_handler,
            "get_alert_ids_by_action_id",
            lambda action_ids: (["1776330921292201387"], {action_ids[0]: ["1776330921292201387"]}),
        )

        result = self._transform("action_id : 17790733296960932147")

        # 改写后应不再含原 action_id 字段名，且应包含解析出的 alert_id
        assert "action_id" not in result
        assert "1776330921292201387" in result

    def test_chinese_display_name_is_rewritten_to_id_query(self, monkeypatch):
        """处理记录ID : X → 同样被 Path B 改写"""
        from fta_web.alert.handlers import alert as alert_handler

        monkeypatch.setattr(
            alert_handler,
            "get_alert_ids_by_action_id",
            lambda action_ids: (["1776330921292201387"], {action_ids[0]: ["1776330921292201387"]}),
        )

        result = self._transform("处理记录ID : 17790733296960932147")

        assert "处理记录ID" not in result
        assert "1776330921292201387" in result

    def test_english_i18n_display_name_is_not_rewritten(self, monkeypatch):
        """ "Handling Record ID : X" 因含空格无法被 luqum 解析为单一 SearchField，
        因此 Path B 不会改写它。验证不会触发 get_alert_ids_by_action_id 调用，
        且 ID 字段值保留（说明未经 action_id 路径改写）。
        这与 Path A 的 detect_action_id_query 现在也不识别它的语义保持一致。
        """
        from fta_web.alert.handlers import alert as alert_handler

        called = {"count": 0}

        def fake_get_alert_ids(action_ids):
            called["count"] += 1
            return ([], {})

        monkeypatch.setattr(alert_handler, "get_alert_ids_by_action_id", fake_get_alert_ids)

        result = self._transform("Handling Record ID : 12345")

        # 未触发 action_id 反查
        assert called["count"] == 0
        # ID 仍以原始值保留，未被替换为 alert id
        assert "12345" in result

    def test_parent_action_id_is_not_rewritten(self, monkeypatch):
        """parent_action_id 是合法的另一字段（handlers/action.py），不应被误识别为 action_id。"""
        from fta_web.alert.handlers import alert as alert_handler

        called = {"count": 0}

        def fake_get_alert_ids(action_ids):
            called["count"] += 1
            return ([], {})

        monkeypatch.setattr(alert_handler, "get_alert_ids_by_action_id", fake_get_alert_ids)

        # parent_action_id 不是 AlertQueryTransformer.query_fields 注册的字段，luqum 会解析成
        # SearchField('parent_action_id', Word('999'))，Path B 的 _process_action_id 严格判断
        # search_field_origin_name in 白名单，不会命中
        result = self._transform("parent_action_id : 999")

        assert called["count"] == 0
        assert "999" in result
