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
    evidence = [
        item
        for item in analysis.get("evidence", [])
        if item.get("evidence_id") in evidence_ids
        or (entity_ref is not None and item.get("entity_ref") == entity_ref)
        or (edge_ref is not None and item.get("edge_ref") == edge_ref)
    ]
    capabilities = copy.deepcopy(analysis.get("capabilities", {}))
    capabilities["context_expansion"] = bool(entity_ref and next(_matching_context_graphs(analysis, entity_ref), None))
    return copy.deepcopy(
        {
            "protocol": analysis["protocol"],
            "version": analysis["version"],
            "producer": analysis.get("producer", {}),
            "root_causes": [item for item in analysis.get("root_causes", []) if item.get("entity_ref") == entity_ref],
            "evidence": evidence,
            "capabilities": capabilities,
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
