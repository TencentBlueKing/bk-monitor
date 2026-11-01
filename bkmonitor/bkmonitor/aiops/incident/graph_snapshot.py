"""Read the versioned analysis snapshot without changing its stored algorithm result."""

import copy
import json


def graph_analysis(content):
    value = content.get("graph_analysis")
    if isinstance(value, dict) and value.get("protocol") == "graph-rca-snapshot" and value.get("version") == "1":
        return value
    return None


def edge_identity(edge):
    properties = edge.get("properties") or {}
    return properties.get("edge_id") or json.dumps(
        [
            edge.get("source_id", edge.get("source")),
            edge.get("target_id", edge.get("target")),
            edge.get("edge_type"),
            properties.get("relation"),
        ],
        separators=(",", ":"),
    )


def target_analysis(content, *, entity_ref=None, edge_ref=None):
    if (entity_ref is None) == (edge_ref is None):
        raise ValueError("exactly_one_snapshot_target_required")
    analysis = graph_analysis(content)
    if analysis is None:
        if content.get("graph_analysis") is not None:
            return {"protocol": "graph-rca-snapshot", "version": "unsupported", "capabilities": {}}
        return None
    evidence_ids = {
        link.get("evidence_ref")
        for link in analysis.get("links", [])
        if (entity_ref is not None and link.get("entity_ref") == entity_ref)
        or (edge_ref is not None and link.get("edge_ref") == edge_ref)
    }
    owner_key, owner_ref = ("entity_ref", entity_ref) if entity_ref is not None else ("edge_ref", edge_ref)
    other_key = "edge_ref" if entity_ref is not None else "entity_ref"
    evidence = [
        item
        for item in analysis.get("evidence", [])
        if item.get(owner_key) in (None, owner_ref)
        and item.get(other_key) is None
        and (item.get("evidence_id") in evidence_ids or item.get(owner_key) == owner_ref)
    ]
    capabilities = copy.deepcopy(analysis.get("capabilities", {}))
    # Whole-graph coverage can come exclusively from edges or another node.
    # A target's capabilities must describe only its own frozen observations.
    capabilities["snapshot_metrics"] = any(item.get("evidence_type") == "metric" for item in evidence)
    capabilities["snapshot_events"] = any(item.get("evidence_type") == "event" for item in evidence)
    capabilities["root_causes"] = any(item.get("entity_ref") == entity_ref for item in analysis.get("root_causes", []))
    capabilities["context_expansion"] = bool(entity_ref and next(_matching_context_graphs(analysis, entity_ref), None))
    return copy.deepcopy(
        {
            "protocol": analysis["protocol"],
            "version": analysis["version"],
            "producer": analysis.get("producer", {}),
            "root_causes": [item for item in analysis.get("root_causes", []) if item.get("entity_ref") == entity_ref],
            "evidence": evidence,
            "capabilities": capabilities,
            "availability": {kind: evidence_availability(evidence, kind) for kind in ("metric", "event")},
            "snapshot_context": snapshot_context(content),
            "target": {"entity_ref": entity_ref, "edge_ref": edge_ref},
        }
    )


def evidence_availability(evidence, kind):
    items = [item for item in evidence if item.get("evidence_type") == kind]
    metadata = [(item.get("response") or {}).get("meta") or {} for item in items]
    statuses = sorted({meta.get("status") or "UNKNOWN" for meta in metadata})
    count = sum(len((item.get("response") or {}).get("data") or []) for item in items)
    if not items:
        status = "NOT_PROVIDED"
    elif any(meta.get("truncated") or meta.get("has_more") or meta.get("data_missing") for meta in metadata):
        status = "PARTIAL"
    elif count:
        status = "OK" if statuses == ["OK"] else "PARTIAL"
    elif len(statuses) == 1:
        status = "NO_DATA" if statuses == ["OK"] else statuses[0]
    else:
        status = "PARTIAL"
    return {"status": status, "evidence_count": len(items), "record_count": count, "source_statuses": statuses}


def snapshot_context(content):
    """Presentation metadata only; never infer observation time from a sync time."""
    analysis = graph_analysis(content)
    if analysis is None:
        return None
    run = analysis.get("analysis") or {}
    return copy.deepcopy(
        {
            "snapshot_id": content.get("snapshot_id"),
            "identity": analysis.get("identity", {}),
            "analysis_status": run.get("status"),
            "analysis_window": run.get("window"),
            "query_window": run.get("query_window"),
            "producer_semantics": (analysis.get("extensions") or {}).get("snapshot_semantics"),
            "evidence_mode": "frozen",
            "frame_evidence_mode": "replace",
            "walk_rounds_semantics": "traversal",
            "aggregation_semantics": "display_only",
        }
    )


def _matching_context_graphs(analysis, entity_ref):
    if not analysis.get("capabilities", {}).get("context_expansion"):
        return
    for context in analysis.get("context_graphs", []):
        graph = context.get("graph", {})
        context_entities = graph.get("entities", [])
        if context.get("entity_ref") not in (None, entity_ref):
            continue
        if not any(item.get("entity_id") == entity_ref for item in context_entities):
            continue
        yield graph


def context_graph(content, entity_ref):
    analysis = graph_analysis(content)
    if analysis is None:
        return None
    entities, edges = {}, {}
    for graph in _matching_context_graphs(analysis, entity_ref):
        entities.update((item["entity_id"], item) for item in graph.get("entities", []))
        edges.update((edge_identity(item), item) for item in graph.get("edges", []))
    if not entities:
        return None
    result = copy.deepcopy(content)
    result["incident_propagation_graph"] = {
        "entities": list(entities.values()),
        "edges": [edge for edge in edges.values() if edge["source_id"] in entities and edge["target_id"] in entities],
    }
    result["incident_alerts"] = [
        item for item in result.get("incident_alerts", []) if item.get("entity_id") in entities
    ]
    return copy.deepcopy(result)
