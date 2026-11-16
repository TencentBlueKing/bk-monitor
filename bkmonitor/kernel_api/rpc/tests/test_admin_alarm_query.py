from unittest.mock import Mock

import pytest

from kernel_api.rpc.functions.admin import alarm_query as aq


@pytest.mark.parametrize("resource", ["event", "alert", "action"])
@pytest.mark.parametrize("tenant", ["tenant-a", "__all__"])
def test_search_scope_and_routing(monkeypatch, resource, tenant):
    monkeypatch.setattr(aq.settings, "ENABLE_MULTI_TENANT_MODE", True)
    doc = aq.DOCUMENTS[resource]
    client = Mock()
    client.search.return_value = {"hits": {"hits": [], "total": 0}}
    monkeypatch.setattr(doc._index, "_get_connection", lambda: client)
    result = aq.execute(
        "search",
        {
            "resource": resource,
            "bk_tenant_id": tenant,
            "query_string": "status:OK",
            "filters": [{"field": "severity", "op": "eq", "value": [1, 2]}],
            "page": 2,
        },
    )
    args = client.search.call_args.kwargs
    assert args["index"] == doc.build_all_indices_read_index_name()
    assert args["body"]["from"] == 20
    boolean = args["body"]["query"]["bool"]
    assert boolean["must"] == [{"query_string": {"query": "status:OK"}}]
    assert boolean["filter"] == [{"terms": {"severity": [1, 2]}}] + (
        [] if tenant == "__all__" else [{"term": {"bk_tenant_id": tenant}}]
    )
    assert result["meta"]["tenant_scope"] == ("all" if tenant == "__all__" else "single")


def test_dsl_tenant_escape(monkeypatch):
    monkeypatch.setattr(aq.settings, "ENABLE_MULTI_TENANT_MODE", True)
    with pytest.raises(Exception, match="global"):
        aq.search_body({"bk_tenant_id": "t", "dsl": {"aggs": {"all": {"global": {}}}}})
    with pytest.raises(Exception, match="跨索引"):
        aq.search_body(
            {
                "bk_tenant_id": "__all__",
                "dsl": {"query": {"terms": {"field": {"index": "unrelated", "id": "1", "path": "ids"}}}},
            }
        )


def test_group_cursor_and_partial_results():
    client = Mock()
    client.search.return_value = {
        "hits": {"total": {"value": 8, "relation": "eq"}},
        "timed_out": True,
        "aggregations": {
            "counts": {"buckets": [{"key": {"a": "x", "b": "y"}, "doc_count": 4}], "after_key": {"a": "x", "b": "y"}}
        },
    }
    warnings = []
    result = aq.aggregate(
        client,
        "target",
        {"bk_tenant_id": "__all__", "kind": "groups", "fields": ["a", "b"], "after": {"a": "p", "b": "q"}},
        warnings,
    )
    group = client.search.call_args.kwargs["body"]["aggs"]["counts"]["composite"]
    assert group["after"] == {"a": "p", "b": "q"}
    assert len(group["sources"]) == 2
    assert result == {"total": 8, "buckets": [{"key": {"a": "x", "b": "y"}, "count": 4}], "after": {"a": "x", "b": "y"}}
    assert warnings[0]["code"] == "PARTIAL_SEARCH"


def test_alias_resolution_rejects_mixed_target():
    client = Mock()
    client.indices.get_alias.side_effect = [{"allowed": {"aliases": {"shared": {}}}}, {"allowed": {}, "other": {}}]
    with pytest.raises(Exception, match="不属于"):
        aq.select_target(client, "pattern", "shared")


def test_log_lookup_requires_visible_alert(monkeypatch):
    client = Mock()
    client.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr(aq.AlertDocument._index, "_get_connection", lambda: client)
    with pytest.raises(Exception, match="未找到"):
        aq.execute("alert_logs", {"resource": "alert", "alert_id": "other", "bk_tenant_id": "t"})
    assert client.search.call_count == 1


@pytest.mark.parametrize("kind", ["total", "top", "trend"])
def test_count_preserves_dsl_hit_conditions(kind):
    client = Mock()
    client.search.return_value = {
        "hits": {"total": {"value": 3, "relation": "eq"}},
        "aggregations": {
            "counts": {
                "buckets": [{"key": 3600000 if kind == "trend" else ["ok", 2], "doc_count": 3}]
                if kind != "total"
                else []
            }
        },
    }
    params = {
        "bk_tenant_id": "__all__",
        "kind": kind,
        "fields": ["status", "severity"],
        "dsl": {"query": {"match_all": {}}, "post_filter": {"term": {"strategy_id": "1"}}, "min_score": 0.5, "size": 0},
    }
    result = aq.aggregate(client, "target", params, [])
    body = client.search.call_args.kwargs["body"]
    assert body["min_score"] == 0.5
    assert body["query"]["bool"]["filter"] == [params["dsl"]["post_filter"]]
    if kind == "total":
        assert "aggs" not in body and result["total"] == 3
    elif kind == "trend":
        assert result["buckets"][0]["key"] == {"create_time": 3600}
    else:
        assert result["buckets"][0]["key"] == {"status": "ok", "severity": 2}


def test_index_inventory_survives_partial_permissions(monkeypatch):
    client = Mock()
    monkeypatch.setattr(aq.AlertDocument._index, "_get_connection", lambda: client)
    client.indices.get_alias.return_value = {"physical": {"aliases": {"read": {}, "write": {}}}}
    client.cat.indices.side_effect = RuntimeError("permission denied")
    client.indices.get_mapping.return_value = {
        "physical": {"mappings": {"properties": {"status": {"type": "keyword"}}}}
    }
    result = aq.execute(
        "indices", {"resource": "alert", "bk_tenant_id": "system", "target": "physical", "include_mapping": True}
    )
    assert result["data"]["items"][0]["aliases"] == ["read", "write"]
    assert result["data"]["mapping"]["properties"]["status"]["type"] == "keyword"
    assert result["warnings"][0]["code"] == "INDEX_STATS_UNAVAILABLE"
    aliases = aq.execute("aliases", {"resource": "alert", "bk_tenant_id": "system", "page_size": 1, "page": 2})["data"]
    assert aliases["total"] == 2 and aliases["items"][0]["aliases"] == ["write"]


def test_nested_and_conflicting_fields_require_explicit_dsl(monkeypatch):
    client = Mock()
    monkeypatch.setattr(aq.EventDocument._index, "_get_connection", lambda: client)
    flags = {"searchable": True, "aggregatable": True}
    client.field_caps.return_value = {
        "fields": {
            "tags.key": {"keyword": flags},
            "status": {"keyword": flags},
            "conflict": {"keyword": flags, "long": flags},
        }
    }
    data = aq.execute("fields", {"resource": "event", "bk_tenant_id": "system"})["data"]
    fields = {row["name"]: row for row in data["items"]}
    assert fields["status"]["aggregatable"]
    assert not fields["tags.key"]["searchable"]
    assert not fields["conflict"]["aggregatable"]
