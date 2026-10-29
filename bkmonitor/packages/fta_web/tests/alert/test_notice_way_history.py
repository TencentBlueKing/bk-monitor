import pytest
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response
from rest_framework.exceptions import ValidationError

from .test_notice_way_partial import make_handler


def setup_notice_history(monkeypatch, actions, *, second_page_status=None):
    queries: list[dict] = []

    def execute(search):
        query: dict = search.to_dict()
        queries.append(query)
        after: list = query.get("search_after", [])
        page: list[dict] = [action for action in actions if not after or action["id"] < after[0]]
        page = sorted(page, key=lambda action: action["id"], reverse=True)[: query["size"]]
        return Response(
            search,
            {
                "hits": {
                    "hits": [{"_source": action, "sort": [action["id"]]} for action in page],
                    "total": {"value": len(actions), "relation": "eq"},
                },
                **(second_page_status or {} if len(queries) == 2 else {}),
            },
        )

    monkeypatch.setattr(Search, "execute", execute)
    return queries


def test_recovered_notice_does_not_hide_historical_voice(monkeypatch):
    handler = make_handler()
    setup_notice_history(
        monkeypatch,
        [
            {"id": "1", "alert_id": ["1"], "inputs": {"notify_info": {"voice": [["user"]]}}},
            {
                "id": "2",
                "alert_id": ["1"],
                "inputs": {"notify_info": {"voice": [["user"]]}, "exclude_notice_ways": ["voice"]},
            },
        ],
    )
    monkeypatch.setattr(handler, "_collect_current_alert_ids", lambda: {"1"})

    assert handler._get_alert_ids_by_notice_way(["voice"]) == ["1"]
    aggregation = handler.handle_aggs_notice_way({"1"})
    assert aggregation["count"] == 1
    assert next(child["count"] for child in aggregation["children"] if child["id"] == "voice") == 1


def test_history_is_paginated_and_channels_are_unioned_per_alert(monkeypatch):
    handler = make_handler()
    handler.NOTICE_WAY_ACTION_PAGE_SIZE = 2
    queries = setup_notice_history(
        monkeypatch,
        [
            {"id": "1", "alert_id": ["1", "2"], "inputs": {"notify_info": {"voice": [["user"]]}}},
            {"id": "2", "alert_id": ["1"], "inputs": {"notify_info": {"mail": ["user"]}}},
            {"id": "3", "alert_id": ["1"], "inputs": {"notify_info": {"mail": ["user"]}}},
        ],
    )

    assert handler._query_alert_notice_ways(alert_ids={"1"}) == {"1": {"voice", "mail"}}
    assert len(queries) == 2
    assert queries[0]["sort"] == [{"id": {"order": "desc"}}]
    assert queries[0]["size"] == 2
    assert "aggs" not in queries[0]
    assert queries[1]["search_after"] == ["2"]
    assert set(queries[0]["_source"]) == {
        "alert_id",
        "inputs.notify_info",
        "inputs.follow_notify_info",
        "inputs.exclude_notice_ways",
    }
    filters: list[dict] = queries[0]["query"]["bool"]["filter"]
    assert {"term": {"is_parent_action": True}} in filters
    assert {"term": {"action_plugin_type": "notice"}} in filters
    assert {"terms": {"alert_id": ["1"]}} in filters


def test_excluded_channels_do_not_match_without_an_earlier_notice(monkeypatch):
    handler = make_handler()
    setup_notice_history(
        monkeypatch,
        [
            {
                "id": "1",
                "alert_id": ["1"],
                "inputs": {
                    "notify_info": {"voice": [["user"]]},
                    "follow_notify_info": {"mail": ["follower"], "wxbot_mention_users": ["follower"]},
                    "exclude_notice_ways": ["voice"],
                },
            }
        ],
    )

    assert handler._query_alert_notice_ways(alert_ids={"1"}) == {"1": {"mail", "wxwork-bot"}}


def test_empty_alert_ids_do_not_query_action_history(monkeypatch):
    handler = make_handler()

    def unexpected_query(*args, **kwargs):
        raise AssertionError("empty candidates must not query action history")

    monkeypatch.setattr(Search, "execute", unexpected_query)

    assert handler._query_alert_notice_ways(alert_ids=set()) == {}


@pytest.mark.parametrize(
    ("page_status", "reason"),
    [
        ({"timed_out": True}, "notice_way_action_timeout"),
        ({"_shards": {"failed": 1}}, "notice_way_action_shard_failure"),
    ],
)
@pytest.mark.parametrize("allow_partial", [True, False])
def test_later_page_failure_preserves_completeness_contract(monkeypatch, page_status, reason, allow_partial):
    handler = make_handler(allow_partial=allow_partial)
    handler.NOTICE_WAY_ACTION_PAGE_SIZE = 1
    queries = setup_notice_history(
        monkeypatch,
        [
            {"id": "1", "alert_id": ["1"], "inputs": {"notify_info": {"voice": [["user"]]}}},
            {"id": "2", "alert_id": ["1"], "inputs": {"notify_info": {"mail": ["user"]}}},
        ],
        second_page_status=page_status,
    )

    if allow_partial:
        assert handler._query_alert_notice_ways({"1"}, partial_scopes=["aggs.notice_way"]) == {"1": {"mail", "voice"}}
    else:
        with pytest.raises(ValidationError, match="查询结果不完整"):
            handler._query_alert_notice_ways({"1"}, partial_scopes=["aggs.notice_way"])

    assert len(queries) == 2
    assert handler.partial_reasons[0]["code"] == reason
    assert handler.partial_reasons[0]["scopes"] == ["aggs.notice_way"]
