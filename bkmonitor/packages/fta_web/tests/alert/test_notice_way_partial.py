import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response
from rest_framework.exceptions import ValidationError

from constants.action import ActionStatus, NoticeWay
from fta_web.alert.handlers import alert as alert_handler
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.resources import SearchAlertResource
from fta_web.alert.serializers import AlertSearchSerializer


class FakeAggregations:
    def __init__(self, buckets, sum_other_doc_count=0, min_begin_time=None):
        self.alert_ids = SimpleNamespace(buckets=buckets, sum_other_doc_count=sum_other_doc_count)
        self.min_begin_time = SimpleNamespace(value=min_begin_time)
        self.metric_calls = 0

    def bucket(self, *args, **kwargs):
        return self

    def metric(self, *args, **kwargs):
        self.metric_calls += 1
        return self


class FakeSearch:
    def __init__(self, result):
        self.aggs = FakeAggregations([])
        self.result = result
        self.extra_kwargs = {}

    def __getitem__(self, item):
        return self

    def execute(self):
        return self.result

    def filter(self, *args, **kwargs):
        return self

    def extra(self, *args, **kwargs):
        self.extra_kwargs.update(kwargs)
        return self


def make_handler(*, allow_partial=True):
    handler = AlertQueryHandler.__new__(AlertQueryHandler)
    handler.allow_partial = allow_partial
    handler.partial_reasons = []
    handler.conditions = []
    handler.bk_biz_ids = [2]
    handler.authorized_bizs = None
    handler.start_time = 1711900800
    handler.end_time = 1711987200
    handler.query_context = {}
    handler._notice_ways_cache = None
    handler._notice_way_by_records = False
    handler._notice_way_start_time = None
    return handler


def setup_candidate_search(monkeypatch, handler, *, bucket_count, sum_other_doc_count, min_begin_time=None):
    buckets = [SimpleNamespace(key=str(index)) for index in range(bucket_count)]
    result = SimpleNamespace(
        aggs=FakeAggregations(buckets, sum_other_doc_count=sum_other_doc_count, min_begin_time=min_begin_time)
    )
    search = FakeSearch(result)
    monkeypatch.setattr(handler, "get_search_object", lambda: search)
    monkeypatch.setattr(handler, "add_conditions", lambda search_object: search_object)
    monkeypatch.setattr(handler, "add_query_string", lambda search_object: search_object)
    return search


def test_exactly_candidate_limit_is_complete(monkeypatch):
    handler = make_handler()
    setup_candidate_search(monkeypatch, handler, bucket_count=10000, sum_other_doc_count=0)

    alert_ids = handler._collect_current_alert_ids()

    assert len(alert_ids) == 10000
    assert handler.get_partial_metadata() == {
        "is_partial": False,
        "partial_reasons": [],
    }


def test_candidates_over_limit_mark_filter_result_partial(monkeypatch):
    handler = make_handler()
    setup_candidate_search(monkeypatch, handler, bucket_count=10000, sum_other_doc_count=3)

    handler._collect_current_alert_ids()

    assert handler.get_partial_metadata() == {
        "is_partial": True,
        "partial_reasons": [
            {
                "code": "notice_way_candidate_limit",
                "scopes": ["alerts", "total", "overview", "aggs"],
                "scanned_candidate_count": 10000,
                "candidate_limit": 10000,
            }
        ],
    }


def test_strict_query_rejects_partial_result(monkeypatch):
    handler = make_handler(allow_partial=False)
    setup_candidate_search(monkeypatch, handler, bucket_count=10000, sum_other_doc_count=1)

    with pytest.raises(ValidationError, match="查询结果不完整"):
        handler._collect_current_alert_ids()


def test_partial_notice_way_neq_is_rejected(monkeypatch):
    handler = make_handler(allow_partial=True)

    def get_partial_alert_ids(notice_ways):
        handler._mark_partial(
            code="notice_way_candidate_limit",
            scopes=["alerts", "total", "overview", "aggs"],
            scanned_candidate_count=10000,
            candidate_limit=10000,
        )
        return ["1"]

    monkeypatch.setattr(handler, "_get_alert_ids_by_notice_way", get_partial_alert_ids)

    with pytest.raises(ValidationError, match="排除条件"):
        handler.parse_condition_item(
            {
                "key": "notice_way",
                "origin_key": "notice_way",
                "value": ["voice"],
                "method": "neq",
            }
        )


def test_partial_notice_way_neq_is_rejected_when_reason_was_already_recorded(monkeypatch):
    handler = make_handler(allow_partial=True)
    reason = {
        "code": "notice_way_candidate_limit",
        "scopes": ["alerts", "total", "overview", "aggs"],
        "scanned_candidate_count": 10000,
        "candidate_limit": 10000,
    }
    handler.partial_reasons = [reason]

    def get_partial_alert_ids(notice_ways):
        handler._mark_partial(**reason)
        return ["1"]

    monkeypatch.setattr(handler, "_get_alert_ids_by_notice_way", get_partial_alert_ids)

    with pytest.raises(ValidationError, match="排除条件"):
        handler.parse_condition_item(
            {
                "key": "notice_way",
                "origin_key": "notice_way",
                "value": ["voice"],
                "method": "neq",
            }
        )


def test_search_response_marks_total_as_lower_bound(monkeypatch):
    handler = make_handler()
    handler._mark_partial(
        code="notice_way_candidate_limit",
        scopes=["alerts", "total", "overview", "aggs"],
        scanned_candidate_count=10000,
        candidate_limit=10000,
    )
    search_result = SimpleNamespace(hits=SimpleNamespace(total=SimpleNamespace(value=81, relation="eq")))
    monkeypatch.setattr(handler, "search_raw", lambda *args: (search_result, None))
    monkeypatch.setattr(handler, "handle_hit_list", lambda result: [])
    monkeypatch.setattr(handler, "handle_operator", lambda alerts: None)

    result = handler.search(show_overview=False, show_aggs=False)

    assert result["total"] == 81
    assert result["total_relation"] == "gte"
    assert result["is_partial"] is True
    assert result["partial_reasons"][0]["code"] == "notice_way_candidate_limit"


def test_search_alert_defaults_to_partial_result_metadata():
    serializer = SearchAlertResource.RequestSerializer(
        data={
            "bk_biz_ids": [2],
            "conditions": [],
            "query_string": "",
            "start_time": 1711900800,
            "end_time": 1711987200,
        }
    )

    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["allow_partial"] is True


def test_search_alert_can_explicitly_require_complete_results():
    serializer = SearchAlertResource.RequestSerializer(
        data={
            "bk_biz_ids": [2],
            "conditions": [],
            "query_string": "",
            "start_time": 1711900800,
            "end_time": 1711987200,
            "allow_partial": False,
        }
    )

    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["allow_partial"] is False


def test_shared_alert_search_serializer_preserves_partial_compatibility():
    serializer = AlertSearchSerializer(
        data={
            "bk_biz_ids": [2],
            "conditions": [],
            "query_string": "",
            "start_time": 1711900800,
            "end_time": 1711987200,
        }
    )

    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["allow_partial"] is True


def test_notice_way_aggregation_limit_only_marks_notice_way_aggregation(monkeypatch):
    handler = make_handler()
    search_result = SimpleNamespace(aggs=FakeAggregations([SimpleNamespace(key="1")], sum_other_doc_count=2))
    monkeypatch.setattr(handler, "handle_aggs_severity", lambda result: {"id": "severity"})
    monkeypatch.setattr(handler, "handle_aggs_notice_way", lambda alert_ids: {"id": "notice_way"})
    monkeypatch.setattr(handler, "handle_aggs_stage", lambda result: {"id": "stage"})
    monkeypatch.setattr(handler, "handle_aggs_data_type", lambda result: {"id": "data_type"})
    monkeypatch.setattr(handler, "handle_aggs_category", lambda result: {"id": "category"})

    handler.handle_aggs(search_result)

    assert handler.partial_reasons == [
        {
            "code": "notice_way_aggregation_candidate_limit",
            "scopes": ["aggs.notice_way"],
            "scanned_candidate_count": 1,
            "candidate_limit": 10000,
        }
    ]


def test_notice_way_filter_errors_are_not_converted_to_empty_results(monkeypatch):
    handler = make_handler()
    monkeypatch.setattr(handler, "_collect_current_alert_ids", lambda: {"1"})
    monkeypatch.setattr(
        handler, "_query_alert_notice_ways", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(RuntimeError, match="boom"):
        handler._get_alert_ids_by_notice_way(["voice"])


def test_notice_way_aggregation_errors_are_marked_partial(monkeypatch):
    handler = make_handler()
    monkeypatch.setattr(
        handler, "_query_alert_notice_ways", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    aggregation = handler.handle_aggs_notice_way({"1"})

    assert aggregation["is_partial"] is True
    assert handler.partial_reasons == [
        {
            "code": "notice_way_aggregation_failed",
            "scopes": ["aggs.notice_way"],
        }
    ]


def test_total_hits_lower_bound_does_not_mark_list_partial(monkeypatch):
    handler = make_handler()
    search_result = SimpleNamespace(
        hits=SimpleNamespace(total=SimpleNamespace(value=10000, relation="gte")),
        _shards=SimpleNamespace(failed=0),
    )
    monkeypatch.setattr(handler, "search_raw", lambda *args: (search_result, None))
    monkeypatch.setattr(handler, "handle_hit_list", lambda result: [])
    monkeypatch.setattr(handler, "handle_operator", lambda alerts: None)

    result = handler.search(show_overview=False, show_aggs=False)

    assert result["total_relation"] == "gte"
    assert result["is_partial"] is False
    assert result["partial_reasons"] == []


def test_failed_alert_shards_mark_whole_query_partial(monkeypatch):
    handler = make_handler()
    search_result = SimpleNamespace(
        hits=SimpleNamespace(total=SimpleNamespace(value=12, relation="eq")),
        _shards=SimpleNamespace(failed=1),
    )
    monkeypatch.setattr(handler, "search_raw", lambda *args: (search_result, None))
    monkeypatch.setattr(handler, "handle_hit_list", lambda result: [])
    monkeypatch.setattr(handler, "handle_operator", lambda alerts: None)

    result = handler.search(show_overview=False, show_aggs=False)

    assert result["total_relation"] == "gte"
    assert result["partial_reasons"] == [
        {
            "code": "alert_search_shard_failure",
            "scopes": ["alerts", "total", "overview", "aggs"],
            "failed_shards": 1,
        }
    ]


def test_timed_out_alert_search_marks_whole_query_partial(monkeypatch):
    handler = make_handler()
    search_result = SimpleNamespace(
        hits=SimpleNamespace(total=SimpleNamespace(value=12, relation="eq")),
        timed_out=True,
        _shards=SimpleNamespace(failed=0),
    )
    monkeypatch.setattr(handler, "search_raw", lambda *args: (search_result, None))
    monkeypatch.setattr(handler, "handle_hit_list", lambda result: [])
    monkeypatch.setattr(handler, "handle_operator", lambda alerts: None)

    result = handler.search(show_overview=False, show_aggs=False)

    assert result["total_relation"] == "gte"
    assert result["partial_reasons"] == [
        {
            "code": "alert_search_timeout",
            "scopes": ["alerts", "total", "overview", "aggs"],
        }
    ]


def test_notice_way_neq_allows_partial_result_from_final_alert_search(monkeypatch):
    handler = make_handler()
    monkeypatch.setattr(handler, "_get_alert_ids_by_notice_way", lambda notice_ways: ["1"])
    handler.parse_condition_item(
        {
            "key": "notice_way",
            "origin_key": "notice_way",
            "value": ["voice"],
            "method": "neq",
        }
    )
    search_result = SimpleNamespace(
        hits=SimpleNamespace(total=SimpleNamespace(value=12, relation="eq")),
        _shards=SimpleNamespace(failed=1),
    )
    monkeypatch.setattr(handler, "search_raw", lambda *args: (search_result, None))
    monkeypatch.setattr(handler, "handle_hit_list", lambda result: [])
    monkeypatch.setattr(handler, "handle_operator", lambda alerts: None)

    result = handler.search(show_overview=False, show_aggs=False)

    assert result["total_relation"] == "gte"
    assert result["partial_reasons"][0]["code"] == "alert_search_shard_failure"


def test_failed_candidate_shards_mark_filter_result_partial(monkeypatch):
    handler = make_handler()
    buckets = [SimpleNamespace(key="1")]
    result = SimpleNamespace(
        aggs=FakeAggregations(buckets),
        _shards=SimpleNamespace(failed=1),
    )
    search = FakeSearch(result)
    monkeypatch.setattr(handler, "get_search_object", lambda: search)
    monkeypatch.setattr(handler, "add_conditions", lambda search_object: search_object)
    monkeypatch.setattr(handler, "add_query_string", lambda search_object: search_object)

    handler._collect_current_alert_ids()

    assert handler.partial_reasons == [
        {
            "code": "notice_way_candidate_shard_failure",
            "scopes": ["alerts", "total", "overview", "aggs"],
            "failed_shards": 1,
        }
    ]


def test_timed_out_candidate_search_marks_filter_result_partial(monkeypatch):
    handler = make_handler()
    buckets = [SimpleNamespace(key="1")]
    result = SimpleNamespace(
        aggs=FakeAggregations(buckets),
        timed_out=True,
        _shards=SimpleNamespace(failed=0),
    )
    search = FakeSearch(result)
    monkeypatch.setattr(handler, "get_search_object", lambda: search)
    monkeypatch.setattr(handler, "add_conditions", lambda search_object: search_object)
    monkeypatch.setattr(handler, "add_query_string", lambda search_object: search_object)

    handler._collect_current_alert_ids()

    assert handler.partial_reasons == [
        {
            "code": "notice_way_candidate_timeout",
            "scopes": ["alerts", "total", "overview", "aggs"],
        }
    ]


def test_failed_action_shards_use_caller_partial_scope(monkeypatch):
    handler = make_handler()
    result = SimpleNamespace(
        aggregations=SimpleNamespace(per_alert=SimpleNamespace(buckets=[])),
        _shards=SimpleNamespace(failed=1),
    )
    search = FakeSearch(result)
    search.aggs = SimpleNamespace(bucket=lambda *args, **kwargs: SimpleNamespace(metric=lambda *args, **kwargs: None))
    monkeypatch.setattr(alert_handler.ActionInstanceDocument, "search", lambda **kwargs: search)

    handler._query_alert_notice_ways(alert_ids={"1"}, partial_scopes=["aggs.notice_way"])

    assert handler.partial_reasons == [
        {
            "code": "notice_way_action_shard_failure",
            "scopes": ["aggs.notice_way"],
            "failed_shards": 1,
        }
    ]


def test_timed_out_action_search_uses_caller_partial_scope(monkeypatch):
    handler = make_handler()
    result = SimpleNamespace(
        aggregations=SimpleNamespace(per_alert=SimpleNamespace(buckets=[])),
        timed_out=True,
        _shards=SimpleNamespace(failed=0),
    )
    search = FakeSearch(result)
    search.aggs = SimpleNamespace(bucket=lambda *args, **kwargs: SimpleNamespace(metric=lambda *args, **kwargs: None))
    monkeypatch.setattr(alert_handler.ActionInstanceDocument, "search", lambda **kwargs: search)

    handler._query_alert_notice_ways(alert_ids={"1"}, partial_scopes=["aggs.notice_way"])

    assert handler.partial_reasons == [
        {
            "code": "notice_way_action_timeout",
            "scopes": ["aggs.notice_way"],
        }
    ]


def test_search_includes_partial_reason_discovered_while_handling_aggregations(monkeypatch):
    handler = make_handler()
    search_result = SimpleNamespace(
        hits=SimpleNamespace(total=SimpleNamespace(value=8, relation="eq")),
        _shards=SimpleNamespace(failed=0),
    )
    monkeypatch.setattr(handler, "search_raw", lambda *args: (search_result, None))
    monkeypatch.setattr(handler, "handle_hit_list", lambda result: [])
    monkeypatch.setattr(handler, "handle_operator", lambda alerts: None)

    def handle_aggs(result):
        handler._mark_partial(
            code="notice_way_aggregation_candidate_limit",
            scopes=["aggs.notice_way"],
        )
        return []

    monkeypatch.setattr(handler, "handle_aggs", handle_aggs)

    result = handler.search(show_overview=False, show_aggs=True)

    assert result["is_partial"] is True
    assert result["partial_reasons"][0]["code"] == "notice_way_aggregation_candidate_limit"


@pytest.mark.parametrize("alert_ids", [set(), {"1"}])
def test_notice_way_aggregation_inherits_main_aggregation_partial_state(alert_ids):
    handler = make_handler()
    handler.partial_reasons = [
        {
            "code": "alert_search_shard_failure",
            "scopes": ["alerts", "total", "overview", "aggs"],
            "failed_shards": 1,
        }
    ]
    handler._notice_ways_cache = {}

    aggregation = handler.handle_aggs_notice_way(alert_ids)

    assert aggregation["is_partial"] is True


# ---------------------------------------------------------------------------
# 按通知记录统计（开关 ALERT_NOTICE_WAY_BY_RECORDS 打开）
# ---------------------------------------------------------------------------


def _composite_response(buckets, after_key=None, unfilled=None):
    """构造 composite 聚合的真实响应体；第 0 页需要 unfilled 桶"""
    aggregations = {"pairs": {"buckets": buckets}}
    if after_key is not None:
        aggregations["pairs"]["after_key"] = after_key
    if unfilled is not None:
        aggregations["unfilled"] = {"doc_count": unfilled}
    return {
        "took": 1,
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "failed": 0},
        "hits": {"total": {"value": 0, "relation": "eq"}, "max_score": None, "hits": []},
        "aggregations": aggregations,
    }


def _patch_search_pages(monkeypatch, pages, searches=None):
    """按顺序返回多页响应，记录每次请求的 start_time，可选记录执行时的 Search 对象"""
    captured = []

    def fake_search(**kwargs):
        captured.append(kwargs.get("start_time"))
        return Search()

    def fake_execute(self, *args, **kwargs):
        # Search.filter/exclude 会返回克隆，必须在 execute 时捕获最终对象
        if searches is not None:
            searches.append(self)
        return Response(self, pages.pop(0))

    monkeypatch.setattr(alert_handler.ActionInstanceDocument, "search", fake_search)
    monkeypatch.setattr(Search, "execute", fake_execute)
    return captured


def test_query_by_records_unions_channels_and_skips_sentinel(monkeypatch, caplog):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800

    pages = [
        _composite_response(
            [
                {"key": {"alert_id": "1", "notice_way": "voice"}, "doc_count": 2},
                {"key": {"alert_id": "1", "notice_way": "mail"}, "doc_count": 1},
                {"key": {"alert_id": "2", "notice_way": NoticeWay.NOTICE_WAY_NONE}, "doc_count": 1},
                {"key": {"alert_id": "2", "notice_way": "rtx"}, "doc_count": 1},
                # 候选集外的告警，必须被忽略
                {"key": {"alert_id": "999", "notice_way": "sms"}, "doc_count": 1},
            ],
            unfilled=0,
        )
    ]
    _patch_search_pages(monkeypatch, pages)

    with caplog.at_level(logging.INFO, logger="fta_web.alert.handlers.alert"):
        result = handler._query_notice_ways_by_records({"1", "2"}, None)

    assert result == {"1": {"voice", "mail"}, "2": {NoticeWay.QY_WEIXIN}}
    assert handler.partial_reasons == []
    # pairs 只统计入库组合：voice、mail、rtx 共 3 个；哨兵与候选集外告警不计入
    assert "pairs=3" in caplog.text


def test_query_by_records_paginates_until_after_key_missing(monkeypatch):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800
    handler.NOTICE_WAY_PAIRS_PAGE_SIZE = 2

    pages = [
        _composite_response(
            [
                {"key": {"alert_id": "1", "notice_way": "voice"}, "doc_count": 1},
                {"key": {"alert_id": "1", "notice_way": "mail"}, "doc_count": 1},
            ],
            after_key={"alert_id": "1", "notice_way": "mail"},
            unfilled=0,
        ),
        _composite_response([{"key": {"alert_id": "1", "notice_way": "sms"}, "doc_count": 1}]),
    ]
    captured = _patch_search_pages(monkeypatch, pages)

    assert handler._query_notice_ways_by_records({"1"}, None) == {"1": {"voice", "mail", "sms"}}
    assert captured == [1711900800, 1711900800]


def test_unfilled_records_mark_partial_instead_of_silently_undercounting(monkeypatch):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800
    _patch_search_pages(monkeypatch, [_composite_response([], unfilled=3)])

    assert handler._query_notice_ways_by_records({"1"}, None) == {}
    assert handler.partial_reasons == [
        {
            "code": "notice_way_field_missing",
            "scopes": ["alerts", "total", "overview", "aggs"],
            "missing_count": 3,
        }
    ]


def test_missing_start_time_marks_partial_and_falls_back_to_page_start(monkeypatch):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = None
    captured = _patch_search_pages(monkeypatch, [_composite_response([], unfilled=0)])

    handler._query_notice_ways_by_records({"1"}, None)

    assert captured == [handler.start_time]
    assert handler.partial_reasons == [
        {
            "code": "notice_way_history_start_missing",
            "scopes": ["alerts", "total", "overview", "aggs"],
        }
    ]


def test_save_notice_way_start_time_converts_millis_and_keeps_first_value():
    handler = make_handler()
    handler._notice_way_start_time = None

    handler._save_notice_way_start_time(SimpleNamespace(min_begin_time=SimpleNamespace(value=1711900800000.0)))
    assert handler._notice_way_start_time == 1711900800

    # 筛选路径先写入，后续聚合路径不得覆盖
    handler._save_notice_way_start_time(SimpleNamespace(min_begin_time=SimpleNamespace(value=1600000000000.0)))
    assert handler._notice_way_start_time == 1711900800

    # 没有该聚合（mock 或旧响应）时不写入、不报错
    handler._notice_way_start_time = None
    handler._save_notice_way_start_time(object())
    assert handler._notice_way_start_time is None


@pytest.mark.parametrize(("switch", "expected"), [(True, ["1"]), (False, [])])
def test_filter_alias_normalization_follows_switch(monkeypatch, switch, expected):
    handler = make_handler()
    handler._notice_way_by_records = switch
    monkeypatch.setattr(handler, "_collect_current_alert_ids", lambda: {"1"})
    monkeypatch.setattr(handler, "_query_alert_notice_ways", lambda **kwargs: {"1": {"qy_weixin"}})

    assert handler._get_alert_ids_by_notice_way(["rtx"]) == expected


# ---------------------------------------------------------------------------
# 写入侧：非父通知记录落原始渠道
# ---------------------------------------------------------------------------


def _make_action_instance(**overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        create_time=now,
        update_time=now,
        end_time=None,
        status=ActionStatus.SUCCESS,
        inputs={},
        ex_data={},
        alerts=["1"],
        strategy_id=1,
        alert_level=1,
        signal="abnormal",
        bk_biz_id=2,
        action_config={"name": "notice"},
        action_config_id="1",
        action_plugin={"plugin_key": "notice", "plugin_type": "notice"},
        outputs={},
        assignee=["a"],
        is_parent_action=False,
        parent_action_id=1,
        execute_times=1,
        failure_type="",
        get_content=lambda **kwargs: {},
        strategy={"name": "s"},
        converge_info={},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _stub_action_document_deps(monkeypatch):
    from alarm_backends.service.fta_action import utils as action_utils

    monkeypatch.setattr(action_utils, "get_notice_display_mapping", lambda way: "notice-display")
    monkeypatch.setattr(action_utils, "get_target_info_from_ctx", lambda instance, alerts: {})
    monkeypatch.setattr(action_utils, "bk_biz_id_to_bk_tenant_id", lambda bk_biz_id: "default")
    return action_utils


@pytest.mark.parametrize(
    ("raw_notice_way", "expected"),
    [
        ("voice", ["voice"]),
        (["voice", "mail"], ["voice", "mail"]),
        (None, [NoticeWay.NOTICE_WAY_NONE]),
        ("", [NoticeWay.NOTICE_WAY_NONE]),
    ],
)
def test_to_document_writes_raw_notice_way_for_child(monkeypatch, raw_notice_way, expected):
    action_utils = _stub_action_document_deps(monkeypatch)
    instance = _make_action_instance(inputs={"notice_way": raw_notice_way, "notify_info": {"voice": [["a"]]}})

    document = action_utils.to_document(instance, instance.update_time)

    assert document.to_dict()["notice_way"] == expected


def test_to_document_skips_parent_notice_action(monkeypatch):
    action_utils = _stub_action_document_deps(monkeypatch)
    instance = _make_action_instance(is_parent_action=True, inputs={"notify_info": {"voice": [["a"]]}})

    document = action_utils.to_document(instance, instance.update_time)

    assert "notice_way" not in document.to_dict()


def test_to_document_skips_non_notice_action(monkeypatch):
    action_utils = _stub_action_document_deps(monkeypatch)
    instance = _make_action_instance(
        action_plugin={"plugin_key": "job", "plugin_type": "job"},
        inputs={"notice_way": "voice"},
    )

    document = action_utils.to_document(instance, instance.update_time)

    assert "notice_way" not in document.to_dict()


# ---------------------------------------------------------------------------
# 授权、分页终止、降级与开关读取
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("tenant_wide", "expect_biz_terms"), [(True, False), (False, True)])
def test_query_by_records_biz_terms_follow_tenant_wide_authorization(monkeypatch, tenant_wide, expect_biz_terms):
    """与主查询一致：租户级授权时省略业务 terms，否则必须带上"""
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800
    handler.authorized_bizs = [2]
    monkeypatch.setattr(handler, "is_tenant_wide_authorized", lambda: tenant_wide)
    searches = []
    _patch_search_pages(monkeypatch, [_composite_response([], unfilled=0)], searches=searches)

    handler._query_notice_ways_by_records({"1"}, None)

    query = json.dumps(searches[0].to_dict()["query"], ensure_ascii=False)
    assert ("bk_biz_id" in query) is expect_biz_terms


def test_query_by_records_disables_total_hits(monkeypatch):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800
    searches = []
    _patch_search_pages(monkeypatch, [_composite_response([], unfilled=0)], searches=searches)

    handler._query_notice_ways_by_records({"1"}, None)

    body = searches[0].to_dict()
    assert body["size"] == 0
    assert body["track_total_hits"] is False


def test_query_by_records_logs_pages_pairs_and_took(monkeypatch, caplog):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800
    _patch_search_pages(monkeypatch, [_composite_response([], unfilled=0)])

    with caplog.at_level(logging.INFO, logger="fta_web.alert.handlers.alert"):
        handler._query_notice_ways_by_records({"1"}, None)

    assert "notice_way records: candidates=1 pages=1 pairs=0 took_ms=1" in caplog.text


def test_query_by_records_terminates_on_full_page_without_after_key(monkeypatch):
    handler = make_handler()
    handler._notice_way_by_records = True
    handler._notice_way_start_time = 1711900800
    handler.NOTICE_WAY_PAIRS_PAGE_SIZE = 2

    pages = [
        _composite_response(
            [
                {"key": {"alert_id": "1", "notice_way": "voice"}, "doc_count": 1},
                {"key": {"alert_id": "1", "notice_way": "mail"}, "doc_count": 1},
            ],
            unfilled=0,
        )
    ]
    captured = _patch_search_pages(monkeypatch, pages)

    assert handler._query_notice_ways_by_records({"1"}, None) == {"1": {"voice", "mail"}}
    assert len(captured) == 1


def test_notice_way_aggregation_degrades_to_partial_when_query_raises(monkeypatch):
    """聚合路径异常（如索引缺 mapping）降级为 0 + partial，不抛 500"""
    handler = make_handler()
    monkeypatch.setattr(
        handler,
        "_query_alert_notice_ways",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = handler.handle_aggs_notice_way({"1"})

    assert result["count"] == 0
    assert result["is_partial"] is True
    assert handler.partial_reasons[0]["code"] == "notice_way_aggregation_failed"


def test_collect_current_alert_ids_saves_history_start(monkeypatch):
    handler = make_handler()
    handler._notice_way_by_records = True
    search = setup_candidate_search(
        monkeypatch,
        handler,
        bucket_count=1,
        sum_other_doc_count=0,
        min_begin_time=1711900800000.0,
    )

    handler._collect_current_alert_ids()

    assert search.aggs.metric_calls == 1
    assert search.extra_kwargs["track_total_hits"] is False
    assert handler._notice_way_start_time == 1711900800


def test_collect_current_alert_ids_skips_min_agg_when_switch_off(monkeypatch):
    handler = make_handler()
    search = setup_candidate_search(monkeypatch, handler, bucket_count=1, sum_other_doc_count=0)

    handler._collect_current_alert_ids()

    assert search.aggs.metric_calls == 0
    assert search.extra_kwargs["track_total_hits"] is False


def test_handler_reads_switch_once_from_settings(settings):
    settings.ALERT_NOTICE_WAY_BY_RECORDS = True

    handler = AlertQueryHandler(bk_biz_ids=None, username="tester", need_bucket_count=False)

    assert handler._notice_way_by_records is True
