"""Native unify-query operations for the environment-scoped Admin CLI."""

import json
from functools import partial
from urllib.parse import quote

import requests
from django.conf import settings
from jsonschema import Draft7Validator
from rest_framework.exceptions import ValidationError

from api.unify_query.default import get_unify_query_url
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response
from kernel_api.rpc.functions.admin.space import _apply_space_bk_biz_id_filter
from metadata.models import Space

TEXT = {"type": "string"}
INT = {"type": "integer"}
BOOL = {"type": "boolean"}
OBJECT = {"type": "object"}
STRINGS = {"type": "array", "items": TEXT}
OBJECTS = {"type": "array", "items": OBJECT}
# Only sources resolved through the space router. bkdata uses a separate router.
SOURCE = {"enum": ["", "bkmonitor", "bk_monitor", "bklog", "bk_log_search", "bkapm", "bk_apm", "custom"]}
CONTROL = {
    "bk_tenant_id": {"type": "string", "minLength": 1, "not": {"const": "__all__"}},
    "bk_biz_id": {"type": "integer", "not": {"const": 0}},
    "uq_target": {"type": "string", "minLength": 1, "description": "服务端配置的实例名；省略按空间路由"},
    "doris_direct_query": {"type": "boolean", "description": "本次请求的 Doris 直查偏好；省略使用实例默认值"},
    "space_uid": {"type": "string", "description": "可省略；提供时必须与租户和业务解析结果一致"},
}


def typed_keys(names, schema):
    return dict.fromkeys(names.split(), schema)


def object_schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


OUTPUTS = {
    "response_contract": TEXT,
    "legacy_output_ref": TEXT,
    "output_list": {
        "type": "array",
        "items": object_schema({"reference_name": TEXT, "expression": TEXT}, ["reference_name", "expression"]),
    },
}
ITEM = object_schema(
    {
        "data_source": SOURCE,
        **typed_keys("table_id field_name reference_name query_string offset step time_field", TEXT),
        **typed_keys("is_regexp exact_total is_dom_sampled offset_forward is_prefix", BOOL),
        **typed_keys("dimensions keep_columns field_list", STRINGS),
        **typed_keys("from limit slimit soffset timestamp", INT),
        **typed_keys("conditions time_aggregation collapse", OBJECT),
        "function": OBJECTS,
        "table_id_conditions": {"type": "array", "items": OBJECTS},
        "sql": {"const": "", "description": "业务空间查询使用结构化条件"},
    }
)
PERIOD = {"start_time": TEXT, "end_time": TEXT, "timezone": TEXT}
STRUCT = {
    **PERIOD,
    **OUTPUTS,
    "query_list": {"type": "array", "minItems": 1, "items": ITEM},
    **typed_keys("metric_merge step down_sample_range look_back_delta", TEXT),
    **typed_keys("instant not_time_align reference is_merge_db dry_run allow_partial_es_results", BOOL),
    **typed_keys("order_by result_columns add_dimensions", STRINGS),
    **typed_keys("from limit", INT),
}
CURSOR = object_schema(
    {
        **typed_keys("from slice_index slice_max", INT),
        "search_after": {"type": "array"},
        "query_backend": {"enum": ["", "bk_sql", "doris"]},
        # Returned diagnostic fields can be replayed. UQ resolves the actual tables from the space route.
        "direct_tables": OBJECTS,
        "result_schema": OBJECTS,
        "sql": TEXT,
        "scroll_id": {"const": ""},
    }
)
RAW = {
    **STRUCT,
    "is_search_after": BOOL,
    "is_multi_from": BOOL,
    "is_es_batch": BOOL,
    "highlight": OBJECT,
    "result_table_options": {"type": "object", "additionalProperties": CURSOR},
}
PROM = {
    **OUTPUTS,
    "bk_biz_ids": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 1},
    **typed_keys("promql start end step timezone down_sample_range max_source_resolution match look_back_delta", TEXT),
    **typed_keys("instant not_time_align not_align_influxdb is_verify_dimensions reference", BOOL),
    **typed_keys("limit slimit", INT),
    "add_dimensions": STRINGS,
}
INFO = {
    **PERIOD,
    "data_source": SOURCE,
    **typed_keys("table_id metric_name query_string", TEXT),
    "conditions": OBJECT,
    "keys": STRINGS,
    "limit": INT,
    "slimit": INT,
    "is_regexp": BOOL,
    "table_id_conditions": {"type": "array", "items": OBJECTS},
}

METRIC = {"data_source": "bkmonitor", "table_id": "system.cpu_summary", "field_name": "usage", "reference_name": "a"}
LOG = {"data_source": "bklog", "table_id": "example.log", "field_name": "*", "reference_name": "a"}
WINDOW = {"start_time": "1790100000", "end_time": "1790100300"}
STRUCT_EXAMPLE = {**WINDOW, "query_list": [METRIC], "metric_merge": "a", "step": "60s"}
RAW_EXAMPLE = {**WINDOW, "query_list": [LOG], "from": 0, "limit": 20}
PROM_EXAMPLE = {
    "promql": "bkmonitor:system:cpu_summary:usage",
    "start": "1790100000",
    "end": "1790100300",
    "step": "60s",
}
STRUCT_REQUIRED = ("query_list", "start_time", "end_time")
PROM_REQUIRED = ("promql", "start", "end")
# Route paths are fixed by the operation, never taken from the request.
ENDPOINTS = {
    "raw": ("query/ts/raw", "查询日志明细及 SearchAfter 分页", RAW, STRUCT_REQUIRED, RAW_EXAMPLE),
    "raw_with_scroll": (
        "query/ts/raw_with_scroll",
        "滚动读取日志，连续请求使用相同参数",
        {**STRUCT, "scroll": TEXT, "slice_max": INT, "clear_cache": BOOL},
        STRUCT_REQUIRED,
        {**RAW_EXAMPLE, "scroll": "1m"},
    ),
    "reference": ("query/ts/reference", "执行结构化聚合", STRUCT, STRUCT_REQUIRED, STRUCT_EXAMPLE),
    "exemplar": ("query/ts/exemplar", "查询指标 Exemplar", STRUCT, STRUCT_REQUIRED, STRUCT_EXAMPLE),
    "ts": ("query/ts", "执行结构化时序查询", STRUCT, STRUCT_REQUIRED, STRUCT_EXAMPLE),
    "check": ("check/query/ts", "预览结构化查询的存储路由", RAW, STRUCT_REQUIRED, STRUCT_EXAMPLE),
    "promql": ("query/ts/promql", "执行原生 PromQL 查询", PROM, PROM_REQUIRED, PROM_EXAMPLE),
    "check_promql": ("check/query/ts/promql", "预览原生 PromQL 查询", PROM, PROM_REQUIRED, PROM_EXAMPLE),
}
for name, title in {
    "field_map": "字段映射",
    "field_keys": "字段列表",
    "tag_keys": "维度名",
    "tag_values": "维度值",
    "series": "序列",
}.items():
    example = {**WINDOW, "data_source": "bkmonitor", "table_id": "system.cpu_summary", "metric_name": "usage"}
    if name == "tag_values":
        example["keys"] = ["bk_target_ip"]
    ENDPOINTS[name] = (f"query/ts/info/{name}", f"查询{title}", INFO, ("start_time", "end_time"), example)
ENDPOINTS["label_values"] = (
    "query/ts/label/{label}/values",
    "按 PromQL selector 查询维度值",
    {
        "label": {"type": "string", "pattern": r"^[^/?#\x00-\x1f]+$", "not": {"enum": [".", ".."]}},
        "match[]": {"type": "array", "items": TEXT, "minItems": 1, "maxItems": 1},
        "start": TEXT,
        "end": TEXT,
        "limit": INT,
    },
    ("label", "match[]", "start", "end"),
    {"label": "bk_target_ip", "match[]": [PROM_EXAMPLE["promql"]], "start": "1790100000", "end": "1790100300"},
)


def request_uq(base, path, headers, payload, method="POST"):
    response = requests.request(
        method,
        f"{base.rstrip('/')}/{path}",
        headers=headers,
        timeout=60,
        allow_redirects=False,
        **({"params": payload} if method == "GET" else {"json": payload}),
    )
    if response.status_code != 200:
        raise CustomException(
            message=f"unify-query HTTP {response.status_code}", data={"upstream": response.text[:4096]}
        )
    return response.json()


def invoke(name, validator, params):
    error = next(validator.iter_errors(params), None)
    if error:
        raise ValidationError(f"{error.json_path}: {error.message}")
    payload = dict(params)
    tenant = payload.pop("bk_tenant_id")
    biz = payload.pop("bk_biz_id")
    space = _apply_space_bk_biz_id_filter(Space.objects.filter(bk_tenant_id=tenant), biz).first()
    if not space or payload.pop("space_uid", space.space_uid) != space.space_uid:
        raise ValidationError("业务空间不存在或与请求范围不一致")
    if "bk_biz_ids" in payload and payload["bk_biz_ids"] != [str(biz)]:
        raise ValidationError("bk_biz_ids 必须与查询业务一致")
    target = payload.pop("uq_target", None)
    if target is None:
        base = get_unify_query_url(space.space_uid)
    else:
        base = settings.ADMIN_UNIFY_QUERY_TARGETS.get(target)
        if not base:
            raise ValidationError(f"未配置 unify-query 实例 {target}")
    headers = {
        "X-Bk-Scope-Space-Uid": space.space_uid,
        "X-Bk-Tenant-Id": tenant,
        "Bk-Query-Source": f"admin:{quote(tenant, safe='')}",
    }
    if "doris_direct_query" in payload:
        headers["X-Bk-Query-Flags"] = json.dumps({"doris_direct_query": payload.pop("doris_direct_query")})
    path = ENDPOINTS[name][0]
    # PromQL can encode a data source in a selector. Use the target UQ's parser, including for named outputs.
    expressions = []
    if "promql" in payload:
        expressions = [payload["promql"], *(item["expression"] for item in payload.get("output_list", []))]
    elif name == "label_values":
        expressions = payload["match[]"]
    for expr in dict.fromkeys(expressions):
        parsed = request_uq(base, "query/ts/promql_to_struct", headers, {"promql": expr})
        queries = parsed["data"].get("query_list", [])
        if any(q.get("data_source", "") not in SOURCE["enum"] for q in queries):
            raise ValidationError("PromQL 数据来源不支持业务空间隔离")
    if name == "label_values":
        raw = request_uq(base, path.format(label=quote(payload.pop("label"), safe="")), headers, payload, method="GET")
    else:
        raw = request_uq(base, path, headers, payload)
    return build_response(
        operation=f"unify_query.{name}",
        func_name=f"admin.unify_query.{name}",
        bk_tenant_id=tenant,
        safety_level="inspect",
        data=raw,
    )


for name, (path, summary, properties, required, example) in ENDPOINTS.items():
    schema = object_schema({**CONTROL, **properties}, ("bk_tenant_id", "bk_biz_id", *required))
    KernelRPCRegistry.register_function(
        func_name=f"admin.unify_query.{name}",
        handler=partial(invoke, name, Draft7Validator(schema)),
        summary=summary,
        description=f"{summary}。绑定具体业务空间；原生 UQ 返回体位于 data。路径 /{path}",
        params_schema=schema,
        example_params={"bk_tenant_id": "system", "bk_biz_id": 2, **example},
    )
