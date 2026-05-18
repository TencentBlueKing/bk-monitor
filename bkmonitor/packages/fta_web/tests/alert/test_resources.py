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
    def test_perform_request_allows_empty_graph_panel(self, monkeypatch):
        alert_id = "17742505258462064"
        fake_alert = SimpleNamespace(event=SimpleNamespace(bk_biz_id=8))

        monkeypatch.setattr(alert_resources.AlertDocument, "get", lambda _alert_id: fake_alert)
        monkeypatch.setattr(alert_resources.AIOPSManager, "get_graph_panel", lambda _alert: None)
        monkeypatch.setattr(AlertDetailResource, "get_relation_info", lambda self, alert, length_limit=True: "recent")
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
        assert result["relation_info"] == "topo recent"


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

    def test_query_string_with_english_i18n_display_name_is_detected(self):
        request_data = {"query_string": "Handling Record ID : 17790733296960932147"}
        has_action_id, detect_result = SearchAlertResource.detect_action_id_query(request_data)
        assert has_action_id is True
        assert "17790733296960932147" in detect_result["action_ids_in_query"]

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
