from types import SimpleNamespace
from unittest.mock import call

import pytest

from apm.core.discover.base import TopoHandler


def response(sources, scroll_id=None):
    result = {"hits": {"hits": [{"_source": source} for source in sources]}}
    if scroll_id is not None:
        result["_scroll_id"] = scroll_id
    return result


@pytest.fixture
def handler(mocker):
    instance = object.__new__(TopoHandler)
    instance.bk_biz_id = 2
    instance.app_name = "test-app"
    instance.datasource = SimpleNamespace(es_client=mocker.Mock(), result_table_id="2_trace.test")
    mocker.patch("apm.core.discover.base.constants.DISCOVER_BATCH_SIZE", 2)
    return instance


def query(handler):
    return handler.list_span_by_trace_ids(["trace-a", "trace-b"], 3, "trace-index")


@pytest.mark.parametrize("count", [0, 1, 2])
def test_short_page_does_not_create_scroll(handler, count):
    sources = [{"span_id": str(i), "attributes": {"custom": i}} for i in range(count)]
    client = handler.datasource.es_client
    client.search.return_value = response(sources)

    assert query(handler) == sources
    client.search.assert_called_once_with(
        index="trace-index",
        body={"query": {"bool": {"must": [{"terms": {"trace_id": ["trace-a", "trace-b"]}}]}}, "size": 3},
    )
    client.scroll.assert_not_called()
    client.clear_scroll.assert_not_called()


def test_existing_direct_query_branch_keeps_its_page_size(handler):
    client = handler.datasource.es_client
    sources = [{"span_id": str(i)} for i in range(4)]
    client.search.return_value = response(sources)
    assert handler.list_span_by_trace_ids(["trace-a", "trace-b"], 5, "trace-index") == sources
    assert client.search.call_args.kwargs["body"]["size"] == 4
    assert "scroll" not in client.search.call_args.kwargs
    client.search.assert_called_once()
    client.scroll.assert_not_called()
    client.clear_scroll.assert_not_called()


@pytest.mark.parametrize("page_sizes", [(3,), (3, 1), (3, 3, 2)])
def test_full_probe_restarts_with_complete_scroll_snapshot(handler, page_sizes):
    client = handler.datasource.es_client
    sources = [{"span_id": str(i), "attributes": {"value": i}} for i in range(sum(page_sizes))]
    pages = []
    start = 0
    for count in page_sizes:
        pages.append(sources[start : start + count])
        start += count
    # 两次 search 之间的数据可以变化，结果只能来自完整的 scroll 快照。
    client.search.side_effect = [response([{"span_id": "probe"}] * 3), response(pages[0], "cursor-0")]
    client.scroll.side_effect = [response(page, f"cursor-{i}") for i, page in enumerate([*pages[1:], []], start=1)]

    assert query(handler) == sources
    assert client.search.call_count == 2
    first, second = client.search.call_args_list
    assert second.kwargs == {**first.kwargs, "scroll": "5m"}
    assert client.scroll.call_args_list == [call(scroll_id=f"cursor-{i}", scroll="5m") for i in range(len(pages))]
    client.clear_scroll.assert_called_once_with(scroll_id=f"cursor-{len(pages)}")


def test_scroll_without_replacement_id_cleans_last_known_cursor(handler):
    client = handler.datasource.es_client
    sources = [{"span_id": str(i)} for i in range(3)]
    client.search.side_effect = [response(sources), response(sources, "cursor-0")]
    client.scroll.return_value = response([])
    assert query(handler) == sources
    client.clear_scroll.assert_called_once_with(scroll_id="cursor-0")


@pytest.mark.parametrize("shared", [False, True])
def test_probe_and_scroll_keep_same_application_guard_and_full_source(handler, shared):
    handler.datasource.result_table_id = "apm_global.shared_trace" if shared else "2_trace.test"
    client = handler.datasource.es_client
    sources = [{"span_id": str(i)} for i in range(3)]
    client.search.side_effect = [response(sources), response(sources, "cursor-0")]
    client.scroll.return_value = response([], "cursor-1")
    query(handler)
    for request in client.search.call_args_list:
        body = request.kwargs["body"]
        assert set(body) == {"query", "size"}
        assert body["size"] == 3
        assert body["query"]["bool"]["must"] == [{"terms": {"trace_id": ["trace-a", "trace-b"]}}]
        assert body["query"]["bool"].get("filter", []) == (
            [{"term": {"bk_biz_id": 2}}, {"term": {"app_name": "test-app"}}] if shared else []
        )


@pytest.mark.parametrize("stage", ["probe_search", "probe_hits", "probe_source", "scroll_search"])
def test_failure_before_cursor_does_not_attempt_clear(handler, stage):
    client = handler.datasource.es_client
    failure = RuntimeError("search failed")
    if stage == "probe_search":
        client.search.side_effect = failure
    elif stage == "probe_hits":
        client.search.return_value = {}
    elif stage == "probe_source":
        client.search.return_value = {"hits": {"hits": [{}]}}
    else:
        client.search.side_effect = [response([{}] * 3), failure]

    with pytest.raises(RuntimeError if stage.endswith("search") else KeyError) as raised:
        query(handler)
    if stage.endswith("search"):
        assert raised.value is failure
    client.clear_scroll.assert_not_called()


@pytest.mark.parametrize("stage", ["initial_hits", "initial_source", "scroll", "next_hits", "next_source"])
@pytest.mark.parametrize("clear_fails", [False, True])
def test_query_or_parse_failure_clears_latest_cursor_without_masking_error(handler, stage, clear_fails):
    client = handler.datasource.es_client
    sources = [{"span_id": str(i)} for i in range(3)]
    first_scroll = response(sources, "cursor-0")
    failure = RuntimeError("scroll failed")
    last_cursor = "cursor-0"
    if stage == "initial_hits":
        first_scroll = {"_scroll_id": "cursor-0"}
    elif stage == "initial_source":
        first_scroll["hits"]["hits"] = [{}]
    elif stage == "scroll":
        client.scroll.side_effect = failure
    else:
        last_cursor = "cursor-1"
        client.scroll.return_value = {"_scroll_id": "cursor-1"}
        if stage == "next_source":
            client.scroll.return_value["hits"] = {"hits": [{}]}
    client.search.side_effect = [response(sources), first_scroll]
    if clear_fails:
        client.clear_scroll.side_effect = ValueError("clear failed")

    with pytest.raises(RuntimeError if stage == "scroll" else KeyError) as raised:
        query(handler)
    if stage == "scroll":
        assert raised.value is failure
    client.clear_scroll.assert_called_once_with(scroll_id=last_cursor)


def test_clear_failure_after_success_remains_a_failure(handler):
    client = handler.datasource.es_client
    sources = [{"span_id": str(i)} for i in range(3)]
    client.search.side_effect = [response(sources), response(sources, "cursor-0")]
    client.scroll.return_value = response([], "cursor-1")
    failure = RuntimeError("clear failed")
    client.clear_scroll.side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        query(handler)
    assert raised.value is failure
    client.clear_scroll.assert_called_once_with(scroll_id="cursor-1")
