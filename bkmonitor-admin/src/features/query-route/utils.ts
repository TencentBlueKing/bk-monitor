import { queryRouteQuerySchema, type QueryRouteQuery } from './schemas';

export const QUERY_ROUTE_PAGE_SIZE = 20;
const MAX_HISTORY_COUNT = 5;

export interface QueryRouteDraft {
  spaceUid: string;
  tableIdsText: string;
  dataLabelsText: string;
  fieldNamesText: string;
}

export interface QueryRouteHistoryEntry {
  draft: QueryRouteDraft;
  timestamp: number;
}

function getHistoryKey(environmentId: string, tenantId: string): string {
  return `qr_history_${environmentId}_${tenantId}`;
}

export function loadQueryRouteHistory(
  environmentId: string,
  tenantId: string
): QueryRouteHistoryEntry[] {
  try {
    const raw = localStorage.getItem(getHistoryKey(environmentId, tenantId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((entry): entry is QueryRouteHistoryEntry => {
      if (entry == null || typeof entry !== 'object') return false;
      const record = entry as Record<string, unknown>;
      return record.draft != null && typeof record.draft === 'object';
    });
  } catch {
    return [];
  }
}

export function saveQueryRouteHistory(
  environmentId: string,
  tenantId: string,
  draft: QueryRouteDraft
) {
  if (!hasQueryRouteDraftInput(draft)) return;

  const key = getHistoryKey(environmentId, tenantId);
  const history = loadQueryRouteHistory(environmentId, tenantId);

  const isDuplicate = history.some(
    (entry) =>
      entry.draft.spaceUid === draft.spaceUid &&
      entry.draft.tableIdsText === draft.tableIdsText &&
      entry.draft.dataLabelsText === draft.dataLabelsText &&
      entry.draft.fieldNamesText === draft.fieldNamesText
  );

  if (isDuplicate) return;

  history.unshift({ draft, timestamp: Date.now() });
  if (history.length > MAX_HISTORY_COUNT) {
    history.length = MAX_HISTORY_COUNT;
  }

  try {
    localStorage.setItem(key, JSON.stringify(history));
  } catch {
    // localStorage full or unavailable, silently fail
  }
}

export function buildQueryRouteQuery(draft: QueryRouteDraft, bkTenantId: string): QueryRouteQuery {
  return queryRouteQuerySchema.parse({
    bkTenantId,
    spaceUid: draft.spaceUid.trim() || undefined,
    tableIds: parseList(draft.tableIdsText),
    dataLabels: parseList(draft.dataLabelsText),
    fieldNames: parseList(draft.fieldNamesText)
  });
}

export function getQueryRouteDraftFromSearch(search: object): QueryRouteDraft {
  return {
    spaceUid: getStringSearch(search, 'space_uid') ?? getStringSearch(search, 'spaceUid') ?? '',
    tableIdsText: getStringSearch(search, 'table_ids') ?? getStringSearch(search, 'tableIds') ?? '',
    dataLabelsText:
      getStringSearch(search, 'data_labels') ?? getStringSearch(search, 'dataLabels') ?? '',
    fieldNamesText:
      getStringSearch(search, 'field_names') ?? getStringSearch(search, 'fieldNames') ?? ''
  };
}

export function buildQueryRouteSearch(query: QueryRouteQuery, baseSearch: Record<string, string>) {
  return compactSearch({
    ...baseSearch,
    space_uid: query.spaceUid,
    table_ids: query.tableIds.join('\n'),
    data_labels: query.dataLabels.join('\n'),
    field_names: query.fieldNames.join('\n')
  });
}

export function hasQueryRouteDraftInput(draft: QueryRouteDraft): boolean {
  return Boolean(
    draft.spaceUid.trim() ||
    draft.tableIdsText.trim() ||
    draft.dataLabelsText.trim() ||
    draft.fieldNamesText.trim()
  );
}

export function parseList(value: string): string[] {
  const values: string[] = [];
  const seen = new Set<string>();

  for (const item of value.split(/[\s,]+/)) {
    const normalized = item.trim();
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    values.push(normalized);
    seen.add(normalized);
  }

  return values;
}

export function filterItems<T>(items: T[], keyword: string): T[] {
  if (!keyword) {
    return items;
  }

  return items.filter((item) => JSON.stringify(item).toLowerCase().includes(keyword));
}

export function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

function getStringSearch(search: object, key: string): string | undefined {
  const values = search as Record<string, unknown>;
  if (!(key in values)) {
    return undefined;
  }
  const value = values[key];
  if (typeof value === 'string') {
    return value;
  }
  if (Array.isArray(value)) {
    return value.join('\n');
  }
  return undefined;
}

function compactSearch(search: Record<string, string | undefined>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(search).filter(
      (entry): entry is [string, string] => entry[1] !== undefined && entry[1] !== ''
    )
  );
}
