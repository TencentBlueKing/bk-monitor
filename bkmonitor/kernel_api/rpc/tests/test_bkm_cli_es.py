"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.exceptions import api_exception_handler
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli import es


# ---------------- fakes ----------------


class FakeESError(Exception):
    """模拟 elasticsearch 客户端异常（duck-type：status_code / error / info）。"""

    def __init__(self, status_code, error=None, info=None):
        super().__init__(error or "es error")
        self.status_code = status_code
        self.error = error
        self.info = info


class _FakeIndices:
    def __init__(self, mapping):
        self._mapping = mapping
        self.last_fields = None

    def get_field_mapping(self, index, fields, params):
        self.last_fields = fields
        return self._mapping


class _FakeNodes:
    def __init__(self, stats):
        self._stats = stats

    def stats(self, metric, params):
        return self._stats


class _FakeCat:
    def __init__(self, rows):
        self._rows = rows
        self.segments_called_with_index = "unset"

    def segments(self, index=None, **kwargs):
        self.segments_called_with_index = index
        return self._rows


class FakeESClient:
    def __init__(self, *, search=None, mapping=None, node_stats=None, cat_rows=None):
        self._search = search
        self.indices = _FakeIndices(mapping)
        self.nodes = _FakeNodes(node_stats)
        self.cat = _FakeCat(cat_rows or [])

    def search(self, index, body, params):
        self.last_search = {"index": index, "body": body, "params": params}
        return self._search


def _search_resp(
    *,
    shards_failed=0,
    timed_out=False,
    total=12345,
    total_relation="gte",
    top_buckets=None,
    top_exists=0,
    by_index=None,
    sum_other=0,
):
    return {
        "_shards": {"total": 5, "successful": 5 - shards_failed, "failed": shards_failed, "failures": []},
        "timed_out": timed_out,
        "hits": {"total": {"value": total, "relation": total_relation}},
        "aggregations": {
            "probe": {"buckets": top_buckets if top_buckets is not None else []},
            "field_exists": {"doc_count": top_exists},
            "by_index": {"sum_other_doc_count": sum_other, "buckets": by_index or []},
        },
    }


def _idx_bucket(name, *, doc_count, probe_buckets, exists):
    return {
        "key": name,
        "doc_count": doc_count,
        "probe": {"buckets": probe_buckets},
        "field_exists": {"doc_count": exists},
    }


def _run_probe(resp):
    return es._terms_agg_probe(FakeESClient(search=resp), 10, {"index_pattern": "idx-*", "field": "namespace"})


MISSING = es.MISSING_PLACEHOLDER


# ---------------- 注册 ----------------


def test_es_ops_registered():
    assert BkmCliOpRegistry.resolve("es-diagnose").func_name == "bkm_cli.es_diagnose"
    assert BkmCliOpRegistry.resolve("list-es-capabilities").func_name == "bkm_cli.list_es_capabilities"
    assert BkmCliOpRegistry.resolve("list-es-clusters").func_name == "bkm_cli.list_es_clusters"
    # 8 个白名单 operation（list-es-clusters 是独立 op，不进 es_diagnose 的 ALLOWED_OPERATIONS）
    assert len(es.ALLOWED_OPERATIONS) == 8
    assert {c["operation"] for c in es.ES_CAPABILITIES} == set(es.ALLOWED_OPERATIONS)


# ---------------- 服务端护栏（安全模型，非 CLI 自律）----------------


def test_es_diagnose_rejects_non_allowlisted_operation():
    # operation 白名单在服务端强制：非白名单项在解析集群/构造客户端之前就被拒（不靠 CLI 自律）。
    with pytest.raises(CustomException) as exc:
        es.es_diagnose({"cluster_id": "10", "operation": "_cluster/settings"})
    assert exc.value.data["error_code"] == "OPERATION_NOT_ALLOWED"


def test_terms_agg_probe_forces_size_zero_and_breakdown_aggs():
    # AC3 硬门槛：probe 的 search body 恒 size:0（绝不返回原始文档→消除跨租户读原文），
    # 且带 by_index 下钻 + field_exists 过滤（逐索引归因所依赖的结构）。
    client = FakeESClient(search=_search_resp())
    es._terms_agg_probe(client, 10, {"index_pattern": "idx-*", "field": "namespace"})
    body = client.last_search["body"]
    assert body["size"] == 0
    assert body["aggs"]["probe"]["terms"]["field"] == "namespace"
    assert body["aggs"]["field_exists"]["filter"]["exists"]["field"] == "namespace"
    assert "by_index" in body["aggs"]
    # probe 用专属放宽超时（须 < CLI 30s 抓取超时，让服务端 ES_QUERY_TIMEOUT 先于 CLI abort 触发）
    assert body["timeout"] == es.PROBE_SEARCH_TIMEOUT
    assert client.last_search["params"]["request_timeout"] == es.PROBE_REQUEST_TIMEOUT


def test_load_es_cluster_rejects_non_es_cluster_type(monkeypatch):
    # cluster_type 守卫：拒绝把 kafka/influxdb 等非 ES 存储当 ES 直查，
    # 避免对任意已注册存储 host 发带凭据的只读外呼。
    from metadata.models import ClusterInfo

    class _FakeCluster:
        cluster_type = "kafka"
        bk_tenant_id = "system"

    monkeypatch.setattr(ClusterInfo.objects, "get", lambda **kwargs: _FakeCluster())
    with pytest.raises(CustomException) as exc:
        es._load_es_cluster(10)
    assert exc.value.data["error_code"] == "OPERATION_NOT_ALLOWED"


# ---------------- #2 list-es-clusters（fleet 发现，仅元数据、不探活）----------------


class _FakeClusterQS:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, **kwargs):  # name_contains__icontains 二次过滤
        sub = kwargs.get("cluster_name__icontains")
        rows = [r for r in self._rows if sub.lower() in r["cluster_name"].lower()] if sub else self._rows
        return _FakeClusterQS(rows)

    def order_by(self, *a):
        return self

    def count(self):
        return len(self._rows)

    def values(self, *fields):
        return [{f: r.get(f) for f in fields} for r in self._rows]


def _es_row(cid, name, version="7.10.2", display=""):
    return {
        "cluster_id": cid,
        "cluster_name": name,
        "display_name": display,
        "cluster_type": "elasticsearch",
        "version": version,
    }


def _patch_cluster_filter(monkeypatch, es_rows):
    from metadata.models import ClusterInfo

    captured = {}

    def fake_filter(**kwargs):
        captured["cluster_type"] = kwargs.get("cluster_type")
        return _FakeClusterQS(es_rows)

    monkeypatch.setattr(ClusterInfo.objects, "filter", fake_filter)
    return captured


def test_list_es_clusters_filters_to_es_type(monkeypatch):
    from metadata.models import ClusterInfo

    captured = _patch_cluster_filter(monkeypatch, [_es_row(1, "es_a"), _es_row(2, "es_b", version=None)])
    out = es.list_es_clusters({})
    assert captured["cluster_type"] == ClusterInfo.TYPE_ES  # 只查 ES 类型（非 ES 永不进结果）
    assert out["count"] == 2
    assert {it["cluster_id"] for it in out["items"]} == {1, 2}


def test_list_es_clusters_returns_only_safe_fields(monkeypatch):
    _patch_cluster_filter(monkeypatch, [_es_row(1, "es_a")])
    item = es.list_es_clusters({})["items"][0]
    assert set(item.keys()) == {"cluster_id", "cluster_name", "display_name", "cluster_type", "version"}
    # 凭据/host/port 等敏感字段绝不出现（.values 白名单是唯一泄露面，负向断言守住）
    for forbidden in ("domain_name", "port", "username", "password", "schema", "ssl_certificate"):
        assert forbidden not in item


def test_list_es_clusters_null_version_surfaced(monkeypatch):
    _patch_cluster_filter(monkeypatch, [_es_row(2, "es_b", version=None)])
    assert es.list_es_clusters({})["items"][0]["version"] is None  # 如实回 null、不抛错不填假值


def test_list_es_clusters_truncation_note(monkeypatch):
    rows = [_es_row(i, f"es_{i}") for i in range(es.CLUSTER_LIST_MAX_ROWS + 5)]
    _patch_cluster_filter(monkeypatch, rows)
    out = es.list_es_clusters({})
    assert out["truncated"] is True
    assert out["returned"] == es.CLUSTER_LIST_MAX_ROWS
    assert out["count"] == es.CLUSTER_LIST_MAX_ROWS + 5
    assert "截断" in out["summary"]


def test_list_es_clusters_name_contains_filter(monkeypatch):
    _patch_cluster_filter(monkeypatch, [_es_row(1, "bklog_es"), _es_row(2, "metric_es")])
    out = es.list_es_clusters({"name_contains": "bklog"})
    assert {it["cluster_id"] for it in out["items"]} == {1}


# ---------------- #6 可聚合类型 allowlist ----------------


@pytest.mark.parametrize(
    "definition,expected",
    [
        ({"type": "keyword"}, True),
        ({"type": "long"}, True),
        ({"type": "date"}, True),
        ({"type": "boolean"}, True),
        ({"type": "ip"}, True),
        ({"type": "version"}, True),
        ({"type": "wildcard"}, True),
        ({"type": "constant_keyword"}, True),
        ({"type": "keyword", "doc_values": False}, False),  # 显式关 doc_values
        ({"type": "text"}, False),  # text 无 fielddata
        ({"type": "text", "fielddata": True}, True),  # text 开 fielddata
        ({"type": "nested"}, False),
        ({"type": "geo_point"}, False),
        ({"type": "geo_shape"}, False),
        ({"type": "completion"}, False),
        ({}, False),  # object / 无 type 容器 → None → 不可聚合
    ],
)
def test_agg_leaf_row_aggregatable_allowlist(definition, expected):
    row = es._agg_leaf_row("idx", "f", "f", definition)
    assert row["aggregatable"] is expected


def test_field_mapping_surfaces_multifield_keyword_subfield():
    mapping = {
        "idx-1": {
            "mappings": {
                "namespace": {
                    "full_name": "namespace",
                    "mapping": {"namespace": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}},
                }
            }
        }
    }
    result = es._field_mapping(FakeESClient(mapping=mapping), 10, {"index_pattern": "idx-*", "field": "namespace"})
    by_path = {item["field_path"]: item for item in result["items"]}
    assert by_path["namespace"]["type"] == "text"
    assert by_path["namespace"]["aggregatable"] is False
    # multi-field 子字段必须显式暴露且按自身定义判定可聚合
    assert by_path["namespace.keyword"]["type"] == "keyword"
    assert by_path["namespace.keyword"]["aggregatable"] is True


# ---------------- #3 field_mapping list 模式（field 省略=自发现可聚合字段）----------------


def test_field_mapping_list_mode_sorts_aggregatable_first():
    mapping = {
        "idx-1": {
            "mappings": {
                "namespace": {
                    "full_name": "namespace",
                    "mapping": {"namespace": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}},
                },
                "ts": {"full_name": "ts", "mapping": {"ts": {"type": "date"}}},
                "geo": {"full_name": "geo", "mapping": {"geo": {"type": "geo_point"}}},
            }
        }
    }
    result = es._field_mapping(FakeESClient(mapping=mapping), 10, {"index_pattern": "idx-*"})
    assert result["field"] is None
    paths = [it["field_path"] for it in result["items"]]
    aggs = [it["field_path"] for it in result["items"] if it["aggregatable"]]
    non_aggs = [it["field_path"] for it in result["items"] if not it["aggregatable"]]
    assert paths == aggs + non_aggs  # 可聚合段整体在前
    assert set(aggs) == {"namespace.keyword", "ts"}
    assert set(non_aggs) == {"namespace", "geo"}
    assert "namespace.keyword" in paths  # multi-field 子字段在 list 模式也 surface
    assert result["meta"]["clean_aggregatable_count"] == 2
    assert result["meta"]["conflicted_count"] == 0  # 单索引、无跨索引分歧
    assert result["meta"]["total_field_paths"] == 4
    assert set(result["items"][0].keys()) == {
        "field_path",
        "type",
        "types",
        "aggregatable",
        "conflicted",
        "indices",
        "aggregatable_indices",
    }
    assert "2 个全索引一致可聚合" in result["summary"]


def test_field_mapping_list_mode_conflicting_field_not_clean_aggregatable():
    # 真实问题：跨索引同名字段 type 不一致（idx-new=keyword 可聚合 / idx-old=text 不可聚合）。
    # 必须标 conflicted、aggregatable 保守取 false——绝不把"第一个索引可聚合"误报成整 pattern 可直接 probe。
    mapping = {
        "idx-new": {"mappings": {"ns": {"full_name": "ns", "mapping": {"ns": {"type": "keyword"}}}}},
        "idx-old": {"mappings": {"ns": {"full_name": "ns", "mapping": {"ns": {"type": "text"}}}}},
    }
    result = es._field_mapping(FakeESClient(mapping=mapping), 10, {"index_pattern": "idx-*"})
    ns = next(it for it in result["items"] if it["field_path"] == "ns")
    assert ns["conflicted"] is True
    assert ns["aggregatable"] is False  # 保守：非全体一致可聚合
    assert ns["type"] is None and set(ns["types"]) == {"keyword", "text"}
    assert ns["indices"] == 2
    assert ns["aggregatable_indices"] == 1
    assert result["meta"]["conflicted_count"] == 1
    assert result["meta"]["clean_aggregatable_count"] == 0
    assert "conflicted" in result["summary"]


def test_field_mapping_list_mode_truncates_and_flags():
    leaves = {
        f"f{i}": {"full_name": f"f{i}", "mapping": {f"f{i}": {"type": "keyword"}}}
        for i in range(es.FIELD_LIST_MAX + 30)
    }
    result = es._field_mapping(FakeESClient(mapping={"idx-1": {"mappings": leaves}}), 10, {"index_pattern": "idx-*"})
    assert len(result["items"]) == es.FIELD_LIST_MAX
    assert result["meta"]["truncated"] is True
    assert result["meta"]["total_field_paths"] == es.FIELD_LIST_MAX + 30
    assert "截断至前" in result["summary"]


def test_field_mapping_list_mode_empty_pattern_raises_clean():
    # 通配符匹配空集 → 200 空响应（非 404）：明确告知没有可枚举字段
    with pytest.raises(CustomException) as exc:
        es._field_mapping(FakeESClient(mapping={}), 10, {"index_pattern": "nope-*"})
    assert "未枚举到任何字段" in str(exc.value)


def test_field_mapping_passes_star_in_list_mode_and_field_in_single():
    # 接线：list 模式拉 fields="*"（枚举全字段），单字段模式只拉该字段——区分两条路径的关键入参
    client = FakeESClient(
        mapping={"idx-1": {"mappings": {"f": {"full_name": "f", "mapping": {"f": {"type": "keyword"}}}}}}
    )
    es._field_mapping(client, 10, {"index_pattern": "idx-*"})
    assert client.indices.last_fields == "*"
    es._field_mapping(client, 10, {"index_pattern": "idx-*", "field": "f"})
    assert client.indices.last_fields == "f"


def test_field_mapping_list_mode_es5_6_typed_shape():
    # ES5/6 typed: mappings[<doc_type>][<field>]，list 模式须照样枚举到字段（复用 _field_blocks 的两级下钻）
    mapping = {
        "idx-1": {"mappings": {"_doc": {"host": {"full_name": "host", "mapping": {"host": {"type": "keyword"}}}}}}
    }
    result = es._field_mapping(FakeESClient(mapping=mapping), 10, {"index_pattern": "idx-*"})
    assert "host" in [it["field_path"] for it in result["items"]]
    assert result["meta"]["clean_aggregatable_count"] == 1


# ---------------- #6 错误分类（duck-type status_code）----------------


def test_es_query_error_400_is_operation_not_allowed():
    err = FakeESError(
        400,
        error="illegal_argument_exception",
        info={"error": {"root_cause": [{"reason": "Fielddata is disabled on text fields by default"}]}},
    )
    with pytest.raises(CustomException) as exc:
        es._es_query_error("terms_agg_probe", err)
    assert exc.value.data["error_code"] == "OPERATION_NOT_ALLOWED"
    assert "Fielddata" in str(exc.value) or "illegal_argument" in str(exc.value)


def test_es_query_error_connection_is_upstream():
    # 连接错误时 elasticsearch 客户端 status_code 为字符串 'N/A'，不能误判为 400
    with pytest.raises(CustomException) as exc:
        es._es_query_error("cluster_health", FakeESError("N/A"))
    assert exc.value.data["error_code"] == "ES_UPSTREAM_ERROR"


def test_es_query_error_429_is_retryable_upstream():
    # 429（es_rejected / circuit-breaking）是瞬态、可重试，不应被当成确定性 400
    with pytest.raises(CustomException) as exc:
        es._es_query_error("terms_agg_probe", FakeESError(429))
    assert exc.value.data["error_code"] == "ES_UPSTREAM_ERROR"


def test_es_query_error_404_is_index_not_found_not_upstream():
    # 404 = 具体索引不存在：是"目标不存在"（CLI target_not_found，勿重试），不能误判为 ES 不可用可重试。
    err = FakeESError(
        404,
        error="index_not_found_exception",
        info={"error": {"root_cause": [{"reason": "no such index [foo-2026.05.30]"}]}},
    )
    with pytest.raises(CustomException) as exc:
        es._es_query_error("terms_agg_probe", err)
    assert exc.value.data["error_code"] == "INDEX_NOT_FOUND"
    # message 必须带 ES error.type/reason（分类标签只取主因，真相以 message 为准）
    assert "index_not_found_exception" in str(exc.value) or "no such index" in str(exc.value)


def test_es_query_error_timeout_is_query_timeout_with_narrowing_actions():
    # 传输层 ReadTimeout：ES5/6/7 客户端一律 ConnectionTimeout，status_code == 字符串 "TIMEOUT"；
    # 必须落 ES_QUERY_TIMEOUT，next_actions 引导缩到单个具体物理索引，绝非"原样重试同一宽 pattern"。
    err = FakeESError("TIMEOUT", error="read timed out")
    with pytest.raises(CustomException) as exc:
        es._es_query_error("terms_agg_probe", err)
    assert exc.value.data["error_code"] == "ES_QUERY_TIMEOUT"
    actions = " ".join(exc.value.data["next_actions"])
    assert "cat_indices" in actions  # 引导先列具体物理索引名
    assert "具体" in actions and "重试" in actions


def test_es_query_error_timeout_by_classname_fallback():
    # 即使某封装把 status_code 改写，类名含 "Timeout" 也兜住判为超时（不误落 ES_UPSTREAM_ERROR）
    class ConnectionTimeout(Exception):
        status_code = None
        error = "timeout"
        info = None

    with pytest.raises(CustomException) as exc:
        es._es_query_error("terms_agg_probe", ConnectionTimeout())
    assert exc.value.data["error_code"] == "ES_QUERY_TIMEOUT"


# ---------------- #2/#4/#5 terms_agg_probe verdict 链 ----------------


def test_probe_shards_failed_first():
    resp = _search_resp(shards_failed=2, top_buckets=[{"key": MISSING, "doc_count": 100}], top_exists=80)
    out = _run_probe(resp)
    assert "shards_failed=2" in out["summary"]
    assert "强指向 B1" not in out["summary"]  # 分片失败不追加逐索引 B1 后缀


def test_probe_timed_out_is_inconclusive_not_degradation():
    # 超时 + 顶层只回 missing 桶 + exists>0：必须判 inconclusive，绝不说成 doc_values 退化
    resp = _search_resp(timed_out=True, top_buckets=[{"key": MISSING, "doc_count": 100}], top_exists=80)
    out = _run_probe(resp)
    assert "timed_out" in out["summary"]
    assert "退化" not in out["summary"]
    assert "强指向 B1" not in out["summary"]  # 文案"不做 B1/B2 定性"是对的，确定性归因短语才该缺席


def test_probe_total_hits_zero_is_no_sample_not_normal():
    resp = _search_resp(total=0, total_relation="eq", top_buckets=[])
    out = _run_probe(resp)
    assert "无样本" in out["summary"]
    assert "正常" not in out["summary"]


def test_probe_degradation_with_per_index_b1_when_not_truncated():
    resp = _search_resp(
        top_buckets=[{"key": MISSING, "doc_count": 100}],
        top_exists=80,
        by_index=[
            _idx_bucket("idx-a", doc_count=60, probe_buckets=[{"key": MISSING, "doc_count": 60}], exists=40),
            _idx_bucket("idx-b", doc_count=40, probe_buckets=[{"key": "ns1", "doc_count": 40}], exists=40),
        ],
        sum_other=0,
    )
    out = _run_probe(resp)
    assert "退化" in out["summary"]
    assert "B1" in out["summary"]  # 部分索引塌缩 + 部分正常 → 强指向 B1
    overall = out["items"][0]
    assert overall["collapsed_index_count"] == 1
    assert overall["healthy_index_count"] == 1
    assert overall["by_index_truncated"] is False


def test_probe_truncated_forbids_deterministic_attribution():
    # 同样的塌缩形状，但 by_index 被 top-N 截断（sum_other_doc_count>0）→ 禁确定性 B1/B2 归因
    resp = _search_resp(
        top_buckets=[{"key": MISSING, "doc_count": 100}],
        top_exists=80,
        by_index=[
            _idx_bucket("idx-a", doc_count=60, probe_buckets=[{"key": MISSING, "doc_count": 60}], exists=40),
            _idx_bucket("idx-b", doc_count=40, probe_buckets=[{"key": "ns1", "doc_count": 40}], exists=40),
        ],
        sum_other=9999,
    )
    out = _run_probe(resp)
    assert out["items"][0]["by_index_truncated"] is True
    assert "不完整" in out["summary"]
    assert "强指向 B1" not in out["summary"]


# ---------------- #3 node_breaker_stats 累计 vs 瞬时 ----------------


def test_node_breaker_stats_cumulative_not_treated_as_current_pressure():
    node_stats = {
        "nodes": {
            # 历史上 tripped/rejected 过，但当前 heap/old-gen 都低 → 不应判当前压力
            "id1": {
                "name": "n1",
                "breakers": {"parent": {"tripped": 5}, "fielddata": {"tripped": 0}},
                "jvm": {"mem": {"heap_used_percent": 40, "pools": {"old": {"used_in_bytes": 30, "max_in_bytes": 100}}}},
                "thread_pool": {"search": {"queue": 0, "active": 1, "rejected": 12}},
            },
            # 当前 heap 高 → 判当前压力
            "id2": {
                "name": "n2",
                "breakers": {"parent": {"tripped": 0}},
                "jvm": {"mem": {"heap_used_percent": 92, "pools": {"old": {"used_in_bytes": 90, "max_in_bytes": 100}}}},
                "thread_pool": {"search": {"queue": 3, "active": 5, "rejected": 0}},
            },
        }
    }
    out = es._node_breaker_stats(FakeESClient(node_stats=node_stats), 10)
    rows = {item["node"]: item for item in out["items"]}
    # 关键：历史累计 tripped/rejected 不让健康节点被判当前压力
    assert rows["n1"]["under_pressure_now"] is False
    assert rows["n1"]["breaker_tripped_cumulative"] == {"parent": 5, "fielddata": 0}
    assert rows["n1"]["search_rejected_cumulative"] == 12
    assert rows["n2"]["under_pressure_now"] is True  # heap 92% ≥ 85%
    assert out["meta"]["flagged_now"] == 1
    assert "max_old_gen_used_percent" in out["meta"]
    # 不再暴露会被误读为"当前"的旧字段名
    assert "breaker_tripped" not in rows["n1"]


def test_node_breaker_stats_old_gen_max_undefined_is_safe():
    # max_in_bytes 缺失/为 -1 时不除零、不臆断压力
    node_stats = {
        "nodes": {
            "id1": {
                "name": "n1",
                "breakers": {},
                "jvm": {"mem": {"heap_used_percent": 50, "pools": {"old": {"used_in_bytes": 10, "max_in_bytes": -1}}}},
                "thread_pool": {"search": {"queue": 0, "active": 0, "rejected": 0}},
            }
        }
    }
    out = es._node_breaker_stats(FakeESClient(node_stats=node_stats), 10)
    assert out["items"][0]["old_gen_used_percent"] is None
    assert out["items"][0]["under_pressure_now"] is False


# ---------------- 回退后：cat 支持全集群（运维工具设计需求）----------------


def test_cat_segments_allows_whole_cluster():
    client = FakeESClient(cat_rows=[{"index": "i", "segment": "_0"}])
    out = es._cat_passthrough(client, 10, {}, "cat_segments")  # 无 index_pattern
    assert out["operation"] == "cat_segments"
    assert client.cat.segments_called_with_index is None  # 走了全集群分支，未被拒


# ---------------- P1 错误数据透传（api_exception_handler 收窄）----------------


def test_api_exception_handler_passes_structured_error_data():
    exc = CustomException(message="boom", data={"error_code": "ES_UPSTREAM_ERROR", "next_actions": ["retry"]})
    resp = api_exception_handler(exc, None)
    assert resp.data["data"] == {"error_code": "ES_UPSTREAM_ERROR", "next_actions": ["retry"]}


def test_api_exception_handler_does_not_leak_nonwhitelisted_data():
    # 模拟 BKAPIError 把上游原始响应体塞进 data：不含 error_code/next_actions → 不透出
    exc = CustomException(message="boom", data={"code": 500, "message": "raw upstream body", "secret": "x"})
    resp = api_exception_handler(exc, None)
    assert resp.data["data"] == {}
