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
    "field_mapping",
    "terms_agg_probe",
)
ES_REQUEST_TIMEOUT = 20  # 传输层 request_timeout（秒）
ES_SEARCH_TIMEOUT = "15s"  # search body timeout，限制聚合耗时
PROBE_TERMS_SIZE = 50  # terms 探针只为判塌缩，不需要全量取值
MISSING_PLACEHOLDER = " "  # 对齐 unify-query 的 Missing(" ")
CAT_MAX_ROWS = 500  # cat_* 输出硬上限，超出截断并显式告知（不静默截断）

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
            "size:0 terms 聚合 + 字段 exists 计数，并回传 _shards/timed_out；三方对照区分"
            "分片失败 / doc_values·global-ordinals 退化 / 字段在文档里真缺失"
        ),
        "cannot_prove": "证明不了退化的根因时序（段合并 / ordinals 重建），需结合 cat_segments / unify-query trace",
    },
]


# ---------------- 入参与客户端解析 ----------------


def _raise(message: str, *, error_code: str | None = None, next_actions: list[str] | None = None) -> NoReturn:
    # error_code: §5.2 结构化错误码（CLUSTER_NOT_FOUND / OPERATION_NOT_ALLOWED / ES_UPSTREAM_ERROR …），
    # 供 bkm-cli 端精确分类。注意：当前 apigateway 在 result:false 响应里会抹掉 data，该字段短期到不了
    # 客户端（见 es-readonly spec 的 error-path follow-up）；契约已就位，网关透传 data 后自动生效。
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
                field_type = definition.get("type")
                # keyword/数值/日期默认 doc_values=true；text 默认 false（不可聚合，除非 fielddata）
                doc_values = definition.get("doc_values", field_type != "text")
                items.append(
                    {
                        "index": index_name,
                        "field": field,
                        "leaf": leaf_name,
                        "type": field_type,
                        "doc_values": doc_values,
                        "indexed": definition.get("index", True),
                        "eager_global_ordinals": definition.get("eager_global_ordinals", False),
                        "aggregatable": bool(doc_values) and field_type != "text",
                    }
                )
    if not items:
        _raise(
            f"在 {index_pattern} 未找到字段 {field} 的 mapping。",
            next_actions=["确认 index_pattern 与 field 正确，或用 cat_shards 确认索引存在。"],
        )
    types = sorted({str(item["type"]) for item in items})
    return {
        "operation": "field_mapping",
        "cluster_id": cluster_id,
        "index_pattern": index_pattern,
        "field": field,
        "summary": f"field_mapping: {field} 在 {len(items)} 个索引映射中 type={types}",
        "items": items,
        "next_actions": [
            "若 type=keyword 且 doc_values=true 但 terms 仍塌缩，用 terms_agg_probe 抓聚合期 _shards 真相。"
        ],
    }


def _terms_agg_probe(client, cluster_id: int, params: dict[str, Any]) -> dict[str, Any]:
    index_pattern = _require(params, "index_pattern")
    field = _require(params, "field")
    body = {
        "size": 0,  # 护栏：恒 size:0，绝不返回原始文档（消除跨租户读原文）
        "timeout": ES_SEARCH_TIMEOUT,
        "aggs": {
            "probe": {"terms": {"field": field, "size": PROBE_TERMS_SIZE, "missing": MISSING_PLACEHOLDER}},
            # exists 计数：同一 size:0 查询内多算一个 filter 子聚合（无额外请求），用于区分
            # “字段在文档里真缺失/为空”（exists=0）与“字段有值却聚不出 = doc_values/ordinals 退化”（exists>0）。
            "field_exists": {"filter": {"exists": {"field": field}}},
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
    buckets = ((aggs.get("probe") or {}).get("buckets")) or []
    exists_count = (aggs.get("field_exists") or {}).get("doc_count")  # 匹配文档中该字段 exists 的篇数
    missing_doc_count = None
    non_missing = 0
    for bucket in buckets:
        if bucket.get("key") == MISSING_PLACEHOLDER:
            missing_doc_count = bucket.get("doc_count")
        else:
            non_missing += 1
    only_missing_bucket = bool(buckets) and non_missing == 0 and missing_doc_count is not None
    shards_failed = shards.get("failed") or 0
    timed_out = bool(res.get("timed_out"))
    signals = {
        "shards_total": shards.get("total"),
        "shards_successful": shards.get("successful"),
        "shards_failed": shards_failed,
        "shards_skipped": shards.get("skipped"),
        "timed_out": timed_out,
        "total_hits": total_hits,
        "total_hits_relation": total_hits_relation,
        "field_exists_doc_count": exists_count,
        "buckets_returned": len(buckets),
        "non_missing_buckets": non_missing,
        "missing_bucket_doc_count": missing_doc_count,
        "only_missing_bucket": only_missing_bucket,
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
    elif (total_hits or 0) > 0 and len(buckets) == 0:
        verdict = f"total_hits>0 但 terms({field}) 返回 0 桶 → 异常退化 / 字段聚合不可用。"
    else:
        verdict = f"terms({field}) 正常：{non_missing} 个非空桶，未见塌缩。"
    return {
        "operation": "terms_agg_probe",
        "cluster_id": cluster_id,
        "index_pattern": index_pattern,
        "field": field,
        "summary": verdict,
        "items": [signals],
        "next_actions": [
            "对照 field_mapping 确认字段 type/doc_values；",
            "若复发，结合 unify-query trace 的 shards_failed/timed_out（需求①）交叉印证。",
        ],
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
    if operation in ("cat_segments", "cat_recovery"):
        return _cat_passthrough(client, cluster_id, params, operation)
    if operation == "field_mapping":
        return _field_mapping(client, cluster_id, params)
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
    summary="ES 只读诊断（cluster_health/cat_shards/cat_segments/cat_recovery/field_mapping/terms_agg_probe）",
    description=(
        "经 metadata ClusterInfo 解析集群后受限只读调用 ES：仅 6 个白名单 operation，"
        "search 恒 size:0，预解析 _shards/timed_out 等排障信号。"
    ),
    handler=es_diagnose,
    params_schema={
        "cluster_id": "ES 集群 id（取自 trace query-storage-id）",
        "operation": "cluster_health | cat_shards | cat_segments | cat_recovery | field_mapping | terms_agg_probe",
        "index_pattern": "field_mapping / terms_agg_probe 必填",
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
        "受限只读 ES 诊断：cluster_health/cat_shards/cat_segments/cat_recovery/field_mapping/terms_agg_probe，"
        "search 恒 size:0，定位聚合塌缩 / 分片静默退化类误告。"
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
