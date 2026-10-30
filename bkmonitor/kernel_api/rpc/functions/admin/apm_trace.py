"""面向 Admin/CLI 的原始 Trace、Span 和应用候选查询。"""

import time

from rest_framework import serializers

from apm.serializers import FilterSerializer
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.apm import apm_models
from kernel_api.rpc.functions.admin.common import build_response


class ScopeSerializer(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=64)
    start_time = serializers.IntegerField(min_value=0, required=False, allow_null=True, default=None)
    end_time = serializers.IntegerField(min_value=0, required=False, allow_null=True, default=None)

    def validate(self, attrs):
        unknown = self.initial_data.keys() - self.fields.keys()
        if unknown:
            raise serializers.ValidationError(f"不支持的参数: {', '.join(sorted(unknown))}")
        if attrs["bk_tenant_id"] == "__all__":
            raise serializers.ValidationError("请选择具体租户")
        start, end = attrs["start_time"], attrs["end_time"]
        if (start is None) != (end is None):
            raise serializers.ValidationError("start_time 和 end_time 必须同时提供")
        if start is not None and start > end:
            raise serializers.ValidationError("start_time 不能大于 end_time")
        return attrs


class AppSerializer(ScopeSerializer):
    bk_biz_id = serializers.IntegerField()
    app_name = serializers.CharField(max_length=50)


class PageSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class SpanListSerializer(AppSerializer, PageSerializer):
    trace_id = serializers.CharField(required=False)
    span_id = serializers.CharField(required=False)
    parent_span_id = serializers.CharField(required=False)
    filters = FilterSerializer(many=True, default=list)
    query_string = serializers.CharField(allow_blank=True, default="")
    sort = serializers.ListField(child=serializers.CharField(), default=list)

    def validate(self, attrs):
        from apm.core.handlers.query.proxy import QueryProxy

        attrs = super().validate(attrs)
        if attrs["start_time"] is None and not QueryProxy.is_trace_or_span_id_query(
            _filters(attrs), attrs["query_string"]
        ):
            raise serializers.ValidationError("普通列表查询必须提供时间范围")
        return attrs


class TraceListSerializer(SpanListSerializer):
    query_mode = serializers.ChoiceField(choices=["pre_calculation", "origin"], default="pre_calculation")


class TraceDetailSerializer(AppSerializer, PageSerializer):
    trace_id = serializers.CharField()


class SpanDetailSerializer(AppSerializer):
    span_id = serializers.CharField()
    trace_id = serializers.CharField(required=False)


class SpanRelationSerializer(SpanDetailSerializer, PageSerializer):
    relation = serializers.ChoiceField(choices=["parent", "children", "links_out", "links_in"])


class TraceApplicationSerializer(ScopeSerializer, PageSerializer):
    trace_id = serializers.CharField()
    bk_biz_id = serializers.IntegerField(required=False)


FILTER_SCHEMA = {
    "type": "object",
    "required": ["key", "operator", "value"],
    "properties": {
        "key": {"type": "string"},
        "operator": {"type": "string"},
        "value": {"type": "array", "items": {"type": "string"}},
        "options": {
            "type": "object",
            "properties": {
                "is_wildcard": {"type": "boolean"},
                "group_relation": {"type": "string", "enum": ["AND", "OR"]},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
PARAM_PROPERTIES = {
    "bk_tenant_id": {"type": "string", "minLength": 1, "maxLength": 64},
    "bk_biz_id": {"type": "integer"},
    "app_name": {"type": "string", "minLength": 1, "maxLength": 50},
    "start_time": {"type": ["integer", "null"], "minimum": 0, "description": "Unix 秒"},
    "end_time": {"type": ["integer", "null"], "minimum": 0, "description": "Unix 秒"},
    "trace_id": {"type": "string", "minLength": 1},
    "span_id": {"type": "string", "minLength": 1},
    "parent_span_id": {"type": "string", "minLength": 1},
    "page": {"type": "integer", "minimum": 1, "default": 1},
    "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
    "filters": {"type": "array", "items": FILTER_SCHEMA},
    "query_string": {"type": "string"},
    "sort": {"type": "array", "items": {"type": "string"}},
    "query_mode": {"type": "string", "enum": ["pre_calculation", "origin"], "default": "pre_calculation"},
    "relation": {"type": "string", "enum": ["parent", "children", "links_out", "links_in"]},
}
APP_EXAMPLE = {"bk_tenant_id": "system", "bk_biz_id": 2, "app_name": "checkout"}


def _register(name, serializer_class, description, example):
    fields = serializer_class().fields
    return KernelRPCRegistry.register(
        f"admin.apm.{name}",
        summary=description,
        description=f"inspect，只读，至少 operator。{description}；分页不提供总数，使用 has_more。",
        params_schema={
            "type": "object",
            "properties": {key: PARAM_PROPERTIES[key] for key in fields},
            "required": [key for key, field in fields.items() if field.required],
            "additionalProperties": False,
        },
        example_params=example,
    )


def _validate(serializer_class, params):
    serializer = serializer_class(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _make_proxy(params):
    from apm.core.handlers.query.proxy import QueryProxy

    application = apm_models.ApmApplication.objects.filter(
        bk_tenant_id=params["bk_tenant_id"], bk_biz_id=params["bk_biz_id"], app_name=params["app_name"]
    ).first()
    if application is None:
        raise CustomException(message="指定租户下的 APM 应用不存在")
    return QueryProxy(application.bk_biz_id, application.app_name)


def _filters(params):
    filters = list(params.get("filters", []))
    for key in ("trace_id", "span_id", "parent_span_id"):
        if params.get(key):
            filters.append({"key": key, "operator": "equal", "value": [params[key]]})
    return filters


def _page(items, params):
    return {
        "items": items[: params["page_size"]],
        "page": params["page"],
        "page_size": params["page_size"],
        "has_more": len(items) > params["page_size"],
    }


def _response(name, params, data, warnings=None):
    return build_response(
        operation=f"apm.{name}",
        func_name=f"admin.apm.{name}",
        bk_tenant_id=params["bk_tenant_id"],
        data=data,
        warnings=warnings,
        safety_level="inspect",
    )


def _query(proxy, params, mode):
    # 直接使用路由后的 Query，保留调用方显式提供的时间范围，也不触发跨应用详情路径。
    return proxy._get_query(mode, params["start_time"], params["end_time"])


def _list(query, params, filters=None, *, full=False, offset=None, limit=None):
    from apm.core.handlers.query.origin_trace_query import OriginTraceQuery

    sort = [f"{field[1:]} desc" if field.startswith("-") else field for field in params.get("sort", [])]
    offset = (params.get("page", 1) - 1) * params.get("page_size", 20) if offset is None else offset
    limit = params.get("page_size", 20) + 1 if limit is None else limit
    filters = _filters(params) if filters is None else filters
    if full:
        # 不做 values 投影，保留原始 Span 的全部字段（包括扩展字段）。
        queries = [q.order_by(*(sort or ["end_time desc", "span_id"])) for q in query.build_queries(filters)]
        return query._query_list(queries, params["start_time"], params["end_time"], offset, limit)
    if isinstance(query, OriginTraceQuery):
        # 原有 origin 列表会忽略单条 Trace 处理异常；Admin 查询必须把失败返回调用方。
        from functools import partial

        from apm.core.discover.precalculation.processor import PrecalculateProcessor
        from bkmonitor.utils.thread_backend import ThreadPool

        queries = [
            q.order_by(*(sort or ["end_time desc"])).distinct("trace_id").values("trace_id")
            for q in query.build_queries(filters, params.get("query_string", ""))
        ]
        records = query._query_list(queries, params["start_time"], params["end_time"], offset, limit)
        trace_ids = [
            record["trace_id"][0] if isinstance(record["trace_id"], list) else record["trace_id"] for record in records
        ]
        if not trace_ids:
            return []
        processor = PrecalculateProcessor(None, query.bk_biz_id, query.app_name)
        with ThreadPool() as pool:
            return pool.map_async(partial(query._query_trace_info, processor), trace_ids).get()
    return (
        query.query_list(
            params["start_time"],
            params["end_time"],
            offset,
            limit,
            filters,
            None,
            params.get("query_string", ""),
            sort or None,
        )
        or []
    )


def _find_span(proxy, params, *, trace_id=None, span_id=None):
    filters = [{"key": "span_id", "operator": "equal", "value": [span_id or params["span_id"]]}]
    trace_id = trace_id or params.get("trace_id")
    if trace_id:
        filters.append({"key": "trace_id", "operator": "equal", "value": [trace_id]})
    spans = _list(_query(proxy, params, "span"), params, filters, full=True, offset=0, limit=1)
    return spans[0] if spans else None


@_register(
    "trace_list",
    TraceListSerializer,
    "分页查询应用内 Trace；默认预计算，可显式选择 origin",
    {
        **APP_EXAMPLE,
        "start_time": 1790100000,
        "end_time": 1790103600,
        "page": 1,
        "page_size": 20,
    },
)
def trace_list(params):
    params = _validate(TraceListSerializer, params)
    proxy = _make_proxy(params)
    mode = "trace" if params["query_mode"] == "pre_calculation" else "origin_trace"
    query = _query(proxy, params, mode)
    warnings = []
    if mode == "trace":
        from apm.core.handlers.query.base import FakeQuery

        if isinstance(query, FakeQuery):
            warnings.append({"code": "PRECALCULATION_UNAVAILABLE", "message": "预计算不可用，可显式使用 origin 模式"})
    return _response(
        "trace_list", params, {**_page(_list(query, params), params), "query_mode": params["query_mode"]}, warnings
    )


@_register(
    "span_list",
    SpanListSerializer,
    "分页查询应用内 Span；精确 Trace/Span ID 查询可省略时间范围",
    {
        **APP_EXAMPLE,
        "trace_id": "example-trace",
        "page": 1,
        "page_size": 20,
    },
)
def span_list(params):
    params = _validate(SpanListSerializer, params)
    proxy = _make_proxy(params)
    return _response("span_list", params, _page(_list(_query(proxy, params, "span"), params), params))


@_register(
    "trace_detail",
    TraceDetailSerializer,
    "查询 Trace 预计算摘要与分页 Span；摘要可能延迟，不从当前页合成统计",
    {
        **APP_EXAMPLE,
        "trace_id": "example-trace",
        "page": 1,
        "page_size": 20,
    },
)
def trace_detail(params):
    params = _validate(TraceDetailSerializer, params)
    proxy = _make_proxy(params)
    spans = _list(_query(proxy, params, "span"), params)
    summary = _list(_query(proxy, params, "trace"), params, offset=0, limit=1)
    warnings = (
        [] if summary else [{"code": "TRACE_SUMMARY_UNAVAILABLE", "message": "预计算摘要缺失或延迟，请参考原始 Span"}]
    )
    return _response(
        "trace_detail",
        params,
        {
            "trace_id": params["trace_id"],
            "summary": summary[0] if summary else None,
            "spans": _page(spans, params),
        },
        warnings,
    )


@_register(
    "span_detail",
    SpanDetailSerializer,
    "查询完整原始 Span，保留 resource、attributes、events 和 links",
    {
        **APP_EXAMPLE,
        "span_id": "example-span",
        "trace_id": "example-trace",
    },
)
def span_detail(params):
    params = _validate(SpanDetailSerializer, params)
    return _response("span_detail", params, {"span": _find_span(_make_proxy(params), params)})


def _reference(span):
    return {"trace_id": span.get("trace_id", ""), "span_id": span.get("span_id", "")}


def _span_summary(span):
    return {key: value for key, value in span.items() if key not in {"attributes", "events", "links"}}


def _edge(source, target, related=None, link=None):
    return {"source": source, "target": target, "span": _span_summary(related) if related else None, "link": link}


@_register(
    "span_relation_list",
    SpanRelationSerializer,
    "分页查询 parent/children/links_out/links_in；仅解析当前应用内目标",
    {
        **APP_EXAMPLE,
        "span_id": "example-span",
        "relation": "children",
        "page": 1,
        "page_size": 20,
    },
)
def span_relation_list(params):
    params = _validate(SpanRelationSerializer, params)
    proxy = _make_proxy(params)
    span = _find_span(proxy, params)
    if span is None:
        return _response("span_relation_list", params, {"relation": params["relation"], **_page([], params)})
    ref = _reference(span)
    relation = params["relation"]
    offset = (params["page"] - 1) * params["page_size"]
    items = []
    if relation == "parent":
        parent_id = span.get("parent_span_id")
        if parent_id and parent_id != "0000000000000000" and offset == 0:
            parent = _find_span(proxy, params, trace_id=span["trace_id"], span_id=parent_id)
            items = [_edge({"trace_id": span["trace_id"], "span_id": parent_id}, ref, parent)]
    elif relation == "children":
        filters = [
            {"key": "trace_id", "operator": "equal", "value": [span["trace_id"]]},
            {"key": "parent_span_id", "operator": "equal", "value": [span["span_id"]]},
        ]
        children = _list(_query(proxy, params, "span"), params, filters)
        items = [_edge(ref, _reference(child), child) for child in children]
    elif relation == "links_out":
        links = (span.get("links") or [])[offset : offset + params["page_size"] + 1]
        for link in links:
            target = _reference(link)
            related = _find_span(proxy, params, **target) if target["trace_id"] and target["span_id"] else None
            items.append(_edge(ref, target, related, link))
    else:
        # 先按嵌套字段缩小候选，再逐个 Link 匹配同一对象中的两个 ID，避免交叉匹配。
        filters = [{"key": f"links.{key}", "operator": "equal", "value": [value]} for key, value in ref.items()]
        query = _query(proxy, params, "span")
        scan_offset = 0
        matched = 0
        while len(items) <= params["page_size"]:
            candidates = _list(query, params, filters, full=True, offset=scan_offset, limit=100)
            for candidate in candidates:
                for link in candidate.get("links") or []:
                    if _reference(link) != ref:
                        continue
                    if matched >= offset:
                        items.append(_edge(_reference(candidate), ref, candidate, link))
                    matched += 1
                    if len(items) > params["page_size"]:
                        break
                if len(items) > params["page_size"]:
                    break
            if len(candidates) < 100:
                break
            scan_offset += len(candidates)
    return _response("span_relation_list", params, {"relation": relation, **_page(items, params)})


def _precalc_tables():
    configs = apm_models.DataLink.objects.values_list("pre_calculate_config", flat=True)
    return list(
        dict.fromkeys(cluster["table_name"] for config in configs for cluster in ((config or {}).get("cluster") or []))
    )


def _query_application_candidates(table_id, params):
    from bkmonitor.data_source import load_data_source
    from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
    from bkmonitor.data_source.unify_query.query import UnifyQuery
    from constants.data_source import DataSourceLabel, DataTypeLabel

    query = (
        QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM))
        .table(table_id)
        .filter(
            trace_id__eq=params["trace_id"],
            bk_tenant_id__eq=params["bk_tenant_id"],
        )
    )
    if "bk_biz_id" in params:
        query = query.filter(biz_id__eq=str(params["bk_biz_id"]))
    query = (
        query.time_field("min_start_time")
        .alias("a")
        .metric("trace_id", "count")
        .group_by("biz_id", "app_name")
        .order_by("biz_id", "app_name")
    )
    # 聚合后每个应用一条；按底层既有窗口读取，避免默认只取前几条而漏掉后续候选。
    qs = (
        UnifyQuerySet()
        .add_query(query)
        .start_time(params["start_time"] * 1000)
        .end_time(params["end_time"] * 1000)
        .time_align(False)
        .time_agg(False)
        .instant()
        .expression("a")
    )
    config = qs.config["query_configs"][0]
    source = load_data_source(config["data_source_label"], config["data_type_label"])(
        bk_biz_id=None, use_full_index_names=True, **config
    )
    provider = UnifyQuery(bk_biz_id=None, data_sources=[source], expression="a")
    # 仅在新反查接口内显式传偏移，不修改公共 query_reference 的历史行为。
    if provider.use_unify_query():
        provider.process_data_sources(provider.data_sources)
        query_page = provider._query_reference_using_unify_query
    else:
        query_page = provider.query_reference
    records = []
    offset = 0
    while True:
        batch = query_page(
            start_time=params["start_time"] * 1000,
            end_time=params["end_time"] * 1000,
            limit=100,
            offset=offset,
            time_alignment=False,
            instant=True,
            order_by=["biz_id", "app_name"],
        )
        records.extend(batch)
        if len(batch) < 100:
            return records
        offset += len(batch)


@_register(
    "trace_application_list",
    TraceApplicationSerializer,
    "仅通过预计算反查候选应用；默认最近 7 天，可能延迟或漏查，未命中不代表 Trace 不存在",
    {
        "bk_tenant_id": "system",
        "trace_id": "example-trace",
        "page": 1,
        "page_size": 20,
    },
)
def trace_application_list(params):
    params = _validate(TraceApplicationSerializer, params)
    if params["start_time"] is None:
        params["end_time"] = int(time.time())
        params["start_time"] = params["end_time"] - 7 * 86400
    warnings = [
        {"code": "PRECALCULATION_DELAY", "message": "仅查询预计算候选，可能延迟或漏查；未命中不代表 Trace 不存在"}
    ]
    tables = _precalc_tables()
    if not tables:
        warnings.append({"code": "PRECALCULATION_UNAVAILABLE", "message": "没有可用的预计算表配置"})
    keys = set()
    for table_id in tables:
        try:
            records = _query_application_candidates(table_id, params)
            keys.update((int(record["biz_id"]), record["app_name"]) for record in records)
        except Exception as error:
            warnings.append(
                {"code": "PRECALCULATION_QUERY_FAILED", "message": f"预计算表 {table_id} 查询失败: {error}"}
            )
    from django.db.models import Q

    pairs = Q()
    for bk_biz_id, app_name in keys:
        if "bk_biz_id" not in params or bk_biz_id == params["bk_biz_id"]:
            pairs |= Q(bk_biz_id=bk_biz_id, app_name=app_name)
    items = []
    if pairs:
        offset = (params["page"] - 1) * params["page_size"]
        applications = apm_models.ApmApplication.objects.filter(
            pairs,
            bk_tenant_id=params["bk_tenant_id"],
        ).order_by("id")[offset : offset + params["page_size"] + 1]
        items = [
            {
                "application_id": app.id,
                "bk_tenant_id": app.bk_tenant_id,
                "bk_biz_id": app.bk_biz_id,
                "app_name": app.app_name,
                "app_alias": app.app_alias,
            }
            for app in applications
        ]
    return _response(
        "trace_application_list",
        params,
        {
            **_page(items, params),
            "trace_id": params["trace_id"],
            "source": "pre_calculation",
            "start_time": params["start_time"],
            "end_time": params["end_time"],
        },
        warnings,
    )
