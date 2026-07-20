from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from fta_web.alert.handlers import alert as alert_handler
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.resources import SearchAlertResource
from fta_web.alert.serializers import AlertSearchSerializer


class FakeAggregations:
    def __init__(self, buckets, sum_other_doc_count=0):
        self.alert_ids = SimpleNamespace(buckets=buckets, sum_other_doc_count=sum_other_doc_count)

    def bucket(self, *args, **kwargs):
        return self


class FakeSearch:
    def __init__(self, result):
        self.aggs = FakeAggregations([])
        self.result = result

    def __getitem__(self, item):
        return self

    def execute(self):
        return self.result

    def filter(self, *args, **kwargs):
        return self

    def extra(self, *args, **kwargs):
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
    return handler


def setup_candidate_search(monkeypatch, handler, *, bucket_count, sum_other_doc_count):
    buckets = [SimpleNamespace(key=str(index)) for index in range(bucket_count)]
    result = SimpleNamespace(aggs=FakeAggregations(buckets, sum_other_doc_count=sum_other_doc_count))
    search = FakeSearch(result)
    monkeypatch.setattr(handler, "get_search_object", lambda: search)
    monkeypatch.setattr(handler, "add_conditions", lambda search_object: search_object)
    monkeypatch.setattr(handler, "add_query_string", lambda search_object: search_object)


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


def test_search_alert_defaults_to_complete_results():
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
