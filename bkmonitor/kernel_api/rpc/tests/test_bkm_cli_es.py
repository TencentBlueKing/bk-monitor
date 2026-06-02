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

    def get_field_mapping(self, index, fields, params):
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
    # 8 个白名单 operation
    assert len(es.ALLOWED_OPERATIONS) == 8
    assert {c["operation"] for c in es.ES_CAPABILITIES} == set(es.ALLOWED_OPERATIONS)


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
