import type { EventStatistics, IMetricItem, MetricEvent } from './types/topo';

export interface SnapshotEvidence {
  evidence_id: string;
  evidence_type: string;
  evidence_descriptor: { kind: string; name: string; source?: string };
  unit?: string;
  response: {
    meta: { status: string; total?: number };
    data: {
      time: number;
      value?: number | null;
      label?: number | null;
      dimensions?: unknown[];
      event_name?: string;
      event_source?: string;
      event_level?: string;
    }[];
  };
}

export interface SnapshotScore {
  kind: string;
  value: number | null;
  method?: string | null;
}

export interface SnapshotAnalysis {
  protocol: string;
  version: string;
  producer?: { engine?: string; algorithm_version?: string | null };
  root_causes?: {
    entity_ref: string;
    rank: number | null;
    reason?: string | string[] | null;
    scores: SnapshotScore[];
  }[];
  evidence?: SnapshotEvidence[];
  capabilities?: {
    realtime_metrics?: boolean;
    realtime_events?: boolean;
    context_expansion?: boolean;
    snapshot_metrics?: boolean;
  };
}

export function snapshotMetrics(analysis?: SnapshotAnalysis | null): IMetricItem[] | null {
  if (!analysis) return null;
  if (analysis.protocol !== 'graph-rca-snapshot' || analysis.version !== '1') return [];
  return (analysis.evidence || [])
    .filter(item => item.evidence_type === 'metric')
    .flatMap(item => {
      if (!['OK', 'PARTIAL'].includes(item.response?.meta?.status)) return [];
      const series: IMetricItem['time_series'] = {};
      for (const point of item.response.data || []) {
        const value = point.value;
        if (!Number.isFinite(point.time) || (value !== null && typeof value !== 'number')) continue;
        if (typeof value === 'number' && !Number.isFinite(value)) continue;
        const dimensions = point.dimensions || [];
        const key = dimensions.length ? JSON.stringify(dimensions) : 'default';
        if (!series[key]) series[key] = { datapoints: [], unit: item.unit || '' };
        series[key].datapoints.push([point.time, value, point.label || 0]);
      }
      if (!Object.values(series).some(value => value.datapoints.some(point => point[1] !== null))) return [];
      for (const value of Object.values(series)) value.datapoints.sort((a, b) => a[0] - b[0]);
      return [
        {
          display_by_dimensions: Object.keys(series).some(key => key !== 'default'),
          metric_alias: item.evidence_descriptor.name,
          metric_name: item.evidence_descriptor.name,
          metric_type: 'snapshot',
          time_series: series,
        },
      ];
    });
}

export function allowsRealtimeMetrics(analysis?: SnapshotAnalysis | null): boolean {
  return (
    !analysis ||
    (analysis.protocol === 'graph-rca-snapshot' &&
      analysis.version === '1' &&
      analysis.capabilities?.realtime_metrics === true)
  );
}

export function allowsRealtimeEvents(analysis?: SnapshotAnalysis | null): boolean {
  return (
    !analysis ||
    (analysis.protocol === 'graph-rca-snapshot' &&
      analysis.version === '1' &&
      analysis.capabilities?.realtime_events === true)
  );
}

export function snapshotEvents(
  analysis: SnapshotAnalysis | null | undefined,
  unavailable: string
): {
  statistics: EventStatistics;
  events: MetricEvent[];
} | null {
  if (!analysis) return null;
  const statistics: EventStatistics = { event_source: {}, event_level: {} };
  const groups = new Map<string, MetricEvent>();
  if (analysis.protocol !== 'graph-rca-snapshot' || analysis.version !== '1') return { statistics, events: [] };
  for (const item of analysis.evidence || []) {
    if (item.evidence_type !== 'event' || !['OK', 'PARTIAL'].includes(item.response?.meta?.status)) continue;
    for (const record of item.response.data || []) {
      if (!Number.isFinite(record.time)) continue;
      const source = record.event_source || item.evidence_descriptor.source || unavailable;
      const level = record.event_level || unavailable;
      const name = record.event_name || item.evidence_descriptor.name || unavailable;
      const key = JSON.stringify([source, level, name]);
      if (!groups.has(key))
        groups.set(key, { event_source: source, event_level: level, event_name: name, series: [{ datapoints: [] }] });
      // Each frozen record represents one event; this is a count, not an anomaly score.
      groups.get(key)!.series[0].datapoints.push([record.time, 1]);
      statistics.event_source[source] = (statistics.event_source[source] || 0) + 1;
      statistics.event_level[level] = (statistics.event_level[level] || 0) + 1;
    }
  }
  return { statistics, events: Array.from(groups.values()) };
}

export function topologyEdgeId(edge: {
  id?: string;
  source?: string;
  target?: string;
  edge_type?: string;
  properties?: { edge_id?: string; relation?: unknown };
}): string {
  return (
    edge.id ||
    edge.properties?.edge_id ||
    JSON.stringify([edge.source, edge.target, edge.edge_type, edge.properties?.relation ?? null])
  );
}
