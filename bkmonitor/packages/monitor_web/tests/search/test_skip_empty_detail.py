"""全局搜索跳过空明细滚动查询，同时保持聚合及权限行为。"""

from types import SimpleNamespace
from unittest import mock

import pytest
from elasticsearch.helpers import ScanError
from elasticsearch_dsl import Search

from monitor_web.search.handlers import action, alert
from monitor_web.search.handlers.base import SearchScope


class SearchClient:
    """仅替换传输层，执行真实的 DSL 响应解析和 scan 分页。"""

    def __init__(self, scene, buckets, documents=(), failed_shards=False):
        self.scene = scene
        self.buckets = buckets
        self.documents = documents
        self.failed_shards = failed_shards
        self.calls = []
        self.remaining = []

    def response(self, documents, scroll_id=None):
        result = {
            "hits": {"hits": documents, "total": len(documents)},
            "_shards": {"total": 1, "successful": 0 if self.failed_shards else 1},
        }
        if scroll_id:
            result["_scroll_id"] = scroll_id
        return result

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        body = kwargs.get("body", kwargs)
        if "aggs" in body:
            result = self.response([])
            if self.buckets is not None:
                result["aggregations"] = {"bk_biz_id": {"buckets": self.buckets}}
            return result
        terms = body["query"]["bool"]["filter"][0]["terms"]
        ids = terms["event.bk_biz_id" if self.scene == "alert" else "bk_biz_id"]
        hits = []
        for biz, identifier in self.documents:
            if str(biz) not in ids:
                continue
            source = {"id": identifier, f"{self.scene}_name": identifier}
            source.update({"event": {"bk_biz_id": str(biz)}} if self.scene == "alert" else {"bk_biz_id": str(biz)})
            hits.append({"_index": "test-records", "_id": identifier, "_source": source})
        self.remaining = hits[2:]
        return self.response(hits[:2], "cursor-first")

    def scroll(self, **kwargs):
        self.calls.append(("scroll", kwargs))
        page, self.remaining = self.remaining[:2], self.remaining[2:]
        return self.response(page, "cursor-next")

    def clear_scroll(self, **kwargs):
        self.calls.append(("clear_scroll", kwargs))
        return {"succeeded": True}


@pytest.fixture(params=[(alert, "Alert"), (action, "Action")], ids=["alert", "action"])
def search_handler(request):
    module, prefix = request.param

    def create(buckets, documents=(), failed_shards=False, allowed=(1, 2, 3)):
        client = SearchClient(prefix.lower(), buckets, documents, failed_shards)
        query_handler = SimpleNamespace(
            get_search_object=lambda: Search(using=client, index="test-records"),
            add_query_string=lambda search, query: search.query("query_string", query=query),
        )
        handler = getattr(module, f"{prefix}SearchHandler")(bk_biz_id=2, scope=SearchScope.GLOBAL, username="tester")
        handler.allowed_biz_ids = set(allowed)
        handler.all_business = [SimpleNamespace(bk_biz_id=biz, bk_biz_name=f"Business {biz}") for biz in allowed]
        return handler, client, mock.patch.object(module, f"{prefix}QueryHandler", return_value=query_handler)

    return create


@pytest.mark.parametrize("buckets", [None, [], [{"key": "invalid", "doc_count": 1}]])
def test_no_detail_business_skips_scroll_but_keeps_aggregation(search_handler, buckets):
    handler, client, patched = search_handler(buckets)
    with patched:
        assert handler.handle("needle").results == []
    assert [name for name, _ in client.calls] == ["search"]
    aggregate_request = client.calls[0][1].get("body", client.calls[0][1])
    assert aggregate_request["size"] == 1
    assert "aggs" in aggregate_request


def test_all_large_buckets_keep_summaries_permissions_names_and_sort(search_handler):
    buckets = [{"key": str(biz), "doc_count": 11} for biz in (3, 1, 2)]
    handler, client, patched = search_handler(buckets, allowed=(1, 2))
    with patched:
        result = handler.handle("needle", limit=10).results
    assert [(item.bk_biz_id, item.bk_biz_name, item.is_collected) for item in result] == [
        (2, "Business 2", True),
        (1, "Business 1", True),
    ]
    assert all(item.view == "event-center" and item.is_allowed for item in result)
    assert [name for name, _ in client.calls] == ["search"]


def test_mixed_buckets_preserve_boundary_and_all_cross_business_details(search_handler):
    buckets = [{"key": "1", "doc_count": 3}, {"key": "2", "doc_count": 3}, {"key": "3", "doc_count": 4}]
    documents = [(biz, f"record-{biz}-{number}") for biz in (1, 2) for number in range(3)]
    handler, client, patched = search_handler(buckets, documents)
    with patched:
        result = handler.handle("needle", limit=3).results
    assert [item.bk_biz_id for item in result] == [2, 2, 2, 1, 1, 1, 3]
    assert {item.title for item in result if not item.is_collected} == {identifier for _, identifier in documents}
    assert result[-1].is_collected
    assert sum(name == "search" for name, _ in client.calls) == 2
    detail_request = client.calls[1][1]
    assert detail_request["query"]["bool"]["filter"] == [
        {"terms": {"event.bk_biz_id" if handler.SCENE == "alert" else "bk_biz_id": ["1", "2"]}}
    ]
    assert detail_request["query"]["bool"]["must"] == [{"query_string": {"query": "needle"}}]
    assert client.calls[-1][0] == "clear_scroll"
    assert client.calls[-1][1]["scroll_id"] == "cursor-next"


def test_nonempty_scan_shard_failure_propagates_and_clears_cursor(search_handler):
    handler, client, patched = search_handler([{"key": "1", "doc_count": 1}], [(1, "record-1")], True)
    with patched, pytest.raises(ScanError):
        handler.handle("needle")
    assert client.calls[-1][0] == "clear_scroll"
    assert client.calls[-1][1]["scroll_id"] == "cursor-first"
