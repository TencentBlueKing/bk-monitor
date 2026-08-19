import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from apps.api import BkDataAccessApi, BkDataDatabusApi, BkDataDataFlowApi
from apps.exceptions import ValidationError
from apps.log_admin_resource.handlers.inspection import (
    DEFAULT_SAMPLE_LIMIT,
    MAX_SAMPLE_LIMIT,
    build_bkdata_context,
    call_bkdata,
    optional_positive_int,
    probe_failure,
    probe_skipped,
    reject_identity_params,
    require_nonzero_int,
    require_positive_int,
    sanitize_json,
    serialize_tail_rows,
)


MAX_RESULT_TABLES = 20
MAX_EXTERNAL_CONCURRENCY = 5


def get_bkdata_raw_snapshot(params):
    params = params or {}
    reject_identity_params(params)
    raw_data_id = require_positive_int(params, "raw_data_id")
    bk_biz_id = require_nonzero_int(params, "bk_biz_id")
    sample_limit = optional_positive_int(
        params.get("sample_limit"), "sample_limit", default=DEFAULT_SAMPLE_LIMIT, maximum=MAX_SAMPLE_LIMIT
    )
    try:
        context = build_bkdata_context(bk_biz_id)
    except Exception as error:
        return {
            "raw_data_id": raw_data_id,
            "bk_biz_id": bk_biz_id,
            **_context_failure_probes(error, "deploy", "tail"),
        }

    probes = _parallel_bkdata_calls(
        {
            "deploy": (BkDataAccessApi.get_deploy_summary, {**context, "raw_data_id": raw_data_id}),
            "tail": (BkDataDatabusApi.get_raw_data_tail, {**context, "raw_data_id": raw_data_id}),
        }
    )
    return {
        "raw_data_id": raw_data_id,
        "bk_biz_id": bk_biz_id,
        "deploy": _summarize_probe(probes["deploy"], _raw_deploy_summary),
        "tail": _summarize_probe(
            probes["tail"],
            lambda data: serialize_tail_rows(data, sample_limit, decode_wrapped=True),
        ),
    }


def get_bkdata_clean_snapshot(params):
    params = params or {}
    reject_identity_params(params)
    processing_id = params.get("processing_id")
    if not processing_id:
        raise ValidationError("processing_id is required")
    bk_biz_id = require_nonzero_int(params, "bk_biz_id")
    try:
        context = build_bkdata_context(bk_biz_id)
    except Exception as error:
        return {
            "processing_id": processing_id,
            "result_table_id": params.get("result_table_id"),
            "bk_biz_id": bk_biz_id,
            **_context_failure_probes(error, "detail", "tasks"),
        }
    detail = call_bkdata(
        BkDataDatabusApi.get_clean,
        {**context, "processing_id": processing_id},
    )
    result_table_id = params.get("result_table_id")
    if not result_table_id and detail["probe_status"] == "success" and isinstance(detail["data"], dict):
        result_table_id = detail["data"].get("result_table_id")
    if result_table_id:
        tasks = call_bkdata(
            BkDataDatabusApi.get_tasks,
            {**context, "result_table_id": result_table_id},
        )
    else:
        tasks = probe_skipped(
            "RESOURCE_NOT_CONFIGURED",
            "result_table_id was not provided and could not be derived from clean detail.",
        )
    return {
        "processing_id": processing_id,
        "result_table_id": result_table_id,
        "bk_biz_id": bk_biz_id,
        "detail": _summarize_probe(detail, _clean_detail_summary),
        "tasks": _summarize_probe(tasks, _clean_task_summary),
    }


def get_bkdata_flow_snapshot(params):
    params = params or {}
    reject_identity_params(params)
    flow_id = require_positive_int(params, "flow_id")
    bk_biz_id = require_nonzero_int(params, "bk_biz_id")
    try:
        context = build_bkdata_context(bk_biz_id)
    except Exception as error:
        return {
            "flow_id": flow_id,
            "bk_biz_id": bk_biz_id,
            **_context_failure_probes(error, "detail", "latest_deploy", "graph"),
        }
    flow_params = {**context, "flow_id": flow_id}
    probes = _parallel_bkdata_calls(
        {
            "detail": (BkDataDataFlowApi.get_dataflow, dict(flow_params)),
            "latest_deploy": (BkDataDataFlowApi.get_latest_deploy_data, dict(flow_params)),
            "graph": (BkDataDataFlowApi.get_flow_graph, dict(flow_params)),
        }
    )
    return {
        "flow_id": flow_id,
        "bk_biz_id": bk_biz_id,
        "detail": _summarize_probe(probes["detail"], _flow_detail_summary),
        "latest_deploy": _summarize_probe(probes["latest_deploy"], _flow_deploy_summary),
        "graph": _summarize_probe(probes["graph"], _flow_graph_summary),
    }


def batch_get_bkdata_result_table_snapshots(params):
    params = params or {}
    reject_identity_params(params)
    items = params.get("items")
    if not isinstance(items, list) or not items:
        raise ValidationError("items must be a non-empty array")
    if len(items) > MAX_RESULT_TABLES:
        raise ValidationError(f"items must contain at most {MAX_RESULT_TABLES} result tables")
    sample_limit = optional_positive_int(
        params.get("sample_limit"), "sample_limit", default=DEFAULT_SAMPLE_LIMIT, maximum=MAX_SAMPLE_LIMIT
    )

    prepared = []
    results = [None] * len(items)
    context_by_bk_biz_id = {}
    context_error_by_bk_biz_id = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValidationError(f"items[{index}] must be an object")
        reject_identity_params(item)
        result_table_id = item.get("result_table_id")
        if not result_table_id:
            raise ValidationError(f"items[{index}].result_table_id is required")
        try:
            bk_biz_id = int(item.get("bk_biz_id") or str(result_table_id).split("_", 1)[0])
        except (TypeError, ValueError):
            raise ValidationError(f"items[{index}].bk_biz_id is required when it cannot be derived from RT")
        if bk_biz_id == 0:
            raise ValidationError(f"items[{index}].bk_biz_id must not be zero")
        prepared_item = {
            "index": index,
            "result_table_id": str(result_table_id),
            "bk_biz_id": bk_biz_id,
        }
        if bk_biz_id not in context_by_bk_biz_id and bk_biz_id not in context_error_by_bk_biz_id:
            try:
                context_by_bk_biz_id[bk_biz_id] = build_bkdata_context(bk_biz_id)
            except Exception as error:
                context_error_by_bk_biz_id[bk_biz_id] = error
        if bk_biz_id in context_by_bk_biz_id:
            prepared_item["context"] = context_by_bk_biz_id[bk_biz_id]
            prepared.append(prepared_item)
        else:
            error = context_error_by_bk_biz_id[bk_biz_id]
            results[index] = {
                "result_table_id": prepared_item["result_table_id"],
                "bk_biz_id": bk_biz_id,
                "detail": probe_failure(error),
                "tail": probe_failure(error),
            }

    started = time.monotonic()
    if prepared:
        with ThreadPoolExecutor(max_workers=min(MAX_EXTERNAL_CONCURRENCY, len(prepared))) as executor:
            future_map = {executor.submit(_inspect_result_table, item, sample_limit): item for item in prepared}
            for future in as_completed(future_map):
                item = future_map[future]
                index = item["index"]
                try:
                    results[index] = future.result()
                except Exception as error:  # Keep the remaining RT evidence available.
                    results[index] = {
                        "result_table_id": item["result_table_id"],
                        "bk_biz_id": item["bk_biz_id"],
                        "detail": probe_failure(error),
                        "tail": probe_failure(error),
                    }
    return {
        "items": results,
        "item_count": len(results),
        "sample_limit": sample_limit,
        "max_concurrency": MAX_EXTERNAL_CONCURRENCY,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
    }


def _inspect_result_table(item, sample_limit):
    request_params = {**item["context"], "result_table_id": item["result_table_id"]}
    detail = call_bkdata(BkDataDatabusApi.get_result_table, dict(request_params))
    tail = call_bkdata(BkDataDatabusApi.get_result_table_tail, dict(request_params))
    return {
        "result_table_id": item["result_table_id"],
        "bk_biz_id": item["bk_biz_id"],
        "detail": _summarize_probe(detail, _result_table_summary),
        "tail": _summarize_probe(tail, lambda data: serialize_tail_rows(data, sample_limit)),
    }


def _parallel_bkdata_calls(call_specs):
    results = {}
    with ThreadPoolExecutor(max_workers=min(MAX_EXTERNAL_CONCURRENCY, len(call_specs))) as executor:
        future_map = {executor.submit(call_bkdata, api, params): name for name, (api, params) in call_specs.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception as error:
                results[name] = probe_failure(error)
    return results


def _context_failure_probes(error, *names):
    return {name: probe_failure(error) for name in names}


def _summarize_probe(probe, serializer):
    if probe["probe_status"] != "success":
        return probe
    try:
        serialized = serializer(probe["data"])
    except Exception as error:
        return probe_failure(error)
    warnings = list(probe.get("warnings") or [])
    if isinstance(serialized, dict):
        warnings.extend(serialized.pop("warnings", []))
    probe["data"] = serialized
    probe["warnings"] = warnings
    return probe


def _raw_deploy_summary(data):
    _require_mapping(data, "RawData deploy")
    summary = _pick(data, "raw_data_id", "data_id", "active", "status", "topic", "bk_biz_id")
    return {"summary": summary, "raw": sanitize_json(data, max_bytes=256 * 1024)}


def _clean_detail_summary(data):
    _require_mapping(data, "clean detail")
    summary = _pick(
        data,
        "processing_id",
        "status",
        "raw_data_id",
        "result_table_id",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    )
    return {"summary": summary, "raw": sanitize_json(data, max_bytes=256 * 1024)}


def _clean_task_summary(data):
    if data is not None and not isinstance(data, list | dict):
        raise ValueError("invalid response: clean tasks must be an object or array")
    rows = data if isinstance(data, list) else [data] if data else []
    summary = [
        _pick(row, "id", "status", "processing_id", "result_table_id", "connector_task_name", "cluster_name")
        for row in rows
        if isinstance(row, dict)
    ]
    return {"summary": summary, "raw": sanitize_json(data, max_bytes=256 * 1024)}


def _flow_detail_summary(data):
    _require_mapping(data, "Flow detail")
    return {
        "summary": _pick(data, "flow_id", "flow_name", "status", "project_id", "created_at", "updated_at"),
        "raw": sanitize_json(data, max_bytes=512 * 1024),
    }


def _flow_deploy_summary(data):
    _require_mapping(data, "Flow deploy")
    return {
        "summary": _pick(
            data,
            "status",
            "deploy_status",
            "deploy_progress",
            "start_time",
            "end_time",
            "nodes_status",
            "version",
        ),
        "raw": sanitize_json(data, max_bytes=512 * 1024),
    }


def _flow_graph_summary(data):
    _require_mapping(data, "Flow graph")
    nodes = []
    if isinstance(data, dict):
        raw_nodes = data.get("nodes") or data.get("node_list") or []
        if isinstance(raw_nodes, dict):
            raw_nodes = list(raw_nodes.values())
        for node in raw_nodes if isinstance(raw_nodes, list) else []:
            if isinstance(node, dict):
                nodes.append(_pick(node, "node_id", "id", "node_name", "name", "node_type", "type", "status"))
    return {
        "summary": {
            "nodes": nodes,
            "node_count": len(nodes),
            "link_count": _collection_size(data, "links", "lines", "edges"),
        },
        "raw": sanitize_json(data, max_bytes=1024 * 1024),
    }


def _result_table_summary(data):
    _require_mapping(data, "result table detail")
    return {
        "summary": _pick(
            data,
            "result_table_id",
            "result_table_name",
            "processing_type",
            "generate_type",
            "sensitivity",
            "count_freq",
            "created_at",
            "updated_at",
        ),
        "raw": sanitize_json(data, max_bytes=256 * 1024),
    }


def _pick(value, *keys):
    if not isinstance(value, dict):
        return {}
    return {key: sanitize_json(value.get(key)) for key in keys if key in value}


def _collection_size(value, *keys):
    if not isinstance(value, dict):
        return 0
    for key in keys:
        collection = value.get(key)
        if isinstance(collection, list | dict):
            return len(collection)
    return 0


def _require_mapping(data, resource_name):
    if data is not None and not isinstance(data, dict):
        raise ValueError(f"invalid response: {resource_name} must be an object")
