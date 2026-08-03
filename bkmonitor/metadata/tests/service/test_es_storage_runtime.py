import re
from types import SimpleNamespace
from unittest.mock import Mock

from metadata.service.es_storage import query_es_storage_runtime


def _build_client(*, stats=None, cat_rows=None, settings=None, aliases=None, mappings=None):
    return SimpleNamespace(
        cat=SimpleNamespace(indices=Mock(return_value=cat_rows or [])),
        indices=SimpleNamespace(
            stats=Mock(return_value=stats or {"indices": {}}),
            get_settings=Mock(return_value=settings or {}),
            get_alias=Mock(return_value=aliases or {}),
            get_mapping=Mock(return_value=mappings or {}),
        ),
    )


def test_managed_es_runtime_uses_v2_v1_rule_and_returns_projected_fields(mocker):
    index_name = "v2_system_cpu_20260803_0"
    client = _build_client(
        cat_rows=[
            {
                "index": index_name,
                "uuid": "index-uuid",
                "health": "green",
                "status": "open",
                "pri": "1",
                "rep": "1",
                "docs.count": "3",
                "docs.deleted": "1",
                "store.size": "128",
                "pri.store.size": "64",
            }
        ],
        settings={
            index_name: {
                "settings": {
                    "index": {
                        "number_of_shards": "1",
                        "number_of_replicas": "1",
                        "creation_date": "1785722400000",
                    }
                }
            }
        },
        aliases={
            index_name: {
                "aliases": {
                    "system_cpu_20260803_read": {},
                    "write_20260803_system_cpu": {
                        "is_write_index": True,
                        "filter": {"term": {"ignored": True}},
                    },
                    "unmanaged_alias": {},
                }
            }
        },
    )
    storage = SimpleNamespace(
        table_id="system.cpu",
        origin_table_id=None,
        storage_cluster_id=1,
        index_set="ignored-for-managed-storage",
        need_create_index=True,
        search_format_v2=lambda: "v2_system_cpu_*",
        search_format_v1=lambda: "system_cpu_*",
        get_client=lambda: client,
        es_client=client,
        index_re_v2=re.compile(r"^v2_system_cpu_(?P<datetime>\d+)_(?P<index>\d+)$"),
        index_re_v1=re.compile(r"^system_cpu_(?P<datetime>\d+)_(?P<index>\d+)$"),
        write_alias_re=re.compile(r"write_(?P<datetime>\d+)_system_cpu"),
        old_write_alias_re=re.compile(r"system_cpu_(?P<datetime>\d+)_write"),
        read_alias_re=re.compile(r"system_cpu_(?P<datetime>\d+)_read"),
    )
    storage.get_index_stats = Mock(
        return_value=(
            {
                index_name: {
                    "uuid": "index-uuid",
                    "total": {"docs": {"count": 6, "deleted": 2}, "store": {"size_in_bytes": 128}},
                    "primaries": {"docs": {"count": 3, "deleted": 1}, "store": {"size_in_bytes": 64}},
                }
            },
            "v2",
        )
    )
    cluster = SimpleNamespace(cluster_id=2)
    mocker.patch("metadata.service.es_storage.clone_es_storage_with_cluster", return_value=storage)

    data, warnings = query_es_storage_runtime(
        es_storage=storage,
        bk_tenant_id="system",
        runtime_cluster=cluster,
        includes={"indices", "aliases"},
        timeout=15,
    )

    storage.get_index_stats.assert_called_once_with(request_timeout=15)
    assert client.cat.indices.call_args.kwargs["index"] == "v2_system_cpu_*"
    assert client.indices.get_settings.call_args.kwargs["request_timeout"] == 15
    assert client.indices.get_alias.call_args.kwargs == {"index": index_name, "request_timeout": 15}
    assert data["index_query"] == {
        "mode": "managed",
        "need_create_index": True,
        "source": "generated_table_pattern",
        "expression": "v2_system_cpu_*",
        "index_version": "v2",
        "candidates": ["v2_system_cpu_*", "system_cpu_*"],
    }
    assert data["indices"] == {
        "count": 1,
        "total_docs": 3,
        "total_store_size_bytes": 128,
        "items": [
            {
                "index": index_name,
                "uuid": "index-uuid",
                "health": "green",
                "status": "open",
                "docs_count": 3,
                "docs_deleted": 1,
                "store_size_bytes": 128,
                "primary_store_size_bytes": 64,
                "primary_shards": 1,
                "replica_shards": 1,
                "replica_factor": 1,
                "shards": 2,
                "creation_date_ms": 1785722400000,
            }
        ],
    }
    assert data["aliases"] == {
        "queried": True,
        "count": 2,
        "relation_count": 2,
        "items": [
            {
                "alias": "system_cpu_20260803_read",
                "alias_type": "read",
                "datetime": "20260803",
                "indices": [index_name],
                "write_index": None,
            },
            {
                "alias": "write_20260803_system_cpu",
                "alias_type": "write",
                "datetime": "20260803",
                "indices": [index_name],
                "write_index": index_name,
            },
        ],
    }
    assert "stats" not in data["indices"]["items"][0]
    assert "store_size" not in data["indices"]["items"][0]
    assert warnings == []


def test_es_runtime_docs_fall_back_to_cat_before_total_stats(mocker):
    index_name = "external-logs-2026.08.03"
    client = _build_client(
        stats={
            "indices": {
                index_name: {
                    "total": {"docs": {"count": 14, "deleted": 4}, "store": {"size_in_bytes": 2048}},
                    "primaries": {"store": {"size_in_bytes": 1024}},
                }
            }
        },
        cat_rows=[
            {
                "index": index_name,
                "docs.count": "7",
                "docs.deleted": "2",
                "store.size": "2048",
                "pri.store.size": "1024",
            }
        ],
    )
    storage = SimpleNamespace(
        table_id="2_bklog.external",
        origin_table_id=None,
        storage_cluster_id=1,
        index_set="external-logs-*",
        need_create_index=False,
        get_client=lambda: client,
        es_client=client,
    )
    cluster = SimpleNamespace(cluster_id=2)
    mocker.patch("metadata.service.es_storage.clone_es_storage_with_cluster", return_value=storage)

    data, warnings = query_es_storage_runtime(
        es_storage=storage,
        bk_tenant_id="system",
        runtime_cluster=cluster,
        includes={"indices"},
        timeout=9,
    )

    assert data["indices"]["total_docs"] == 7
    assert data["indices"]["items"][0]["docs_count"] == 7
    assert data["indices"]["items"][0]["docs_deleted"] == 2
    assert warnings == []


def test_external_es_runtime_uses_index_set_without_managed_date_patterns(mocker):
    index_name = "external-logs-2026.08.03"
    client = _build_client(
        stats={
            "indices": {
                index_name: {
                    "primaries": {"docs": {"count": 7}, "store": {"size_in_bytes": 2048}},
                }
            }
        },
        cat_rows=[
            {
                "index": index_name,
                "health": "yellow",
                "status": "open",
                "primary_shards": "2",
                "replicas": "0",
                "docsCount": "7",
                "storeSize": "2048",
            }
        ],
        settings={
            index_name: {
                "settings": {
                    "index.number_of_shards": "2",
                    "index.number_of_replicas": "0",
                }
            }
        },
        aliases={index_name: {"aliases": {"external-current": {}}}},
    )
    search_format_v2 = Mock(side_effect=AssertionError("external index must not use v2 pattern"))
    search_format_v1 = Mock(side_effect=AssertionError("external index must not use v1 pattern"))
    storage = SimpleNamespace(
        table_id="2_bklog.external",
        origin_table_id="2_bklog.physical",
        storage_cluster_id=1,
        index_set="external-logs-*",
        need_create_index=False,
        search_format_v2=search_format_v2,
        search_format_v1=search_format_v1,
        get_client=lambda: client,
        es_client=client,
        index_re_v2=re.compile("never"),
        index_re_v1=re.compile("never"),
    )
    cluster = SimpleNamespace(cluster_id=2)
    mocker.patch("metadata.service.es_storage.clone_es_storage_with_cluster", return_value=storage)

    data, warnings = query_es_storage_runtime(
        es_storage=storage,
        bk_tenant_id="system",
        runtime_cluster=cluster,
        includes={"indices", "aliases"},
        timeout=9,
    )

    assert client.indices.stats.call_args.kwargs == {"index": "external-logs-*", "request_timeout": 9}
    assert client.cat.indices.call_args.kwargs["index"] == "external-logs-*"
    client.indices.get_alias.assert_not_called()
    search_format_v2.assert_not_called()
    search_format_v1.assert_not_called()
    assert data["index_query"] == {
        "mode": "external",
        "need_create_index": False,
        "source": "index_set",
        "expression": "external-logs-*",
    }
    assert data["indices"]["items"][0]["docs_count"] == 7
    assert data["indices"]["items"][0]["store_size_bytes"] == 2048
    assert data["aliases"] == {
        "queried": False,
        "reason": "need_create_index_false",
        "count": 0,
        "relation_count": 0,
        "items": [],
    }
    assert warnings == []


def test_external_es_runtime_failure_does_not_fallback_to_managed_physical_storage(mocker):
    client = _build_client()
    client.indices.stats.side_effect = RuntimeError("external index unavailable")
    storage = SimpleNamespace(
        table_id="2_bklog.external",
        origin_table_id="2_bklog.managed_physical",
        storage_cluster_id=1,
        index_set="external-logs-*",
        need_create_index=False,
        get_client=lambda: client,
        es_client=client,
        index_re_v2=re.compile("never"),
        index_re_v1=re.compile("never"),
    )
    cluster = SimpleNamespace(cluster_id=2)
    mocker.patch("metadata.service.es_storage.clone_es_storage_with_cluster", return_value=storage)
    physical_lookup = mocker.patch("metadata.service.es_storage.models.ESStorage.objects.filter")

    data, warnings = query_es_storage_runtime(
        es_storage=storage,
        bk_tenant_id="system",
        runtime_cluster=cluster,
        includes={"indices", "aliases"},
        timeout=9,
    )

    assert data["indices"] is None
    assert data["aliases"]["queried"] is False
    assert warnings[0]["code"] == "RUNTIME_QUERY_FAILED"
    physical_lookup.assert_not_called()


def test_managed_aliases_are_none_when_index_resolution_fails(mocker):
    client = _build_client()
    get_index_stats = Mock(side_effect=RuntimeError("index stats unavailable"))
    storage = SimpleNamespace(
        table_id="system.cpu",
        origin_table_id=None,
        storage_cluster_id=1,
        index_set=None,
        need_create_index=True,
        search_format_v2=lambda: "v2_system_cpu_*",
        search_format_v1=lambda: "system_cpu_*",
        get_index_stats=get_index_stats,
        get_client=lambda: client,
        es_client=client,
    )
    cluster = SimpleNamespace(cluster_id=2)
    mocker.patch("metadata.service.es_storage.clone_es_storage_with_cluster", return_value=storage)

    data, warnings = query_es_storage_runtime(
        es_storage=storage,
        bk_tenant_id="system",
        runtime_cluster=cluster,
        includes={"indices", "aliases"},
        timeout=15,
    )

    assert data["indices"] is None
    assert data["aliases"] is None
    assert get_index_stats.call_count == 2
    client.indices.get_alias.assert_not_called()
    assert [warning["code"] for warning in warnings] == ["RUNTIME_QUERY_FAILED", "RUNTIME_QUERY_FAILED"]


def test_mapping_query_does_not_depend_on_index_stats(mocker):
    mapping = {"v2_system_cpu_20260803_0": {"mappings": {"properties": {"value": {"type": "long"}}}}}
    client = _build_client(mappings=mapping)
    storage = SimpleNamespace(
        table_id="system.cpu",
        origin_table_id=None,
        storage_cluster_id=1,
        index_set=None,
        need_create_index=True,
        search_format_v2=lambda: "v2_system_cpu_*",
        search_format_v1=lambda: "system_cpu_*",
        get_index_stats=Mock(side_effect=RuntimeError("index stats unavailable")),
        get_client=lambda: client,
        es_client=client,
    )
    cluster = SimpleNamespace(cluster_id=2)
    mocker.patch("metadata.service.es_storage.clone_es_storage_with_cluster", return_value=storage)

    data, warnings = query_es_storage_runtime(
        es_storage=storage,
        bk_tenant_id="system",
        runtime_cluster=cluster,
        includes={"indices", "mapping"},
        timeout=15,
    )

    assert data["indices"] is None
    assert data["mapping"] == mapping
    assert client.indices.get_mapping.call_args.kwargs == {"index": "v2_system_cpu_*", "request_timeout": 15}
    assert [warning["code"] for warning in warnings] == ["RUNTIME_QUERY_FAILED"]
