"""事件、告警和执行实例的只读 Elasticsearch 查询。"""

import json
from functools import partial
from pathlib import Path

from django.conf import settings
from jsonschema import validate, ValidationError

from bkmonitor.documents.action import ActionInstanceDocument
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.event import EventDocument
from bkmonitor.documents.log import AlertLog
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response

DOCUMENTS = {"event": EventDocument, "alert": AlertDocument, "action": ActionInstanceDocument}
CONTRACTS = json.loads(Path(__file__).with_name("alarm_query_schema.json").read_text())
SEARCH_KEYS = {
    "query",
    "aggs",
    "aggregations",
    "sort",
    "_source",
    "from",
    "size",
    "track_total_hits",
    "post_filter",
    "highlight",
    "fields",
    "search_after",
    "min_score",
    "track_scores",
    "collapse",
}


def fail(message):
    raise CustomException(message=message)


def validate_dsl(node, tenant_scoped):
    # 查询体不能指定其他索引（如 terms lookup、indexed_shape、MLT 文档引用）。
    if isinstance(node, list):
        for item in node:
            validate_dsl(item, tenant_scoped)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key in {
                "index",
                "_index",
                "indexed_shape",
                "percolate",
                "script",
                "scripted_metric",
                "script_score",
                "more_like_this",
                "terms_lookup",
                "significant_terms",
                "significant_text",
            }:
                fail(f"不支持跨索引、脚本或背景数据查询：{key}")
            if tenant_scoped and key == "global":
                fail("当前租户查询不支持 global 聚合")
            validate_dsl(value, tenant_scoped)


def filter_clause(item):
    key, op, value = item["field"], item["op"], item.get("value")
    if op in ("eq", "ne"):
        if value is None or isinstance(value, dict):
            fail("精确匹配需要一个值或值列表")
        clause = {"terms" if isinstance(value, list) else "term": {key: value}}
    elif op == "contains":
        if not isinstance(value, str):
            fail("包含匹配需要文本")
        clause = {"match_phrase": {key: value}}
    elif op == "range":
        if not isinstance(value, dict) or not value:
            fail("范围需要起点或终点")
        clause = {"range": {key: value}}
    else:
        clause = {"exists": {"field": key}}
    return {"bool": {"must_not": [clause]}} if op in ("ne", "missing") else clause


def search_body(p):
    body = dict(p.get("dsl", {}))
    if set(body) - SEARCH_KEYS:
        fail("不支持的 DSL 顶层字段：" + ", ".join(sorted(set(body) - SEARCH_KEYS)))
    scoped = settings.ENABLE_MULTI_TENANT_MODE and p["bk_tenant_id"] != "__all__"
    validate_dsl(body, scoped)
    filters = [filter_clause(item) for item in p.get("filters", [])]
    if scoped:
        filters.append({"term": {"bk_tenant_id": p["bk_tenant_id"]}})
    query = body.pop("query", {"match_all": {}})
    if p.get("query_string"):
        query = {"query_string": {"query": p["query_string"]}}
    body["query"] = {"bool": {"must": [query], "filter": filters}}
    return body


def inventory(client, pattern):
    return client.indices.get_alias(index=pattern, ignore_unavailable=True, allow_no_indices=True)


def select_target(client, pattern, target):
    if not target:
        return pattern
    indices = inventory(client, pattern)
    if target in indices:
        return target
    if any(target in v["aliases"] for v in indices.values()):
        resolved = client.indices.get_alias(name=target)
        if set(resolved) <= indices.keys():
            return target
    fail("所选索引或别名不属于该资源")


def search(client, target, body, warnings):
    response = client.search(index=target, body=body, ignore_unavailable=True, request_timeout=30)
    if response.get("timed_out") or response.get("_shards", {}).get("failed"):
        warnings.append({"code": "PARTIAL_SEARCH", "message": "查询超时或部分分片失败，结果可能不完整"})
    return response


def paginate(body, p):
    size = p.get("page_size", 20)
    body.setdefault("from", (p.get("page", 1) - 1) * size)
    body.setdefault("size", size)
    if (
        not all(type(body[k]) is int and body[k] >= 0 for k in ("size", "from"))
        or body["size"] > 100
        or body["from"] + body["size"] > 10000
    ):
        fail("单页最多 100 条，分页窗口最多 10000 条，请缩小检索范围")


def aggregate(client, target, p, warnings):
    body = search_body(p)
    # 可视化计数使用命中条件，忽略 DSL 中用于命中列表展示的分页与聚合。
    query = body["query"]
    if "post_filter" in body:
        query = {"bool": {"must": [query], "filter": [body["post_filter"]]}}
    body = {
        "query": query,
        "size": 0,
        "track_total_hits": True,
        **({"min_score": body["min_score"]} if "min_score" in body else {}),
    }
    kind, fields, size = p["kind"], p.get("fields", []), p.get("size", 20)
    if kind in ("groups", "top") and (not fields or len(set(fields)) != len(fields)):
        fail("请选择不重复的分组字段")
    if kind == "groups":
        group = {"size": size, "sources": [{f: {"terms": {"field": f}}} for f in fields]}
        if p.get("after"):
            group["after"] = p["after"]
        body["aggs"] = {"counts": {"composite": group}}
    elif kind == "top":
        terms = [{"field": f} for f in fields]
        body["aggs"] = {
            "counts": {"terms": {**terms[0], "size": size}}
            if len(fields) == 1
            else {"multi_terms": {"terms": terms, "size": size}}
        }
    elif kind == "trend":
        body["aggs"] = {
            "counts": {
                "date_histogram": {
                    "field": p.get("time_field", "create_time"),
                    "fixed_interval": p.get("interval", "1h"),
                    "min_doc_count": 1,
                }
            }
        }
    result = search(client, target, body, warnings)
    total = result["hits"]["total"]
    counts = result.get("aggregations", {}).get("counts", {})
    buckets = []
    for bucket in counts.get("buckets", []):
        key = bucket["key"]
        if kind == "trend":
            key = {p.get("time_field", "create_time"): key / 1000}
        elif kind == "top":
            key = dict(zip(fields, key if isinstance(key, list) else [key]))
        buckets.append({"key": key, "count": bucket["doc_count"]})
    return {
        "total": total["value"] if isinstance(total, dict) else total,
        "buckets": buckets,
        **({"after": counts["after_key"]} if "after_key" in counts else {}),
    }


def nested_paths(properties, prefix=""):
    for name, definition in properties.items():
        path = prefix + name
        if definition.get("type") == "nested":
            yield path + "."
        elif "properties" in definition:
            yield from nested_paths(definition["properties"], path + ".")


def run(op, p, warnings):
    doc = DOCUMENTS[p["resource"]]
    client = doc._index._get_connection()
    pattern = doc.build_all_indices_read_index_name()
    target = select_target(client, pattern, p.get("target"))
    if op == "fields":
        caps = client.field_caps(index=target, fields="*", ignore_unavailable=True)["fields"]
        nested = tuple(nested_paths(doc._doc_type.mapping.to_dict().get("properties", {})))
        items = []
        for name, types in sorted(caps.items()):
            if name.startswith("_"):
                continue
            values = list(types.values())
            # Nested 字段需要 nested 查询与聚合，留给 DSL 输入。
            selectable = len(values) == 1 and not name.startswith(nested) and not ({"nested", "object"} & types.keys())
            items.append(
                {
                    "name": name,
                    "type": "|".join(types),
                    "searchable": selectable and values[0]["searchable"],
                    "aggregatable": selectable and values[0]["aggregatable"],
                }
            )
        return {"items": items}
    if op in ("indices", "aliases"):
        aliases = inventory(client, target)
        try:
            stats = {
                r["index"]: r
                for r in client.cat.indices(index=target, format="json", h="index,health,docs.count,store.size")
            }
        except Exception as exc:
            stats = {}
            warnings.append({"code": "INDEX_STATS_UNAVAILABLE", "message": str(exc)})
        rows = [
            {
                "name": k,
                "aliases": sorted(v["aliases"]),
                "health": stats.get(k, {}).get("health"),
                "docs": stats.get(k, {}).get("docs.count"),
                "size": stats.get(k, {}).get("store.size"),
            }
            for k, v in sorted(aliases.items())
        ]
        if op == "aliases":
            rows = [{**row, "aliases": [alias]} for row in rows for alias in row["aliases"]]
        size = p.get("page_size", 20)
        start = (p.get("page", 1) - 1) * size
        data = {"total": len(rows), "items": rows[start : start + size]}
        if p.get("include_mapping") and target in aliases:
            data["mapping"] = client.indices.get_mapping(index=target)[target]["mappings"]
        return data
    if op == "aggregate":
        return aggregate(client, target, p, warnings)
    body = search_body(p)
    if op in ("detail", "alert_logs"):
        if op == "alert_logs" and doc != AlertDocument:
            fail("流转日志仅支持告警")
        body["query"]["bool"]["filter"].append({"ids": {"values": [p.get("id") or p["alert_id"]]}})
        hit = search(client, target, {**body, "size": 1}, warnings)["hits"]["hits"]
        if not hit:
            fail("当前查询范围内未找到记录")
        if op == "detail":
            return hit[0]
        clauses = [{"term": {"alert_id": p["alert_id"]}}]
        if p.get("op_type"):
            clauses.append({"term": {"op_type": p["op_type"]}})
        bounds = {k: p[v] for k, v in [("gte", "start"), ("lte", "end")] if v in p}
        if bounds:
            clauses.append({"range": {"create_time": bounds}})
        body = {"query": {"bool": {"filter": clauses}}, "sort": [{"create_time": "desc"}]}
        target = AlertLog.build_all_indices_read_index_name()
        client = AlertLog._index._get_connection()
    if "dsl" not in p:
        body.setdefault("sort", [{p.get("sort_field", "create_time"): "desc" if p.get("descending", True) else "asc"}])
    paginate(body, p)
    return search(client, target, body, warnings)


def execute(op, params):
    contract = CONTRACTS[op]
    try:
        validate(params, contract["schema"])
    except ValidationError as exc:
        fail(exc.message)
    warnings = []
    data = run(op, params, warnings)
    operation = "alarm_query." + op
    return build_response(
        operation=operation,
        func_name="admin." + operation,
        bk_tenant_id=None if params["bk_tenant_id"] == "__all__" else params["bk_tenant_id"],
        data=data,
        warnings=warnings,
    )


for operation, contract in CONTRACTS.items():
    KernelRPCRegistry.register_function(
        func_name="admin.alarm_query." + operation,
        handler=partial(execute, operation),
        summary=contract["summary"],
        description=contract["summary"],
        params_schema=contract["schema"],
        example_params=contract["example"],
    )
