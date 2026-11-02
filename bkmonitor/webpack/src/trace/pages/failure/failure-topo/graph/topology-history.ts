import { topologyEdgeId } from '../snapshot-analysis';

import type { DiffItem, TopoCacheFrame } from '../types/g6';
import type { IEdge, ITopoCombo, ITopoNode } from '../types/topo';

/** Keep historical categories when the latest snapshot no longer contains their nodes. */
export function historyCombos(complete: TopoCacheFrame, latest: TopoCacheFrame): ITopoCombo[] {
  const combos = new Map<string, ITopoCombo>();
  for (const combo of [...(latest.combos ?? []), ...(complete.combos ?? [])]) {
    combos.set(String(combo.id), { ...combo });
  }
  // Older monitor APIs omit complete.combos; the node's frozen category is authoritative.
  for (const node of complete.nodes) {
    const category = node.entity?.rank?.rank_category;
    const id = node.comboId;
    if (id != null && !combos.has(String(id)) && category && String(category.category_id) === String(id)) {
      combos.set(String(id), {
        id: String(id),
        label: category.category_alias,
        dataType: category.category_name,
      });
    }
  }
  return [...combos.values()];
}

/** Fail before ELK receives dangling endpoints or nodes outside the layout hierarchy. */
export function validateTopology(data: TopoCacheFrame): void {
  const combos = new Set((data.combos ?? []).map(combo => String(combo.id)));
  const nodes = new Set(data.nodes.map(node => node.id));
  if (
    data.nodes.some(node => node.comboId == null || !combos.has(String(node.comboId))) ||
    (data.edges ?? []).some(edge => !nodes.has(edge.source) || !nodes.has(edge.target)) ||
    (data.sub_combos ?? []).some(combo => !combos.has(String(combo.comboId)))
  ) {
    throw new Error('INVALID_TOPOLOGY_HISTORY');
  }
}

/** Each frame retains its prior state; later deletions must not leak backwards. */
export function prepareHistoryFrames(diff: DiffItem[]): void {
  const nodes = new Map<string, ITopoNode>();
  const edges = new Map<string, IEdge>();
  const subCombos = new Map<string, ITopoCombo>();
  for (const frame of diff) {
    frame.showNodes = [...nodes.values()];
    frame.showSubCombos = [...subCombos.values()];
    for (const node of frame.content.nodes) nodes.set(node.id, node);
    for (const edge of frame.content.edges ?? []) edges.set(topologyEdgeId(edge), edge);
    for (const combo of frame.content.sub_combos ?? []) subCombos.set(String(combo.id), combo);
    frame.showEdges = [...edges.values()];
  }
}

export function frameNodes(frame: DiffItem): Map<string, ITopoNode> {
  return new Map([...frame.showNodes, ...frame.content.nodes].map(node => [node.id, node]));
}

export function frameEdges(frame: DiffItem): IEdge[] {
  const nodes = frameNodes(frame);
  const edges = new Map([...frame.showEdges, ...(frame.content.edges ?? [])].map(edge => [topologyEdgeId(edge), edge]));
  return [...edges.values()].filter(
    edge => !edge.is_deleted && [edge.source, edge.target].every(id => nodes.has(id) && !nodes.get(id)?.is_deleted)
  );
}
