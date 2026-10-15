export type EdgeRelation = 'call' | 'dependency' | 'propagation' | 'unknown';

interface RelationEdge {
  edge_type?: string;
  properties?: {
    relation?: unknown;
    relation_type?: unknown;
  };
}

function explicitRelation(value: unknown): EdgeRelation {
  if (value === 'BELONG_TO' || value === 0 || value === '0') return 'dependency';
  if (value === 'SERVICE_CALL' || value === 1 || value === '1') return 'call';
  return 'unknown';
}

export function getEdgeRelation(edge: RelationEdge): EdgeRelation {
  const { relation_type: type, relation } = edge.properties || {};
  // Explicit snapshot relations take precedence over legacy drawing categories.
  if (type !== undefined && type !== null && type !== '') return explicitRelation(type);
  if (relation !== undefined && relation !== null && relation !== '') return explicitRelation(relation);
  if (edge.edge_type === 'dependency') return 'dependency';
  if (edge.edge_type === 'ebpf_call') return 'call';
  // Older small-model snapshots also use spread for causal propagation, not necessarily a call.
  return edge.edge_type === 'spread' ? 'propagation' : 'unknown';
}

export function isDirectedEdge(edge: RelationEdge): boolean {
  const relation = getEdgeRelation(edge);
  return relation === 'call' || relation === 'propagation';
}

export function edgeRelationLabel(edge: RelationEdge, t: (message: string) => string): string {
  switch (getEdgeRelation(edge)) {
    case 'dependency':
      return t('从属关系');
    case 'call':
      return t('调用关系');
    case 'propagation':
      return t('传播关系');
    default:
      return t('未知关系');
  }
}
