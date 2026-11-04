from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.models import NO_DATA_TAG_DIMENSION
from bkmonitor.utils.time_tools import utc2datetime
from fta_web.alert import resources as alert_resources
from fta_web.alert.handlers import alert_log as alert_log_module
from fta_web.alert.handlers.alert_log import AlertLogHandler
from fta_web.alert.resources import ListAlertLogResource

# 构造的测试夹具：固定日期 2026-03-15 08:00:00 UTC，后面补 9 位序列，
# 与告警 ID「前 10 位时间戳 + 序列」的格式保持一致
ALERT_CREATE_TIME = 1773561600
ALERT_ID = f"{ALERT_CREATE_TIME}000000123"


class FakeHit(SimpleNamespace):
    """模拟 ES scroll 返回的 hit：支持属性访问与 to_dict()"""

    def __init__(self, **kwargs):
        doc_id = kwargs.pop("doc_id", "doc-id")
        kwargs.setdefault("description", "")
        super().__init__(**kwargs)
        self.meta = SimpleNamespace(id=doc_id)

    def to_dict(self):
        return {key: value for key, value in self.__dict__.items() if key != "meta"}


def make_search_mock(hits=()):
    search_mock = MagicMock()
    search_mock.params.return_value = search_mock
    search_mock.filter.return_value = search_mock
    search_mock.sort.return_value = search_mock
    search_mock.scan.return_value = iter(hits)
    return search_mock


def make_handler(begin_time=ALERT_CREATE_TIME, trigger_condition=None):
    """走完整展示参数路径，构造过程不会读取告警正文"""
    return AlertLogHandler(ALERT_ID, begin_time=begin_time, trigger_condition=trigger_condition)


class TestBuildSearchObject:
    def test_narrow_index_by_alert_create_day(self, monkeypatch):
        search_patch = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(AlertLog, "search", search_patch)
        monkeypatch.setattr(alert_log_module, "time", SimpleNamespace(time=lambda: ALERT_CREATE_TIME + 2 * 86400))

        make_handler().build_search_object()

        # 夹具创建日为 2026-03-15，当前时间固定为创建后第 2 天，应逐日枚举 15/16/17
        assert search_patch.call_args.kwargs["index"] == [
            "bkfta_log_alert_20260315_read",
            "bkfta_log_alert_20260316_read",
            "bkfta_log_alert_20260317_read",
        ]

    def test_fallback_for_invalid_alert_id(self, monkeypatch):
        search_patch = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(AlertLog, "search", search_patch)

        AlertLogHandler("not-a-number", begin_time=1, trigger_condition=None).build_search_object()

        assert search_patch.call_args.kwargs == {"all_indices": True}

    def test_fallback_for_future_create_time(self, monkeypatch):
        search_patch = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(AlertLog, "search", search_patch)
        monkeypatch.setattr(alert_log_module, "time", SimpleNamespace(time=lambda: 1))

        make_handler().build_search_object()

        assert search_patch.call_args.kwargs == {"all_indices": True}

    def test_fallback_for_empty_index_list(self, monkeypatch):
        search_patch = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(AlertLog, "search", search_patch)
        monkeypatch.setattr(AlertLog, "build_index_name_by_time", MagicMock(return_value=[]))

        make_handler().build_search_object()

        assert search_patch.call_args.kwargs == {"all_indices": True}

    def test_fallback_when_candidate_index_too_many(self, monkeypatch):
        search_patch = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(AlertLog, "search", search_patch)
        monkeypatch.setattr(
            AlertLog,
            "build_index_name_by_time",
            MagicMock(
                return_value=[f"idx_{index}_read" for index in range(AlertLogHandler.MAX_SEARCH_INDEX_COUNT + 1)]
            ),
        )

        make_handler().build_search_object()

        assert search_patch.call_args.kwargs == {"all_indices": True}

    def test_keeps_candidate_index_at_limit(self, monkeypatch):
        search_patch = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(AlertLog, "search", search_patch)
        index_name = [f"idx_{index}_read" for index in range(AlertLogHandler.MAX_SEARCH_INDEX_COUNT)]
        monkeypatch.setattr(AlertLog, "build_index_name_by_time", MagicMock(return_value=index_name))

        make_handler().build_search_object()

        assert search_patch.call_args.kwargs["index"] == index_name

    def test_offset_does_not_narrow_index_upper_bound(self, monkeypatch):
        search_patch = MagicMock(return_value=make_search_mock())
        monkeypatch.setattr(AlertLog, "search", search_patch)
        monkeypatch.setattr(alert_log_module, "time", SimpleNamespace(time=lambda: ALERT_CREATE_TIME + 2 * 86400))

        make_handler().search(operate_list=[], offset=ALERT_CREATE_TIME + 86400, limit=20)

        assert search_patch.call_args.kwargs["index"][-1] == "bkfta_log_alert_20260317_read"


class TestDisplayParams:
    def test_full_params_skip_alert_document_get(self, monkeypatch):
        get_patch = MagicMock()
        monkeypatch.setattr(AlertDocument, "get", get_patch)

        handler = make_handler(begin_time=1000, trigger_condition=None)

        get_patch.assert_not_called()
        assert handler.alert is None
        assert handler.begin_time == 1000
        assert handler.trigger_condition is None

    def test_missing_trigger_condition_falls_back(self, monkeypatch):
        alert = SimpleNamespace(begin_time=2000, strategy=None, origin_alarm=None)
        get_patch = MagicMock(return_value=alert)
        monkeypatch.setattr(AlertDocument, "get", get_patch)

        handler = AlertLogHandler(ALERT_ID, begin_time=1000)

        get_patch.assert_called_once_with(ALERT_ID)
        assert handler.begin_time == 2000
        assert handler.trigger_condition is None

    def test_missing_begin_time_falls_back(self, monkeypatch):
        alert = SimpleNamespace(begin_time=2000, strategy=None, origin_alarm=None)
        get_patch = MagicMock(return_value=alert)
        monkeypatch.setattr(AlertDocument, "get", get_patch)

        handler = AlertLogHandler(ALERT_ID, trigger_condition={"type": "no_data", "continuous": 4})

        get_patch.assert_called_once_with(ALERT_ID)
        assert handler.begin_time == 2000

    def test_no_params_falls_back(self, monkeypatch):
        alert = SimpleNamespace(begin_time=2000, strategy=None, origin_alarm=None)
        get_patch = MagicMock(return_value=alert)
        monkeypatch.setattr(AlertDocument, "get", get_patch)

        AlertLogHandler(ALERT_ID)

        get_patch.assert_called_once_with(ALERT_ID)


class TestBuildTriggerCondition:
    def test_algorithm(self):
        alert = SimpleNamespace(
            strategy={
                "items": [{"algorithms": ["threshold"]}],
                "detects": [{"trigger_config": {"check_window": 5, "count": 3}}],
            },
            origin_alarm={"data": {"dimensions": []}},
        )

        assert AlertLogHandler.build_trigger_condition(alert) == {
            "type": "algorithm",
            "check_window": 5,
            "count": 3,
        }

    def test_no_data(self):
        alert = SimpleNamespace(
            strategy={
                "items": [{"algorithms": ["threshold"], "no_data_config": {"continuous": 4}}],
                "detects": [{"trigger_config": {"check_window": 5, "count": 3}}],
            },
            origin_alarm={"data": {"dimensions": [NO_DATA_TAG_DIMENSION]}},
        )

        assert AlertLogHandler.build_trigger_condition(alert) == {"type": "no_data", "continuous": 4}

    def test_empty_algorithms(self):
        alert = SimpleNamespace(strategy={"items": [{"algorithms": []}], "detects": []}, origin_alarm=None)

        assert AlertLogHandler.build_trigger_condition(alert) is None

    def test_empty_strategy(self):
        alert = SimpleNamespace(strategy=None, origin_alarm=None)

        assert AlertLogHandler.build_trigger_condition(alert) is None


class TestAddRecordCreate:
    def test_without_trigger_condition(self):
        handler = make_handler(begin_time=1000, trigger_condition=None)

        handler.handle_hit(FakeHit(op_type=AlertLog.OpType.CREATE, create_time=2000, description="告警产生"))

        record = handler.log_records[0]
        assert record["contents"] == ["告警产生"]
        assert record["source_time"] == utc2datetime(1000)
        assert record["index"] == 0

    def test_with_algorithm_condition(self):
        handler = make_handler(begin_time=1000, trigger_condition={"type": "algorithm", "check_window": 5, "count": 3})

        handler.handle_hit(FakeHit(op_type=AlertLog.OpType.CREATE, create_time=2000, description="告警产生"))

        contents = handler.log_records[0]["contents"]
        assert len(contents) == 2
        assert "5" in contents[1]
        assert "3" in contents[1]

    def test_with_no_data_condition(self):
        handler = make_handler(begin_time=1000, trigger_condition={"type": "no_data", "continuous": 4})

        handler.handle_hit(FakeHit(op_type=AlertLog.OpType.CREATE, create_time=2000, description="告警产生"))

        contents = handler.log_records[0]["contents"]
        assert len(contents) == 2
        assert "4" in contents[1]


class TestRequestSerializer:
    @staticmethod
    def validate(data):
        serializer = ListAlertLogResource.RequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def test_optional_params_absent(self):
        validated = self.validate({"id": ALERT_ID})

        assert "begin_time" not in validated
        assert "trigger_condition" not in validated

    def test_trigger_condition_null_is_kept(self):
        validated = self.validate({"id": ALERT_ID, "begin_time": 1000, "trigger_condition": None})

        assert "trigger_condition" in validated
        assert validated["trigger_condition"] is None

    def test_valid_algorithm(self):
        condition = {"type": "algorithm", "check_window": 5, "count": 3}

        validated = self.validate({"id": ALERT_ID, "begin_time": 1000, "trigger_condition": condition})

        assert validated["trigger_condition"] == condition

    def test_valid_no_data(self):
        condition = {"type": "no_data", "continuous": 4}

        validated = self.validate({"id": ALERT_ID, "begin_time": 1000, "trigger_condition": condition})

        assert validated["trigger_condition"] == condition

    @pytest.mark.parametrize("begin_time", [0, -1, "not-a-time"])
    def test_invalid_begin_time(self, begin_time):
        serializer = ListAlertLogResource.RequestSerializer(
            data={"id": ALERT_ID, "begin_time": begin_time, "trigger_condition": None}
        )

        assert not serializer.is_valid()

    def test_begin_time_accepts_positive_timestamp(self):
        validated = self.validate({"id": ALERT_ID, "begin_time": 1, "trigger_condition": None})

        assert validated["begin_time"] == 1

    @pytest.mark.parametrize(
        "condition",
        [
            {},
            [],
            "",
            {"type": []},
            {"type": {}},
            {"type": 1},
            {"type": True},
            {"type": None},
            {"type": "unknown"},
            {"type": "algorithm", "check_window": 5},
            {"type": "algorithm", "check_window": 5, "count": 3, "text": "文案"},
            {"type": "algorithm", "check_window": 0, "count": 3},
            {"type": "algorithm", "check_window": "5", "count": 3},
            {"type": "algorithm", "check_window": 5, "count": 3.0},
            {"type": "algorithm", "check_window": True, "count": 3},
            {"type": "no_data"},
            {"type": "no_data", "continuous": -1},
            "not-a-dict",
        ],
    )
    def test_invalid_condition(self, condition):
        serializer = ListAlertLogResource.RequestSerializer(
            data={"id": ALERT_ID, "begin_time": 1000, "trigger_condition": condition}
        )

        assert not serializer.is_valid()
        # 必须归到字段校验错误，而不是把 list/dict 当字典键抛 TypeError
        assert "trigger_condition" in serializer.errors


class TestPerformRequest:
    @staticmethod
    def patch_handler(monkeypatch):
        handler_cls = MagicMock()
        handler_cls.return_value.search.return_value = []
        monkeypatch.setattr(alert_resources, "AlertLogHandler", handler_cls)
        return handler_cls

    def test_pass_optional_params(self, monkeypatch):
        handler_cls = self.patch_handler(monkeypatch)

        ListAlertLogResource().perform_request(
            {
                "id": ALERT_ID,
                "limit": 20,
                "operate": [],
                "offset": 0,
                "begin_time": 1000,
                "trigger_condition": None,
            }
        )

        handler_cls.assert_called_once_with(ALERT_ID, begin_time=1000, trigger_condition=None)

    def test_absent_params_not_passed(self, monkeypatch):
        handler_cls = self.patch_handler(monkeypatch)

        ListAlertLogResource().perform_request({"id": ALERT_ID, "limit": 20, "operate": []})

        handler_cls.assert_called_once_with(ALERT_ID)
