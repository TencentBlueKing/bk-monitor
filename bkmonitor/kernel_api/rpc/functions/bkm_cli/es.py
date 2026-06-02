"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import logging
from typing import Any, NoReturn

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from metadata.utils import es_tools

logger = logging.getLogger("kernel_api")

# ---- 护栏常量（服务端强制，bkm-cli 端无法绕过）----
ALLOWED_OPERATIONS = (
    "cluster_health",
    "cat_shards",
    "cat_segments",
    "cat_recovery",
    "cat_indices",
    "field_mapping",
    "terms_agg_probe",
    "node_breaker_stats",
)
ES_REQUEST_TIMEOUT = 20  # 传输层 request_timeout（秒）
ES_SEARCH_TIMEOUT = "15s"  # search body timeout，限制聚合耗时
PROBE_TERMS_SIZE = 50  # terms 探针只为判塌缩，不需要全量取值
INDEX_BREAKDOWN_SIZE = 200  # terms_agg_probe 按 _index 下钻的索引数上限
MISSING_PLACEHOLDER = " "  # 对齐 unify-query 的 Missing(" ")
CAT_MAX_ROWS = 500  # cat_* 输出硬上限，超出截断并显式告知（不静默截断）
HEAP_PRESSURE_PERCENT = 85  # 节点 heap 使用率(瞬时)达此阈值视为当前压力（B2 信号）
OLD_GEN_PRESSURE_PERCENT = 85  # 老年代占用率(瞬时)达此阈值视为当前内存压力（比合计 heap 更对准 ordinals 压力）

# 声明式能力目录：扩展 = 加一行；每行自带 required_params + 排障语义（该证据验证 / 不能证明）。
ES_CAPABILITIES: list[dict[str, Any]] = [
    {
        "operation": "cluster_health",
        "status": "active",
        "required_params": [],
        "optional_params": [],
        "evidence": "集群 status / 未分配·恢复中分片数",
        "cannot_prove": "证明不了单索引/单字段层面的聚合可用性",
    },
    {
        "operation": "cat_shards",
        "status": "active",
        "required_params": [],
        "optional_params": ["index_pattern"],
        "evidence": "按分片的 state / 恢复态；定位未分配或异常分片",
        "cannot_prove": "证明不了字段值解析 / 聚合是否退化",
    },
    {
        "operation": "cat_segments",
        "status": "active",
        "required_params": [],
        "optional_params": ["index_pattern"],
        "evidence": "段级信息（committed/searchable/size）；看段合并 / global-ordinals 重建态",
        "cannot_prove": "证明不了某次查询期聚合一定塌缩（需 terms_agg_probe 实测）",
    },
    {
        "operation": "cat_recovery",
        "status": "active",
        "required_params": [],
        "optional_params": ["index_pattern"],
        "evidence": "分片恢复 stage / 进度；看是否处于恢复/重定位窗口",
        "cannot_prove": "证明不了字段聚合可用性",
    },
    {
        "operation": "cat_indices",
        "status": "active",
        "required_params": [],
        "optional_params": ["index_pattern"],
        "evidence": "逐物理索引的 creation.date（滚动时间表）/docs.count/store.size/health；对齐'塌缩→恢复'起止 vs 索引滚动时刻",
        "cannot_prove": "证明不了某索引内字段是否可聚合（需 field_mapping / terms_agg_probe）",
    },
    {
        "operation": "field_mapping",
        "status": "active",
        "required_params": ["index_pattern", "field"],
        "optional_params": [],
        "evidence": "字段 type / doc_values / 是否可聚合",
        "cannot_prove": "证明不了某次查询期分片是否瞬态退化",
    },
    {
        "operation": "terms_agg_probe",
        "status": "active",
        "required_params": ["index_pattern", "field"],
        "optional_params": [],
        "evidence": (
            "size:0 terms 聚合 + 字段 exists 计数 + 按 _index 下钻，并回传 _shards/timed_out；"
            "把塌缩归因到具体物理索引，区分 分片失败 / doc_values·global-ordinals 退化 / 字段在文档里真缺失"
        ),
        "cannot_prove": "证明不了退化的根因时序（段合并 / ordinals 重建），需结合 cat_segments / node_breaker_stats / unify-query trace",
    },
    {
        "operation": "node_breaker_stats",
        "status": "active",
        "required_params": [],
        "optional_params": [],
        "evidence": "逐节点【瞬时】heap%/老年代占用%/search queue（正证当前内存压力=B2），及【自启动累计】breaker tripped/search reject（仅历史信号，两次调用比 delta 才是'当前在 trip'）",
        "cannot_prove": "证明不了历史某时刻的压力（瞬时值只反映当下、累计值非当前；窗口已恢复需 ES 服务端日志）",
    },
]


# ---------------- 入参与客户端解析 ----------------


def _raise(message: str, *, error_code: str | None = None, next_actions: list[str] | None = None) -> NoReturn:
    # error_code: §5.2 结构化错误码（CLUSTER_NOT_FOUND / OPERATION_NOT_ALLOWED / ES_UPSTREAM_ERROR …），
    # 供 bkm-cli 端精确分类。注意：API 角色异常处理器 kernel_api/exceptions.py 默认用 failed() 把 data
    # 置空——已在该处理器补透传 error_code/next_actions（同 PR）。若端到端仍收不到，再排查上游网关是否
    # 在 result:false 响应里抹 data（本地未验证）。
    data: dict[str, Any] = {"next_actions": next_actions or []}
    if error_code:
        data["error_code"] = error_code
    raise CustomException(message=message, data=data)


def _parse_cluster_id(params: dict[str, Any]) -> int:
    raw_cluster_id = params.get("cluster_id")
    if raw_cluster_id in (None, ""):
        _raise("缺少 cluster_id（取自 trace 的 query-storage-id）。")
    try:
        return int(raw_cluster_id)
    except (TypeError, ValueError):
        _raise(f"cluster_id 必须是整数: {raw_cluster_id!r}")


def _load_es_cluster(cluster_id: int):
    """按 cluster_id（全局唯一 PK）反查 ClusterInfo，一次解决两件事：
    - 反查 bk_tenant_id：agent 只持有 trace 里的 cluster_id、不知道租户，租户必须由服务端从集群反查；
      inject_bk_tenant_id 只能从 bk_biz_id/space_uid/... 推租户，推不出 cluster_id，所以不能依赖它注入。
    - 强制 cluster_type == elasticsearch：拒绝把非 ES 存储（kafka/influxdb/...）当 ES 直查，避免对任意
      已注册存储 host 发带凭据的只读外呼。es_diagnose 与 list_es_capabilities 共用同一校验，避免不一致。
    """
    from metadata.models import ClusterInfo

    try:
        cluster = ClusterInfo.objects.get(cluster_id=cluster_id)
    except ClusterInfo.DoesNotExist:
        _raise(
            f"未找到集群: cluster_id={cluster_id}",
            error_code="CLUSTER_NOT_FOUND",
            next_actions=["确认 cluster_id 正确（取自 trace query-storage-id）。"],
        )
    except Exception as error:
        _raise(f"查询集群信息失败: {error}")
    if getattr(cluster, "cluster_type", None) != ClusterInfo.TYPE_ES:
        _raise(
            f"集群 {cluster_id} 不是 ES 集群（cluster_type={getattr(cluster, 'cluster_type', None)}），"
            "ES 只读诊断仅支持 elasticsearch 集群。",
            error_code="OPERATION_NOT_ALLOWED",
            next_actions=["确认 cluster_id 指向 ES 集群（取自 trace 的 ES query-storage-id）。"],
        )
    return cluster


def _resolve_client(params: dict[str, Any]):
    cluster_id = _parse_cluster_id(params)
    cluster = _load_es_cluster(cluster_id)
    try:
        # get_client 内部按 ClusterInfo 解密凭据 + 选版本客户端；凭据/host 全在服务端。
        # 租户取自反查到的集群行（见 _load_es_cluster），不要求调用方传 bk_tenant_id。
        client = es_tools.get_client(bk_tenant_id=cluster.bk_tenant_id, cluster_id=cluster_id)
    except Exception as error:  # 连接构造失败；多版本 ES 客户端异常类型各异
        logger.warning("es-diagnose resolve client failed: cluster_id=%s, error=%s", cluster_id, error)
        _raise(
            f"无法构造 ES 集群 {cluster_id} 的连接: {error}",
            error_code="ES_UPSTREAM_ERROR",
            next_actions=["确认集群在线、凭据有效。"],
        )
    return client, cluster_id


def _require(params: dict[str, Any], key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        _raise(
            f"该 operation 需要参数 {key}。",
            next_actions=["调用 list-es-capabilities 查看每个 operation 的 required_params。"],
        )
    return value


def _extract_total(hits: dict[str, Any]):
    total = hits.get("total") if isinstance(hits, dict) else None
    if isinstance(total, dict):  # ES7+: {"value": N, "relation": ...}
        return total.get("value")
    return total  # ES5/6: int


# ---------------- 各 operation（均只读）----------------


def _cluster_health(client, cluster_id: int) -> dict[str, Any]:
    try:
        health = client.cluster.health(params={"request_timeout": ES_REQUEST_TIMEOUT})
    except Exception as error:
        _raise(f"cluster_health 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    status = health.get("status")
    signals = {
        "status": status,
        "number_of_nodes": health.get("number_of_nodes"),
        "active_primary_shards": health.get("active_primary_shards"),
        "active_shards": health.get("active_shards"),
        "relocating_shards": health.get("relocating_shards"),
        "initializing_shards": health.get("initializing_shards"),
        "unassigned_shards": health.get("unassigned_shards"),
        "timed_out": health.get("timed_out"),
    }
    next_actions = []
    if status and status != "green":
        next_actions.append("集群非 green：用 operation=cat_shards 看未分配/恢复中的分片明细。")
    return {
        "operation": "cluster_health",
        "cluster_id": cluster_id,
        "summary": f"cluster_health: status={status}, unassigned_shards={signals['unassigned_shards']}",
        "items": [signals],
        "next_actions": next_actions,
    }


def _cat_shards(client, cluster_id: int, params: dict[str, Any]) -> dict[str, Any]:
    index_pattern = str(params.get("index_pattern") or "").strip()
    # 显式 h=：cat/shards?format=json 默认列不含 unassigned.reason/details，需指定才会返回
    kwargs = {
        "format": "json",
        "h": "index,shard,prirep,state,docs,store,node,unassigned.reason,unassigned.details",
        "params": {"request_timeout": ES_REQUEST_TIMEOUT},
    }
    try:
        rows = client.cat.shards(index=index_pattern, **kwargs) if index_pattern else client.cat.shards(**kwargs)
    except Exception as error:
        _raise(f"cat_shards 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    rows = rows or []
    state_counts: dict[str, int] = {}
    abnormal: list[dict[str, Any]] = []
    for row in rows:
        state = str(row.get("state") or "")
        state_counts[state] = state_counts.get(state, 0) + 1
        if state and state != "STARTED":
            abnormal.append(
                {
                    "index": row.get("index"),
                    "shard": row.get("shard"),
                    "prirep": row.get("prirep"),
                    "state": state,
                    "node": row.get("node"),
                    "unassigned_reason": row.get("unassigned.reason"),
                    "unassigned_detail": row.get("unassigned.details"),
                }
            )
    truncated = len(abnormal) > CAT_MAX_ROWS
    items = abnormal[:CAT_MAX_ROWS]
    summary = f"cat_shards: 共 {len(rows)} 分片，状态分布 {state_counts}，异常 {len(abnormal)}"
    if truncated:
        summary += f"（异常明细截断至 {CAT_MAX_ROWS}）"
    next_actions = []
    if not abnormal:
        next_actions.append("所有分片 STARTED；若仍误告，用 terms_agg_probe 查聚合期退化。")
    return {
        "operation": "cat_shards",
        "cluster_id": cluster_id,
        "index_pattern": index_pattern or None,
        "summary": summary,
        # 无异常时也回一行汇总，保证 evidence 非空
        "items": items if items else [{"total_shards": len(rows), "state_counts": state_counts}],
        "next_actions": next_actions,
        "meta": {
            "total_shards": len(rows),
            "state_counts": state_counts,
            "abnormal_count": len(abnormal),
            "truncated": truncated,
        },
    }


def _cat_passthrough(client, cluster_id: int, params: dict[str, Any], operation: str) -> dict[str, Any]:
    """cat_segments / cat_recovery：只读 cat 直透，输出按 CAT_MAX_ROWS 截断并显式标注（不静默截断）。"""
    index_pattern = str(params.get("index_pattern") or "").strip()
    cat_fn = {"cat_segments": client.cat.segments, "cat_recovery": client.cat.recovery}[operation]
    kwargs = {"format": "json", "params": {"request_timeout": ES_REQUEST_TIMEOUT}}
    try:
        rows = cat_fn(index=index_pattern, **kwargs) if index_pattern else cat_fn(**kwargs)
    except Exception as error:
        _raise(f"{operation} 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    rows = rows or []
    truncated = len(rows) > CAT_MAX_ROWS
    summary = f"{operation}: 共 {len(rows)} 行" + (f"（截断至 {CAT_MAX_ROWS}）" if truncated else "")
    return {
        "operation": operation,
        "cluster_id": cluster_id,
        "index_pattern": index_pattern or None,
        "summary": summary,
        "items": rows[:CAT_MAX_ROWS] if rows else [{"total_rows": 0}],
        "next_actions": [],
        "meta": {"total_rows": len(rows), "truncated": truncated},
    }


def _cat_indices(client, cluster_id: int, params: dict[str, Any]) -> dict[str, Any]:
    """cat/indices：取每个物理索引的 creation.date（= 一次滚动事件）+ 规模/健康，按创建时间倒序。
    用途：把'塌缩→恢复'窗口的起止时刻去对索引滚动时刻 —— 对得上→B1(映射 race)；对不上→运行时(A/B2)。
    """
    index_pattern = str(params.get("index_pattern") or "").strip()
    kwargs = {
        "format": "json",
        "h": "index,health,status,docs.count,store.size,creation.date,creation.date.string",
        "s": "creation.date:desc",  # 最近滚动在前
        "params": {"request_timeout": ES_REQUEST_TIMEOUT},
    }
    try:
        rows = client.cat.indices(index=index_pattern, **kwargs) if index_pattern else client.cat.indices(**kwargs)
    except Exception as error:
        _raise(f"cat_indices 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    rows = rows or []
    truncated = len(rows) > CAT_MAX_ROWS
    items = [
        {
            "index": row.get("index"),
            "health": row.get("health"),
            "status": row.get("status"),
            "docs_count": row.get("docs.count"),
            "store_size": row.get("store.size"),
            "creation_date": row.get("creation.date"),  # epoch ms
            "creation_date_string": row.get("creation.date.string"),  # ISO8601
        }
        for row in rows[:CAT_MAX_ROWS]
    ]
    summary = f"cat_indices: 共 {len(rows)} 个物理索引（按 creation.date 倒序）" + (
        f"（截断至 {CAT_MAX_ROWS}）" if truncated else ""
    )
    return {
        "operation": "cat_indices",
        "cluster_id": cluster_id,
        "index_pattern": index_pattern or None,
        "summary": summary,
        "items": items if items else [{"total_indices": 0}],
        "next_actions": [
            "把每个'塌缩→恢复'窗口的起止时刻对 creation_date：对得上滚动→B1(映射 race)；对不上→运行时(A/B2)。",
        ],
        "meta": {"total_indices": len(rows), "truncated": truncated},
    }


def _field_blocks(mappings: dict[str, Any], field: str) -> list[dict[str, Any]]:
    """兼容 ES get_field_mapping 的两种响应形状：
    - ES7+(typeless): mappings[field] = {full_name, mapping}
    - ES5/6(typed):   mappings[<doc_type>][field] = {full_name, mapping}
    """
    direct = mappings.get(field)
    if isinstance(direct, dict) and "mapping" in direct:
        return [direct]
    blocks: list[dict[str, Any]] = []
    for type_block in mappings.values():
        if isinstance(type_block, dict):
            candidate = type_block.get(field)
            if isinstance(candidate, dict) and "mapping" in candidate:
                blocks.append(candidate)
    return blocks


def _agg_leaf_row(index_name: str, queried_field: str, field_path: str, definition: dict[str, Any]) -> dict[str, Any]:
    """把单个叶子字段定义解析成可聚合性行。
    - text：默认无 doc_values、不可聚合，除非显式 fielddata=true；
    - 其余(keyword/数值/date)：默认 doc_values=true → 可聚合。
    field_path 为点号全路径（如 namespace / namespace.keyword），agent 可直接拿去 terms_agg_probe。
    """
    field_type = definition.get("type")
    is_text = field_type == "text"
    fielddata = bool(definition.get("fielddata", False))
    doc_values = definition.get("doc_values", not is_text)
    aggregatable = (bool(doc_values) and not is_text) or (is_text and fielddata)
    return {
        "index": index_name,
        "field": queried_field,
        "field_path": field_path,
        "type": field_type,
        "doc_values": doc_values,
        "fielddata": fielddata,
        "indexed": definition.get("index", True),
        "eager_global_ordinals": definition.get("eager_global_ordinals", False),
        "aggregatable": aggregatable,
    }


def _field_mapping(client, cluster_id: int, params: dict[str, Any]) -> dict[str, Any]:
    index_pattern = _require(params, "index_pattern")
    field = _require(params, "field")
    try:
        mapping = client.indices.get_field_mapping(
            index=index_pattern, fields=field, params={"request_timeout": ES_REQUEST_TIMEOUT}
        )
    except Exception as error:
        _raise(f"field_mapping 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    items: list[dict[str, Any]] = []
    for index_name, body in (mapping or {}).items():
        for field_block in _field_blocks(body.get("mappings") or {}, field):
            leaf_mapping = field_block.get("mapping") or {}
            for leaf_name, definition in leaf_mapping.items():
                if not isinstance(definition, dict):
                    continue
                items.append(_agg_leaf_row(index_name, field, leaf_name, definition))
                # multi-field 子字段（如 namespace.keyword）：text 父字段最常见的可聚合“替身”，
                # 必须显式暴露——否则查 text 父字段会误判“不可聚合”，漏掉真正能聚合的 .keyword。
                # 单层即可：ES 不允许 multi-field 嵌套。每个子字段按自身定义重算可聚合性。
                for sub_name, sub_def in (definition.get("fields") or {}).items():
                    if isinstance(sub_def, dict):
                        items.append(_agg_leaf_row(index_name, field, f"{leaf_name}.{sub_name}", sub_def))
    if not items:
        _raise(
            f"在 {index_pattern} 未找到字段 {field} 的 mapping。",
            next_actions=["确认 index_pattern 与 field 正确，或用 cat_shards 确认索引存在。"],
        )
    agg_paths = sorted({str(item["field_path"]) for item in items if item["aggregatable"]})
    types = sorted({str(item["type"]) for item in items})
    return {
        "operation": "field_mapping",
        "cluster_id": cluster_id,
        "index_pattern": index_pattern,
        "field": field,
        "summary": (
            f"field_mapping: {field} → {len(items)} 个字段叶子(含 multi-field 子字段)，type={types}；"
            f"可聚合路径={agg_paths or '无'}"
        ),
        "items": items,
        "next_actions": [
            "聚合用 items[].field_path 中 aggregatable=true 的路径（text 父字段常需改用其 .keyword 子字段）；",
            "选定可聚合路径后，若仍塌缩，用 terms_agg_probe(field=该路径) 抓聚合期 _shards 真相。",
        ],
    }


def _probe_signals(agg_node: dict[str, Any]) -> dict[str, Any]:
    """从带 probe(terms)+field_exists(filter) 的聚合节点提取塌缩信号（顶层与逐索引共用）。"""
    buckets = ((agg_node.get("probe") or {}).get("buckets")) or []
    exists_count = (agg_node.get("field_exists") or {}).get("doc_count")
    missing_doc_count = None
    non_missing = 0
    for bucket in buckets:
        if bucket.get("key") == MISSING_PLACEHOLDER:
            missing_doc_count = bucket.get("doc_count")
        else:
            non_missing += 1
    only_missing_bucket = bool(buckets) and non_missing == 0 and missing_doc_count is not None
    return {
        "buckets_returned": len(buckets),
        "non_missing_buckets": non_missing,
        "missing_bucket_doc_count": missing_doc_count,
        "field_exists_doc_count": exists_count,
        "only_missing_bucket": only_missing_bucket,
    }


def _terms_agg_probe(client, cluster_id: int, params: dict[str, Any]) -> dict[str, Any]:
    index_pattern = _require(params, "index_pattern")
    field = _require(params, "field")
    sub_aggs = {
        "probe": {"terms": {"field": field, "size": PROBE_TERMS_SIZE, "missing": MISSING_PLACEHOLDER}},
        # exists 计数：区分“字段真缺失/为空”（exists=0）与“有值却聚不出 = doc_values/ordinals 退化”（exists>0）。
        "field_exists": {"filter": {"exists": {"field": field}}},
    }
    body = {
        "size": 0,  # 护栏：恒 size:0，绝不返回原始文档（消除跨租户读原文）
        "timeout": ES_SEARCH_TIMEOUT,
        "aggs": {
            **sub_aggs,  # 顶层（整 pattern 汇总，保留原有信号）
            # 按物理索引下钻（_index 元字段恒可聚合）：把塌缩归因到具体索引——
            # 部分索引塌缩+部分正常=强指向 B1 结构性坏索引；全塌=更像运行时(A/B2)。
            "by_index": {"terms": {"field": "_index", "size": INDEX_BREAKDOWN_SIZE}, "aggs": sub_aggs},
        },
    }
    try:
        res = client.search(index=index_pattern, body=body, params={"request_timeout": ES_REQUEST_TIMEOUT})
    except Exception as error:
        _raise(f"terms_agg_probe 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    shards = res.get("_shards") or {}
    hits = res.get("hits") or {}
    total_hits = _extract_total(hits)
    raw_total = hits.get("total")
    total_hits_relation = raw_total.get("relation") if isinstance(raw_total, dict) else "eq"  # ES7+ 可能是 gte 上限
    aggs = res.get("aggregations") or {}
    top = _probe_signals(aggs)
    exists_count = top["field_exists_doc_count"]
    only_missing_bucket = top["only_missing_bucket"]
    shards_failed = shards.get("failed") or 0
    timed_out = bool(res.get("timed_out"))

    # 逐索引归因：把塌缩落到具体物理索引
    per_index: list[dict[str, Any]] = []
    collapsed_indices: list[str] = []  # exists>0 却只回 missing 桶（聚合塌缩）
    healthy_indices: list[str] = []  # 有非空桶（正常）
    absent_indices: list[str] = []  # 只回 missing 桶且 exists=0（字段真缺失，非退化 → 指向 ②）
    for idx_bucket in ((aggs.get("by_index") or {}).get("buckets")) or []:
        idx_name = idx_bucket.get("key")
        idx_sig = _probe_signals(idx_bucket)
        idx_sig["index"] = idx_name
        idx_sig["doc_count"] = idx_bucket.get("doc_count")
        per_index.append(idx_sig)
        if idx_sig["only_missing_bucket"] and (idx_sig["field_exists_doc_count"] or 0) > 0:
            collapsed_indices.append(idx_name)
        elif idx_sig["only_missing_bucket"] and idx_sig["field_exists_doc_count"] == 0:
            absent_indices.append(idx_name)
        elif idx_sig["non_missing_buckets"] > 0:
            healthy_indices.append(idx_name)

    overall = {
        "scope": "overall",
        "shards_total": shards.get("total"),
        "shards_successful": shards.get("successful"),
        "shards_failed": shards_failed,
        "shards_skipped": shards.get("skipped"),
        "timed_out": timed_out,
        "total_hits": total_hits,
        "total_hits_relation": total_hits_relation,
        "field_exists_doc_count": exists_count,
        "buckets_returned": top["buckets_returned"],
        "non_missing_buckets": top["non_missing_buckets"],
        "missing_bucket_doc_count": top["missing_bucket_doc_count"],
        "only_missing_bucket": only_missing_bucket,
        "collapsed_index_count": len(collapsed_indices),
        "healthy_index_count": len(healthy_indices),
        "absent_index_count": len(absent_indices),
        "shard_failures": (shards.get("failures") or [])[:5],
    }

    if shards_failed:
        verdict = f"shards_failed={shards_failed} → 静默退化源于分片失败；看 shard_failures / 跑 cat_shards。"
    elif only_missing_bucket:
        # 关键：只回单一 missing 桶时，必须用 exists 计数把“真退化”与“真缺失”分开，不能一律定性为退化。
        if (exists_count or 0) > 0:
            verdict = (
                f"分片全成功，且有 {exists_count} 篇文档该字段 exists，但 terms({field}) 只回单一 missing 桶 → "
                "doc_values/global-ordinals 退化（非分片失败，典型聚合塌缩签名）。"
            )
        elif exists_count == 0:
            verdict = (
                f"terms({field}) 只回 missing 桶且 exists 计数=0 → 该字段在匹配文档里确实缺失/为空，"
                "属正常（非聚合退化）；核对 field 名 / index_pattern / 时间窗，或用 field_mapping 确认字段存在。"
            )
        else:  # exists_count 缺失（非预期），不臆断退化
            verdict = (
                f"terms({field}) 只回单一 missing 桶，但 exists 计数缺失，无法区分退化 vs 真缺失；"
                "结合 field_mapping / cat_segments 复核。"
            )
    elif timed_out:
        verdict = "timed_out=true → 聚合在限定时间内未完成，结果可能不完整（非确定性塌缩）。"
    elif (total_hits or 0) > 0 and top["buckets_returned"] == 0:
        verdict = f"total_hits>0 但 terms({field}) 返回 0 桶 → 异常退化 / 字段聚合不可用。"
    else:
        verdict = f"terms({field}) 正常：{top['non_missing_buckets']} 个非空桶，未见塌缩。"

    # 逐索引归因（B1 结构性坏索引 vs 运行时 A/B2 的判别加成）。
    # 关键 gate：仅在「非分片失败 且 非超时」时追加——否则 shards_failed/timed_out 已定因(A/超时)，
    # 此时某索引"看起来塌缩"只是失败分片没贡献桶（A 的逐索引表现），强追加 B1 后缀会与主判矛盾（§8.2 指纹表）。
    if not shards_failed and not timed_out:
        if collapsed_indices and healthy_indices:
            verdict += (
                f" 【按索引下钻】塌缩集中在 {len(collapsed_indices)} 个索引（如 {collapsed_indices[:3]}），"
                f"另有 {len(healthy_indices)} 个索引正常 → 强指向 B1 结构性坏索引："
                "用 cat_indices 对这些索引的 creation_date、用 field_mapping 核其字段 type/doc_values。"
            )
        elif collapsed_indices and not healthy_indices:
            verdict += (
                f" 【按索引下钻】{len(collapsed_indices)} 个索引全部塌缩 → 非单一坏索引，"
                "更像运行时退化(A/B2)：跑 node_breaker_stats，并看 shards_failed/timed_out。"
            )

    return {
        "operation": "terms_agg_probe",
        "cluster_id": cluster_id,
        "index_pattern": index_pattern,
        "field": field,
        "summary": verdict,
        "items": [overall] + per_index[:CAT_MAX_ROWS],
        "next_actions": [
            "对照 field_mapping 确认字段 type/doc_values；",
            "塌缩集中在部分索引→cat_indices 对滚动时刻(B1)；全索引塌缩→node_breaker_stats 看压力(B2)；",
            "若复发，结合 unify-query trace 的 shards_failed/timed_out 交叉印证。",
        ],
    }


def _node_breaker_stats(client, cluster_id: int) -> dict[str, Any]:
    """node stats，区分两类信号，避免把历史当当前：
    - 【瞬时】heap% / 老年代占用% / search queue·active —— 反映查询时刻状态，用于正证“当前”内存压力(B2)；
    - 【自节点启动累计】breaker tripped / search rejected —— 单调递增、仅重启归零，是历史信号，
      不代表当前；要判“当前是否在 trip/reject”，须在塌缩窗口内两次调用本 op 比 delta。
    当前压力判定(under_pressure_now)只用瞬时值，且以老年代占用为主（比合计 heap 更对准 ordinals/fielddata 内存压力）。
    """
    try:
        stats = client.nodes.stats(metric="breaker,jvm,thread_pool", params={"request_timeout": ES_REQUEST_TIMEOUT})
    except Exception as error:
        _raise(f"node_breaker_stats 查询失败: {error}", error_code="ES_UPSTREAM_ERROR")
    nodes = (stats or {}).get("nodes") or {}
    items: list[dict[str, Any]] = []
    flagged = 0  # 当前(瞬时)压力节点数
    breaker_tripped_cumulative_total: dict[str, int] = {}  # 自启动累计
    max_heap = None
    max_old_gen = None
    for node in nodes.values():
        breakers = node.get("breakers") or {}
        jvm_mem = (node.get("jvm") or {}).get("mem") or {}
        heap_pct = jvm_mem.get("heap_used_percent")  # 瞬时（young+old 合计，受 GC 周期影响大）
        old_pool = (jvm_mem.get("pools") or {}).get("old") or {}
        old_used, old_max = old_pool.get("used_in_bytes"), old_pool.get("max_in_bytes")
        # 瞬时老年代占用率；max 可能为 -1/缺失（如部分 GC 配置），此时置 None 不臆断
        old_gen_pct = round(old_used / old_max * 100, 1) if (old_used is not None and old_max and old_max > 0) else None
        search_pool = (node.get("thread_pool") or {}).get("search") or {}
        # parent/fielddata/request/in_flight_requests/accounting 的 tripped 全是自启动累计
        tripped_cumulative = {name: (b or {}).get("tripped") for name, b in breakers.items()}
        for name, value in tripped_cumulative.items():
            breaker_tripped_cumulative_total[name] = breaker_tripped_cumulative_total.get(name, 0) + (value or 0)
        if heap_pct is not None:
            max_heap = heap_pct if max_heap is None else max(max_heap, heap_pct)
        if old_gen_pct is not None:
            max_old_gen = old_gen_pct if max_old_gen is None else max(max_old_gen, old_gen_pct)
        # 当前压力只看瞬时值（heap/old-gen）。search queue/active 仅作观测输出，不进判定——
        # 默认 queue 容量上千，繁忙集群采样瞬间 queue>0 是常态，当阈值会换一种形式误报。
        under_pressure_now = (heap_pct or 0) >= HEAP_PRESSURE_PERCENT or (old_gen_pct or 0) >= OLD_GEN_PRESSURE_PERCENT
        if under_pressure_now:
            flagged += 1
        items.append(
            {
                "node": node.get("name"),
                # —— 瞬时（当前压力判据 / 观测）——
                "heap_used_percent": heap_pct,
                "old_gen_used_percent": old_gen_pct,
                "search_queue": search_pool.get("queue"),
                "search_active": search_pool.get("active"),
                "under_pressure_now": under_pressure_now,
                # —— 自节点启动累计（历史信号，非当前；需两次调用比 delta）——
                "breaker_tripped_cumulative": tripped_cumulative,
                "search_rejected_cumulative": search_pool.get("rejected"),
            }
        )
    boundary = "瞬时值只反映采样当下；已恢复的历史窗口需 ES 服务端日志取证。"
    if flagged:
        verdict = (
            f"{flagged}/{len(items)} 个节点【当前】瞬时压力（heap≥{HEAP_PRESSURE_PERCENT}% 或 "
            f"老年代≥{OLD_GEN_PRESSURE_PERCENT}%）→ 支持 B2：运行时压力致 global-ordinals 重建失败/超时；"
            f"结合 terms_agg_probe(timed_out) 与塌缩窗口时刻确认。{boundary}"
        )
    else:
        verdict = (
            f"{len(items)} 个节点【当前】无瞬时压力（heap<{HEAP_PRESSURE_PERCENT}% 且 "
            f"老年代<{OLD_GEN_PRESSURE_PERCENT}%）→ 当前不支持 B2 压力假设。{boundary}"
        )
    if any(v for v in breaker_tripped_cumulative_total.values()):
        verdict += (
            " 注：breaker tripped 为【自启动累计】(非当前，parent breaker 尤其常 trip)——"
            "要判'当前是否在 trip'，在塌缩窗口内隔数秒两次调用本 op 比 breaker_tripped_cumulative 的 delta。"
        )
    return {
        "operation": "node_breaker_stats",
        "cluster_id": cluster_id,
        "summary": verdict,
        "items": items if items else [{"node_count": 0}],
        "next_actions": [
            "当前压力看瞬时值 heap_used_percent / old_gen_used_percent（search_queue/active 仅观测）；",
            "breaker_tripped_cumulative / search_rejected_cumulative 是自启动累计，"
            "塌缩窗口内两次调用比 delta 才是'当前在 trip/reject'。",
        ],
        "meta": {
            "node_count": len(items),
            "flagged_now": flagged,
            "breaker_tripped_cumulative_total": breaker_tripped_cumulative_total,
            "max_heap_used_percent": max_heap,
            "max_old_gen_used_percent": max_old_gen,
        },
    }


# ---------------- 对外 handler ----------------


def es_diagnose(params: dict[str, Any]) -> dict[str, Any]:
    operation = str(params.get("operation") or "").strip()
    if operation not in ALLOWED_OPERATIONS:
        _raise(
            f"不支持的 operation: {operation or '(空)'}。允许: {', '.join(ALLOWED_OPERATIONS)}。",
            error_code="OPERATION_NOT_ALLOWED",
            next_actions=["调用 list-es-capabilities 查看本集群可用 operation 及其 required_params。"],
        )
    client, cluster_id = _resolve_client(params)
    if operation == "cluster_health":
        return _cluster_health(client, cluster_id)
    if operation == "cat_shards":
        return _cat_shards(client, cluster_id, params)
    if operation == "cat_indices":
        return _cat_indices(client, cluster_id, params)
    if operation in ("cat_segments", "cat_recovery"):
        return _cat_passthrough(client, cluster_id, params, operation)
    if operation == "field_mapping":
        return _field_mapping(client, cluster_id, params)
    if operation == "node_breaker_stats":
        return _node_breaker_stats(client, cluster_id)
    return _terms_agg_probe(client, cluster_id, params)


def list_es_capabilities(params: dict[str, Any]) -> dict[str, Any]:
    # 与 es_diagnose 共用 cluster_id → 租户反查 + ES 类型校验（_load_es_cluster），保证两条路径行为一致。
    cluster_id = _parse_cluster_id(params)
    cluster = _load_es_cluster(cluster_id)
    es_version = getattr(cluster, "version", None)
    return {
        "cluster_id": cluster_id,
        "es_version": es_version,
        "count": len(ES_CAPABILITIES),
        "items": ES_CAPABILITIES,
        "summary": f"集群 {cluster_id}（ES {es_version or '?'}）可用 {len(ES_CAPABILITIES)} 个只读诊断 operation",
        "next_actions": ["选 items[].operation（仅 status=active 可跑），按 required_params 调用 es-diagnose。"],
    }


# ---------------- 注册 ----------------

KernelRPCRegistry.register_function(
    func_name="bkm_cli.es_diagnose",
    summary="ES 只读诊断（cluster_health/cat_shards/cat_segments/cat_recovery/cat_indices/field_mapping/terms_agg_probe/node_breaker_stats）",
    description=(
        "经 metadata ClusterInfo 解析集群后受限只读调用 ES：仅 8 个白名单 operation，"
        "search 恒 size:0，预解析 _shards/timed_out/逐索引归因/节点压力等排障信号。"
    ),
    handler=es_diagnose,
    params_schema={
        "cluster_id": "ES 集群 id（取自 trace query-storage-id）",
        "operation": (
            "cluster_health | cat_shards | cat_segments | cat_recovery | cat_indices | "
            "field_mapping | terms_agg_probe | node_breaker_stats"
        ),
        "index_pattern": "field_mapping / terms_agg_probe 必填；cat_* 可选",
        "field": "field_mapping / terms_agg_probe 必填",
    },
    example_params={
        "cluster_id": "10",
        "operation": "terms_agg_probe",
        "index_pattern": "bklog_*",
        "field": "namespace",
    },
)

KernelRPCRegistry.register_function(
    func_name="bkm_cli.list_es_capabilities",
    summary="列出某 ES 集群可用的只读诊断 operation（版本感知）",
    description="按 cluster_id 返回服务端发布的 ES 诊断 operation 目录及 required_params、status；供 agent 自发现。",
    handler=list_es_capabilities,
    params_schema={"cluster_id": "ES 集群 id（取自 trace query-storage-id）"},
    example_params={"cluster_id": "10"},
)

BkmCliOpRegistry.register(
    op_id="es-diagnose",
    func_name="bkm_cli.es_diagnose",
    summary="ES 只读诊断（经 metadata proxy，bkm-cli 不持凭据）",
    description=(
        "受限只读 ES 诊断：cluster_health/cat_shards/cat_segments/cat_recovery/cat_indices/"
        "field_mapping/terms_agg_probe/node_breaker_stats，search 恒 size:0，"
        "定位聚合塌缩 / 分片静默退化类误告（含逐索引归因 + 滚动时间表 + 节点压力）。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["es", "readonly", "diagnose"],
    params_schema={
        "cluster_id": "string",
        "operation": "string",
        "index_pattern": "string",
        "field": "string",
    },
    example_params={
        "cluster_id": "10",
        "operation": "terms_agg_probe",
        "index_pattern": "bklog_*",
        "field": "namespace",
    },
)

BkmCliOpRegistry.register(
    op_id="list-es-capabilities",
    func_name="bkm_cli.list_es_capabilities",
    summary="发现某 ES 集群可用的只读诊断能力（版本感知）",
    description="供 agent 在不知道某集群可用 ES operation 时自动发现服务端目录。",
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["es", "readonly", "discovery"],
    params_schema={"cluster_id": "string"},
    example_params={"cluster_id": "10"},
)
