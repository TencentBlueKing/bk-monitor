#!/usr/bin/env python3
"""Local surgery tools for BlueKing iframe Grafana dashboards.

The platform is not official Grafana MCP. Dashboards are stored as Grafana 10
JSON with BK-specific targets (mode/ui/code, query_configs, source) and shown
inside a Monitor iframe. This CLI keeps the full JSON on disk and only prints
summaries / single panels / apply results, so the LLM never rewrites the board.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

DS_TYPE = "bkmonitor-timeseries-datasource"
DS_TEMPLATE_UID = "${DS_蓝鲸监控_- 指标数据}"
VAR_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")

DEFAULT_INPUTS = [
    {
        "name": "DS_蓝鲸监控_- 指标数据",
        "label": "蓝鲸监控 - 指标数据",
        "description": "",
        "type": "datasource",
        "pluginId": DS_TYPE,
        "pluginName": "BlueKing Monitor TimeSeries",
    }
]

DEFAULT_REQUIRES = [
    {
        "type": "datasource",
        "id": DS_TYPE,
        "name": "BlueKing Monitor TimeSeries",
        "version": "3.6.0",
    },
    {"type": "grafana", "id": "grafana", "name": "Grafana", "version": "10.4.10"},
    {"type": "panel", "id": "timeseries", "name": "Time series", "version": ""},
]

DEFAULT_OPTIONS = {
    "stat": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "showPercentChange": False,
        "textMode": "auto",
        "wideLayout": True,
    },
    "gauge": {
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "showThresholdLabels": False,
        "showThresholdMarkers": True,
    },
    "timeseries": {
        "legend": {
            "calcs": ["lastNotNull"],
            "displayMode": "list",
            "placement": "bottom",
            "showLegend": True,
        },
        "tooltip": {"mode": "multi", "sort": "none"},
    },
    "table": {"showHeader": True, "cellHeight": "sm"},
}

VALID_PANEL_TYPES = {
    "timeseries",
    "stat",
    "table",
    "gauge",
    "bargauge",
    "barchart",
    "piechart",
    "heatmap",
    "row",
    "text",
    "logs",
}

DATA_SOURCE_PREFIX = {
    "bk_monitor": "bkmonitor",
    "custom": "custom",
    "bk_data": "bkdata",
}


class ToolError(Exception):
    def __init__(self, message: str, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.extra = extra or {}


def load_json(path: str | Path) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def dump_json(path: str | Path, obj: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(obj: Any, code: int = 0) -> int:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


def unwrap_dashboard(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Accept MCP envelope, {data: json-string}, or raw Grafana JSON."""
    meta: dict[str, Any] = {}
    if isinstance(obj, str):
        obj = json.loads(obj)
    if not isinstance(obj, dict):
        raise ToolError("input is not a JSON object")

    if "response_body" in obj and isinstance(obj["response_body"], dict):
        obj = obj["response_body"]

    if "panels" in obj:
        return obj, meta

    payload = obj.get("data", obj)
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], str):
        for key in ("id", "uid", "title", "version", "slug"):
            if key in payload:
                meta[key] = payload[key]
        grafana = json.loads(payload["data"])
        if not isinstance(grafana, dict):
            raise ToolError("decoded data is not a dashboard object")
        return grafana, meta

    if isinstance(payload, str):
        grafana = json.loads(payload)
        if not isinstance(grafana, dict):
            raise ToolError("decoded data is not a dashboard object")
        return grafana, meta

    if isinstance(payload, dict) and "panels" in payload:
        return payload, meta

    raise ToolError("cannot find Grafana dashboard JSON; expected MCP data.data string or panels")


def walk_panels(panels: list[Any] | None):
    for panel in panels or []:
        if not isinstance(panel, dict):
            continue
        yield panel
        if panel.get("type") == "row":
            yield from walk_panels(panel.get("panels") or [])


def find_panel(dashboard: dict[str, Any], panel_id: int) -> dict[str, Any]:
    for panel in walk_panels(dashboard.get("panels") or []):
        if panel.get("id") == panel_id:
            return panel
    raise ToolError(f"panel_id {panel_id} not found")


def remove_panel(panels: list[Any], panel_id: int) -> bool:
    for index, panel in enumerate(list(panels)):
        if not isinstance(panel, dict):
            continue
        if panel.get("id") == panel_id:
            panels.pop(index)
            return True
        if panel.get("type") == "row" and isinstance(panel.get("panels"), list):
            if remove_panel(panel["panels"], panel_id):
                return True
    return False


def next_panel_id(dashboard: dict[str, Any]) -> int:
    ids = [p.get("id") for p in walk_panels(dashboard.get("panels") or []) if isinstance(p.get("id"), int)]
    return (max(ids) + 1) if ids else 1


def max_grid_bottom(dashboard: dict[str, Any]) -> int:
    bottom = 0
    for panel in walk_panels(dashboard.get("panels") or []):
        grid = panel.get("gridPos") or {}
        try:
            bottom = max(bottom, int(grid.get("y", 0)) + int(grid.get("h", 0)))
        except (TypeError, ValueError):
            continue
    return bottom


def deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)
        else:
            dst[key] = copy.deepcopy(value)
    return dst


def summarize_target(target: dict[str, Any]) -> dict[str, Any]:
    mode = target.get("mode") or ("ui" if target.get("query_configs") else "code")
    configs = target.get("query_configs") or []
    summary: dict[str, Any] = {
        "refId": target.get("refId"),
        "mode": mode,
        "promqlAlias": target.get("promqlAlias") or "",
        "format": target.get("format"),
        "type": target.get("type"),
        "has_variables": False,
    }
    if mode == "code":
        source = target.get("source") or ""
        summary["source"] = source
        summary["has_variables"] = bool(VAR_RE.search(source))
    else:
        summary["query_configs"] = [
            {
                "alias": item.get("alias"),
                "refId": item.get("refId"),
                "data_source_label": item.get("data_source_label"),
                "result_table_id": item.get("result_table_id"),
                "metric_field": item.get("metric_field"),
                "method": item.get("method"),
                "group_by": item.get("group_by") or [],
                "functions": [fn.get("id") for fn in (item.get("functions") or []) if isinstance(fn, dict)],
            }
            for item in configs
            if isinstance(item, dict)
        ]
    return summary


def panel_summary(panel: dict[str, Any]) -> dict[str, Any]:
    targets = [t for t in (panel.get("targets") or []) if isinstance(t, dict)]
    return {
        "id": panel.get("id"),
        "title": panel.get("title") or "",
        "type": panel.get("type") or "",
        "queryCount": len(targets),
        "gridPos": panel.get("gridPos") or {},
        "datasource_uid": ((panel.get("datasource") or {}) if isinstance(panel.get("datasource"), dict) else {}).get(
            "uid"
        ),
        "modes": sorted({(t.get("mode") or "") for t in targets if t.get("mode")}),
    }


def dashboard_summary(dashboard: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    panels = [panel_summary(p) for p in walk_panels(dashboard.get("panels") or []) if p.get("type") != "row"]
    rows = [
        {"id": p.get("id"), "title": p.get("title") or ""}
        for p in walk_panels(dashboard.get("panels") or [])
        if p.get("type") == "row"
    ]
    variables = []
    templating = dashboard.get("templating") or {}
    for var in templating.get("list") or []:
        if isinstance(var, dict):
            variables.append(
                {
                    "name": var.get("name"),
                    "type": var.get("type"),
                    "label": var.get("label") or "",
                    "queryType": (var.get("query") or {}).get("queryType")
                    if isinstance(var.get("query"), dict)
                    else None,
                }
            )
    return {
        "uid": dashboard.get("uid") or (meta or {}).get("uid"),
        "title": dashboard.get("title") or (meta or {}).get("title"),
        "version": dashboard.get("version") or (meta or {}).get("version"),
        "slug": (meta or {}).get("slug"),
        "time": dashboard.get("time") or {},
        "tags": dashboard.get("tags") or [],
        "panelCount": len(panels),
        "rowCount": len(rows),
        "panels": panels,
        "rows": rows,
        "variables": variables,
        "iframe_path": "/grafana/d/{uid}/{slug}".format(
            uid=dashboard.get("uid") or (meta or {}).get("uid") or "",
            slug=(meta or {}).get("slug") or "",
        ),
    }


def locate_panels(dashboard: dict[str, Any], query: str) -> list[dict[str, Any]]:
    query_l = query.strip().lower()
    hits = []
    for panel in walk_panels(dashboard.get("panels") or []):
        if panel.get("type") == "row":
            continue
        title = str(panel.get("title") or "")
        if str(panel.get("id")) == query.strip() or query_l in title.lower():
            hits.append(panel_summary(panel))
    return hits


def default_datasource(dashboard: dict[str, Any], for_create: bool = False) -> dict[str, str]:
    if for_create:
        return {"type": DS_TYPE, "uid": DS_TEMPLATE_UID}
    for panel in walk_panels(dashboard.get("panels") or []):
        ds = panel.get("datasource")
        if isinstance(ds, dict) and ds.get("uid"):
            return {"type": ds.get("type") or DS_TYPE, "uid": ds["uid"]}
    return {"type": DS_TYPE, "uid": "000000002"}


def default_target(dashboard: dict[str, Any]) -> dict[str, Any]:
    ds = default_datasource(dashboard)
    return {
        "cluster": [],
        "datasource": ds,
        "enableDownSampling": True,
        "expressionList": [],
        "format": "time_series",
        "host": [],
        "mode": "code",
        "module": [],
        "promqlAlias": "",
        "query_configs": [],
        "refId": "A",
        "showLastPoint": False,
        "source": "",
        "step": "",
        "type": "range",
    }


def ensure_target(panel: dict[str, Any], dashboard: dict[str, Any], index: int) -> dict[str, Any]:
    targets = panel.setdefault("targets", [])
    if not isinstance(targets, list):
        raise ToolError("panel.targets is not a list")
    while len(targets) <= index:
        target = default_target(dashboard)
        target["refId"] = chr(ord("A") + len(targets))
        targets.append(target)
    if not isinstance(targets[index], dict):
        raise ToolError(f"targets[{index}] is not an object")
    return targets[index]


def ui_config_to_promql(item: dict[str, Any]) -> str:
    source_label = item.get("data_source_label") or "bk_monitor"
    table = item.get("result_table_id") or ""
    metric = item.get("metric_field") or ""
    prefix = DATA_SOURCE_PREFIX.get(source_label, source_label)
    if source_label == "bk_monitor" and table.startswith("container"):
        # container metrics in BK have no result-table layer in PromQL
        return f"{prefix}:{metric}"
    if source_label == "bk_monitor" and metric.startswith("container_"):
        return f"{prefix}:{metric}"
    table_path = table.replace(".", ":")
    if table_path:
        return f"{prefix}:{table_path}:{metric}"
    return f"{prefix}:{metric}"


def extract_promqls(panel: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for index, target in enumerate(panel.get("targets") or []):
        if not isinstance(target, dict):
            continue
        mode = target.get("mode") or "code"
        if mode == "code":
            source = target.get("source") or ""
            out.append(
                {
                    "target_index": index,
                    "refId": target.get("refId"),
                    "mode": "code",
                    "promql": source,
                    "has_variables": bool(VAR_RE.search(source)),
                    "alias": target.get("promqlAlias") or "",
                }
            )
            continue
        for cfg_index, item in enumerate(target.get("query_configs") or []):
            if not isinstance(item, dict):
                continue
            promql = ui_config_to_promql(item)
            wrapped = f"avg(avg_over_time({promql}[1m]))"
            out.append(
                {
                    "target_index": index,
                    "config_index": cfg_index,
                    "refId": item.get("refId"),
                    "mode": "ui",
                    "promql": wrapped,
                    "raw_metric": promql,
                    "has_variables": False,
                    "alias": item.get("alias") or "",
                    "note": "ui mode reconstructed from query_configs; not the Grafana target.source",
                }
            )
    return out


def validate_query_target(target: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mode = target.get("mode")
    source = (target.get("source") or "").strip()
    configs = target.get("query_configs") or []
    if mode == "ui":
        if source:
            errors.append("ui mode requires empty source")
        if not configs:
            errors.append("ui mode requires non-empty query_configs")
        for item in configs:
            if not isinstance(item, dict):
                errors.append("query_configs item is not an object")
                continue
            metric = item.get("metric_field") or ""
            if "." in metric:
                errors.append(f"metric_field must be the field name only, got {metric!r}")
            label = item.get("data_source_label")
            if label and label not in DATA_SOURCE_PREFIX:
                errors.append(f"unknown data_source_label {label!r}")
            table = item.get("result_table_id") or ""
            if label == "bk_monitor" and table.startswith("container") is False:
                # container exception: some custom metrics have no table
                pass
    elif mode == "code":
        if not source:
            errors.append("code mode requires source PromQL")
        if configs:
            errors.append("code mode should use empty query_configs")
        if "bkmonitor:system:container:" in source:
            errors.append("container metrics must be bkmonitor:<metric>, no result table")
        if source.startswith("custom:system:"):
            errors.append("host metrics use bkmonitor:system, not custom:system")
        if "cpu_summary__bk_" in source or "mem__bk_" in source:
            errors.append("PromQL metric name contains encoded junk")
    elif mode not in (None, ""):
        errors.append(f"unknown mode {mode!r}, expected ui or code")
    return errors


def validate_panel_queries(panel: dict[str, Any]) -> dict[str, Any]:
    errors = []
    for index, target in enumerate(panel.get("targets") or []):
        if not isinstance(target, dict):
            errors.append({"target_index": index, "error": "target is not an object"})
            continue
        for err in validate_query_target(target):
            errors.append({"target_index": index, "error": err})
    return {"panel_id": panel.get("id"), "ok": not errors, "errors": errors}


def apply_set_query(panel: dict[str, Any], dashboard: dict[str, Any], op: dict[str, Any]) -> None:
    index = int(op.get("target_index") or 0)
    target = ensure_target(panel, dashboard, index)
    mode = op.get("mode") or target.get("mode") or "code"
    target["mode"] = mode
    if "promqlAlias" in op:
        target["promqlAlias"] = op["promqlAlias"]
    if mode == "code":
        if "source" not in op:
            raise ToolError("set_query code mode requires source")
        target["source"] = op["source"]
        target["query_configs"] = []
    elif mode == "ui":
        if "query_configs" not in op:
            raise ToolError("set_query ui mode requires query_configs")
        if not isinstance(op["query_configs"], list) or not op["query_configs"]:
            raise ToolError("query_configs must be a non-empty list")
        target["source"] = ""
        target["query_configs"] = copy.deepcopy(op["query_configs"])
    else:
        raise ToolError(f"unsupported query mode {mode!r}")
    errors = validate_query_target(target)
    if errors:
        raise ToolError("query validation failed: " + "; ".join(errors))


def apply_add_panel(dashboard: dict[str, Any], op: dict[str, Any]) -> int:
    panel = copy.deepcopy(op.get("panel") or {})
    if not isinstance(panel, dict) or not panel.get("type"):
        raise ToolError("add_panel requires panel.type")
    if panel.get("type") not in VALID_PANEL_TYPES:
        raise ToolError(f"unsupported panel type {panel.get('type')!r}")
    panel_id = next_panel_id(dashboard)
    panel["id"] = panel_id
    panel.setdefault("title", "新图表")
    panel.setdefault("datasource", default_datasource(dashboard))
    if panel["type"] != "row":
        panel.setdefault("targets", [default_target(dashboard)])
        panel.setdefault("fieldConfig", {"defaults": {}, "overrides": []})
        panel.setdefault("options", copy.deepcopy(DEFAULT_OPTIONS.get(panel["type"], {})))
        panel.setdefault("pluginVersion", "10.4.10")
    placement = op.get("placement") or {}
    if isinstance(placement.get("gridPos"), dict):
        panel["gridPos"] = copy.deepcopy(placement["gridPos"])
    elif placement.get("after_panel_id") is not None:
        after = find_panel(dashboard, int(placement["after_panel_id"]))
        grid = copy.deepcopy(after.get("gridPos") or {"x": 0, "y": 0, "w": 12, "h": 8})
        grid["y"] = int(grid.get("y", 0)) + int(grid.get("h", 8))
        grid.setdefault("x", 0)
        grid.setdefault("w", 12)
        grid.setdefault("h", 8)
        panel["gridPos"] = grid
    else:
        panel["gridPos"] = {"x": 0, "y": max_grid_bottom(dashboard), "w": 12, "h": 8}
    dashboard.setdefault("panels", []).append(panel)
    return panel_id


def apply_operation(dashboard: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    name = op.get("op")
    if not name:
        raise ToolError("operation missing op")

    if name == "set_dashboard_meta":
        for key in ("title", "tags", "time", "refresh", "timezone", "description"):
            if key in op:
                dashboard[key] = copy.deepcopy(op[key])
        return {
            "op": name,
            "changed": [k for k in ("title", "tags", "time", "refresh", "timezone", "description") if k in op],
        }

    if name == "add_panel":
        panel_id = apply_add_panel(dashboard, op)
        return {"op": name, "panel_id": panel_id}

    if name == "add_variable":
        variable = copy.deepcopy(op.get("variable") or {})
        if not variable.get("name"):
            raise ToolError("add_variable requires variable.name")
        templating = dashboard.setdefault("templating", {})
        items = templating.setdefault("list", [])
        if any(isinstance(v, dict) and v.get("name") == variable["name"] for v in items):
            raise ToolError(f"variable {variable['name']!r} already exists")
        items.append(variable)
        return {"op": name, "name": variable["name"]}

    if name == "set_variable":
        var_name = op.get("name")
        patch = op.get("patch") or {}
        items = (dashboard.get("templating") or {}).get("list") or []
        found = None
        for item in items:
            if isinstance(item, dict) and item.get("name") == var_name:
                found = item
                break
        if found is None:
            raise ToolError(f"variable {var_name!r} not found")
        deep_merge(found, patch)
        return {"op": name, "name": var_name}

    if name == "remove_panel":
        panel_id = int(op["panel_id"])
        if not remove_panel(dashboard.setdefault("panels", []), panel_id):
            raise ToolError(f"panel_id {panel_id} not found")
        return {"op": name, "panel_id": panel_id}

    panel_id = int(op.get("panel_id"))
    panel = find_panel(dashboard, panel_id)

    if name == "set_title":
        panel["title"] = op.get("title") or ""
        return {"op": name, "panel_id": panel_id}
    if name == "set_description":
        panel["description"] = op.get("description") or ""
        return {"op": name, "panel_id": panel_id}
    if name == "set_type":
        new_type = op.get("type")
        if new_type not in VALID_PANEL_TYPES:
            raise ToolError(f"unsupported panel type {new_type!r}")
        panel["type"] = new_type
        if new_type in DEFAULT_OPTIONS:
            panel["options"] = copy.deepcopy(DEFAULT_OPTIONS[new_type])
        return {"op": name, "panel_id": panel_id, "type": new_type}
    if name == "set_query":
        apply_set_query(panel, dashboard, op)
        return {"op": name, "panel_id": panel_id, "target_index": int(op.get("target_index") or 0)}
    if name == "set_viz":
        if "fieldConfig" in op:
            panel.setdefault("fieldConfig", {"defaults": {}, "overrides": []})
            if not isinstance(panel["fieldConfig"], dict):
                panel["fieldConfig"] = {"defaults": {}, "overrides": []}
            deep_merge(panel["fieldConfig"], op["fieldConfig"])
        if "options" in op:
            panel.setdefault("options", {})
            if not isinstance(panel["options"], dict):
                panel["options"] = {}
            deep_merge(panel["options"], op["options"])
        if "transformations" in op:
            if not isinstance(op["transformations"], list):
                raise ToolError("transformations must be a list")
            panel["transformations"] = copy.deepcopy(op["transformations"])
        if "transparent" in op:
            panel["transparent"] = bool(op["transparent"])
        return {"op": name, "panel_id": panel_id}
    if name == "set_grid":
        panel["gridPos"] = copy.deepcopy(op.get("gridPos") or op.get("value") or {})
        return {"op": name, "panel_id": panel_id}

    raise ToolError(f"unsupported op {name!r}")


def apply_operations(dashboard: dict[str, Any], operations: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(operations, list) or not operations:
        raise ToolError("operations must be a non-empty list")
    # remove high indices first if mixed with other ops: only sort consecutive removes
    results = []
    uid = dashboard.get("uid")
    dash_id = dashboard.get("id")
    version = dashboard.get("version")
    for op in operations:
        if not isinstance(op, dict):
            raise ToolError("operation must be an object")
        results.append(apply_operation(dashboard, op))
    if uid is not None:
        dashboard["uid"] = uid
    if dash_id is not None:
        dashboard["id"] = dash_id
    if version is not None:
        dashboard["version"] = version
    return results


def ensure_iac_envelope(dashboard: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dashboard)
    out.setdefault("__inputs", copy.deepcopy(DEFAULT_INPUTS))
    out.setdefault("__elements", {})
    out.setdefault("__requires", copy.deepcopy(DEFAULT_REQUIRES))
    return out


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", name.strip()).strip("-")
    return cleaned or "dashboard"


def build_save_payload(
    dashboard: dict[str, Any],
    bk_biz_id: str | int,
    folder: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enveloped = ensure_iac_envelope(dashboard)
    title = enveloped.get("title") or (meta or {}).get("title") or "dashboard"
    folder_name = (folder or "").strip()
    if not folder_name or folder_name.lower() in {"general", "general folder"}:
        path = f"grafana/{safe_filename(title)}.json"
    else:
        path = f"grafana/{safe_filename(folder_name)}/{safe_filename(title)}.json"
    inner = json.dumps(enveloped, ensure_ascii=False, separators=(",", ":"))
    configs_obj = {path: inner}
    return {
        "path": path,
        "uid": enveloped.get("uid"),
        "title": title,
        "mcp_arguments": {
            "body_param": {
                "bk_biz_id": str(bk_biz_id),
                "configs": configs_obj,
            }
        },
        "note": "Pass mcp_arguments unchanged. configs is a dict: path -> Grafana JSON string. MCP schema may say string; the API requires a dict.",
    }


def cmd_ingest(args: argparse.Namespace) -> int:
    raw = load_json(args.input)
    dashboard, meta = unwrap_dashboard(raw)
    dump_json(args.out, dashboard)
    if args.meta:
        dump_json(args.meta, meta)
    return print_json(
        {
            "ok": True,
            "file": str(Path(args.out)),
            "meta": meta,
            "summary": dashboard_summary(dashboard, meta),
        }
    )


def cmd_summary(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    meta = load_json(args.meta) if args.meta else {}
    return print_json(dashboard_summary(dashboard, meta))


def cmd_get_panel(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    panel = find_panel(dashboard, args.panel_id)
    return print_json(panel)


def cmd_get_queries(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    if args.panel_id is not None:
        panels = [find_panel(dashboard, args.panel_id)]
    else:
        panels = [p for p in walk_panels(dashboard.get("panels") or []) if p.get("type") != "row"]
    payload = []
    for panel in panels:
        payload.append(
            {
                "id": panel.get("id"),
                "title": panel.get("title"),
                "type": panel.get("type"),
                "targets": [summarize_target(t) for t in (panel.get("targets") or []) if isinstance(t, dict)],
            }
        )
    return print_json(payload)


def cmd_locate(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    hits = locate_panels(dashboard, args.query)
    if not hits:
        return print_json({"ok": False, "matches": [], "error": "no panel matched"}, 2)
    if len(hits) > 1 and not args.allow_multiple:
        return print_json(
            {
                "ok": False,
                "ambiguous": True,
                "matches": hits,
                "error": "multiple panels matched; ask the user which panel_id",
            },
            2,
        )
    return print_json({"ok": True, "matches": hits})


def cmd_apply(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    ops_raw = load_json(args.ops)
    operations = ops_raw.get("operations") if isinstance(ops_raw, dict) else ops_raw
    results = apply_operations(dashboard, operations)
    out = args.out or args.file
    dump_json(out, dashboard)
    meta = load_json(args.meta) if args.meta else {}
    return print_json(
        {
            "ok": True,
            "file": str(Path(out)),
            "changed": results,
            "summary": dashboard_summary(dashboard, meta),
        }
    )


def cmd_validate_query(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    panel = find_panel(dashboard, args.panel_id)
    result = validate_panel_queries(panel)
    return print_json(result, 0 if result["ok"] else 2)


def cmd_extract_promql(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    panel = find_panel(dashboard, args.panel_id)
    return print_json(
        {
            "panel_id": panel.get("id"),
            "title": panel.get("title"),
            "queries": extract_promqls(panel),
        }
    )


def cmd_build_save(args: argparse.Namespace) -> int:
    dashboard = load_json(args.file)
    meta = load_json(args.meta) if args.meta else {}
    payload = build_save_payload(dashboard, args.bk_biz_id, args.folder or "", meta)
    if args.out:
        dump_json(args.out, payload)
        payload["payload_file"] = str(Path(args.out))
    return print_json(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BK iframe Grafana dashboard surgery")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="Unwrap MCP/API payload to raw Grafana JSON on disk")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--meta")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("summary")
    p.add_argument("--file", required=True)
    p.add_argument("--meta")
    p.set_defaults(func=cmd_summary)

    p = sub.add_parser("get-panel")
    p.add_argument("--file", required=True)
    p.add_argument("--panel-id", type=int, required=True)
    p.set_defaults(func=cmd_get_panel)

    p = sub.add_parser("get-queries")
    p.add_argument("--file", required=True)
    p.add_argument("--panel-id", type=int)
    p.set_defaults(func=cmd_get_queries)

    p = sub.add_parser("locate")
    p.add_argument("--file", required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--allow-multiple", action="store_true")
    p.set_defaults(func=cmd_locate)

    p = sub.add_parser("apply")
    p.add_argument("--file", required=True)
    p.add_argument("--ops", required=True)
    p.add_argument("--out")
    p.add_argument("--meta")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("validate-query")
    p.add_argument("--file", required=True)
    p.add_argument("--panel-id", type=int, required=True)
    p.set_defaults(func=cmd_validate_query)

    p = sub.add_parser("extract-promql")
    p.add_argument("--file", required=True)
    p.add_argument("--panel-id", type=int, required=True)
    p.set_defaults(func=cmd_extract_promql)

    p = sub.add_parser("build-save")
    p.add_argument("--file", required=True)
    p.add_argument("--bk-biz-id", required=True)
    p.add_argument("--folder", default="")
    p.add_argument("--meta")
    p.add_argument("--out")
    p.set_defaults(func=cmd_build_save)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ToolError as exc:
        payload = {"ok": False, "error": str(exc)}
        payload.update(exc.extra)
        return print_json(payload, 2)
    except json.JSONDecodeError as exc:
        return print_json({"ok": False, "error": f"invalid JSON: {exc}"}, 2)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        return print_json({"ok": False, "error": str(exc)}, 2)


if __name__ == "__main__":
    sys.exit(main())
