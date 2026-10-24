"""Validate stored display snapshots without fetching or changing algorithm results."""


def snapshot_display_status(content):
    if not isinstance(content, dict):
        return "INVALID_DATA"
    # A graph snapshot locator was stored, but its payload did not arrive.
    if not content or "incident_propagation_graph" not in content:
        return "SYNC_FAILED"
    graph = content["incident_propagation_graph"]
    if not isinstance(graph, dict):
        return "INVALID_DATA"
    nodes, edges = graph.get("entities", []), graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return "INVALID_DATA"
    categories = content.get("product_hierarchy_category", {})
    ranks = content.get("product_hierarchy_rank", {})
    if not isinstance(categories, dict) or not isinstance(ranks, dict):
        return "INVALID_DATA"
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("entity_id"), str) or not node["entity_id"]:
            return "INVALID_DATA"
        if node["entity_id"] in ids:
            return "INVALID_DATA"
        ids.add(node["entity_id"])
        rank_name = node.get("rank_name")
        rank = ranks.get(rank_name) if isinstance(rank_name, str) else None
        if not isinstance(rank, dict) or not isinstance(rank.get("rank_category"), str):
            return "INVALID_DATA"
        if rank["rank_category"] not in categories:
            return "INVALID_DATA"
    for edge in edges:
        if not isinstance(edge, dict):
            return "INVALID_DATA"
        if any(not isinstance(edge.get(key), str) or edge[key] not in ids for key in ("source_id", "target_id")):
            return "INVALID_DATA"
    return "OK" if nodes else "NO_DATA"
