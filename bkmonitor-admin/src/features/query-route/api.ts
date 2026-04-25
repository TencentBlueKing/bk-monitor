import { compactObject } from '../../shared/utils/format';
import type { AdminEnvironment } from '../environments/schemas';
import { kernelRpcClient } from '../kernel-rpc/client';
import {
  queryRouteResponseSchema,
  type QueryRouteDataLabelEntry,
  type QueryRouteDiagnostic,
  type QueryRouteField,
  type QueryRouteFilterCondition,
  type QueryRouteFilterGroup,
  type QueryRouteQuery,
  type QueryRouteRefreshResult,
  type QueryRouteResponse,
  type QueryRouteResultTableDetail,
  type QueryRouteSpaceEntry
} from './schemas';

export async function queryRoutes(
  environment: AdminEnvironment,
  query: QueryRouteQuery
): Promise<QueryRouteResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'query_route.query',
    params: toBackendParams(query)
  });

  return queryRouteResponseSchema.parse(normalizeQueryRoutePayload(envelope.data, query, envelope.warnings));
}

export async function refreshQueryRoutes(
  environment: AdminEnvironment,
  query: QueryRouteQuery
): Promise<QueryRouteResponse> {
  const envelope = await kernelRpcClient.call<unknown>({
    environment,
    operation: 'query_route.refresh',
    params: toBackendParams(query)
  });

  return queryRouteResponseSchema.parse(
    normalizeQueryRoutePayload(envelope.data, query, envelope.warnings, true)
  );
}

function toBackendParams(query: QueryRouteQuery): Record<string, unknown> {
  return compactObject({
    bk_tenant_id: query.bkTenantId,
    space_uid: query.spaceUid,
    table_ids: query.tableIds,
    data_labels: query.dataLabels,
    field_names: query.fieldNames,
    refresh_targets: query.refreshTargets
  });
}

function normalizeQueryRoutePayload(
  payload: unknown,
  query: QueryRouteQuery,
  warnings: unknown[] = [],
  fromRefresh = false
): QueryRouteResponse {
  const source = isRecord(payload) ? payload : {};
  const details = normalizeDetails(firstDefined(source.result_table_details, source.result_table_detail), query);
  const detailMap = buildDetailMap(details);
  const rawDataLabelRoutes = normalizeDataLabelRoutes(
    firstDefined(source.data_label_routes, source.data_label_to_result_table),
    query,
    detailMap
  );
  const spaceRoutes = normalizeSpaceRoutes(
    firstDefined(source.space_routes, source.space_route, source.space_to_result_table),
    query,
    rawDataLabelRoutes,
    detailMap
  );
  const spaceTableIds = new Set(spaceRoutes.map((route) => route.table_id));
  const dataLabelRoutes = rawDataLabelRoutes.map((route) => ({
    ...route,
    table_ids: route.table_ids.map((table) => ({
      ...table,
      in_space: table.in_space || spaceTableIds.has(table.table_id)
    }))
  }));
  const diagnostics = normalizeDiagnostics(source.diagnostics, query, spaceRoutes, dataLabelRoutes, details);
  const refresh = normalizeRefreshResult(payload, fromRefresh);

  return {
    space_uid: readString(source.space_uid) ?? readNestedString(source.space_route, 'space_uid') ?? query.spaceUid ?? null,
    inputs: {
      spaceUid: query.spaceUid,
      tableIds: query.tableIds,
      dataLabels: query.dataLabels,
      fieldNames: query.fieldNames
    },
    space_routes: spaceRoutes,
    data_label_routes: dataLabelRoutes,
    result_table_details: details,
    diagnostics,
    refresh,
    warnings: normalizeWarnings(warnings)
  };
}

function normalizeSpaceRoutes(
  value: unknown,
  query: QueryRouteQuery,
  dataLabelRoutes: QueryRouteDataLabelEntry[],
  detailMap: Map<string, QueryRouteResultTableDetail>
): QueryRouteSpaceEntry[] {
  const tableIdsFromDataLabels = new Set(
    dataLabelRoutes.flatMap((route) => route.table_ids.map((table) => table.table_id))
  );
  const inputTableIds = new Set(query.tableIds);
  const entries = normalizeRouteItems(readRouteItems(value), 'table_id');

  return sortByInputTableIds(
    entries.map(({ key, raw }) => {
      const record = isRecord(raw) ? raw : {};
      const tableId = readString(record.table_id) ?? key;

      return {
        table_id: tableId,
        filters: normalizeFilterGroups(firstDefined(record.filter_groups, record.filters, record.filter)),
        in_input_table_ids: inputTableIds.has(tableId),
        in_any_data_label: tableIdsFromDataLabels.has(tableId),
        has_detail: detailMap.get(tableId)?.exists ?? false,
        raw
      };
    }),
    query.tableIds,
    (item) => item.table_id
  );
}

function normalizeDataLabelRoutes(
  value: unknown,
  query: QueryRouteQuery,
  detailMap: Map<string, QueryRouteResultTableDetail>
): QueryRouteDataLabelEntry[] {
  const inputTableIds = new Set(query.tableIds);
  const spaceTableIds = new Set(readRouteTableIds(value, 'space_table_ids'));
  const entries = normalizeRouteItems(value, 'data_label');

  return entries.map(({ key, raw }) => {
    const record = isRecord(raw) ? raw : {};
    const dataLabel = readString(record.data_label) ?? key;
    const tableIds = readRouteTableIds(firstDefined(record.table_ids, record.result_table_ids, raw));

    return {
      data_label: dataLabel,
      exists: readBoolean(record.exists) ?? tableIds.length > 0,
      table_ids: sortByInputTableIds(
        tableIds.map((tableId) => ({
          table_id: tableId,
          in_space: spaceTableIds.size === 0 ? false : spaceTableIds.has(tableId),
          has_detail: detailMap.get(tableId)?.exists ?? false,
          in_input_table_ids: inputTableIds.has(tableId)
        })),
        query.tableIds,
        (item) => item.table_id
      ),
      raw
    };
  });
}

function normalizeDetails(value: unknown, query: QueryRouteQuery): QueryRouteResultTableDetail[] {
  const entries = normalizeRouteItems(value, 'table_id');
  const details = entries.map(({ key, raw }) => normalizeDetail(key, raw, query.fieldNames));
  const detailTableIds = new Set(
    details.flatMap((detail) => [detail.table_id, detail.normalized_table_id].filter(Boolean))
  );

  for (const tableId of query.tableIds) {
    if (!detailTableIds.has(tableId)) {
      details.push(normalizeDetail(tableId, null, query.fieldNames));
    }
  }

  return details;
}

function normalizeDetail(
  key: string,
  raw: unknown,
  fieldNames: string[]
): QueryRouteResultTableDetail {
  const record = isRecord(raw) ? raw : {};
  const detail = isRecord(record.detail) ? record.detail : record;
  const summary = isRecord(record.summary) ? record.summary : {};
  const tableId = readString(record.table_id) ?? readString(detail.table_id) ?? key;
  const normalizedTableId = readString(record.normalized_table_id);
  const exists = readBoolean(record.exists) ?? raw !== null;
  const fields = normalizeFields(firstDefined(record.fields, detail.fields));
  const fieldNameSet = new Set(fields.map((field) => field.field_name));

  return {
    table_id: tableId,
    normalized_table_id: normalizedTableId,
    exists,
    storage_type: readString(firstDefined(record.storage_type, summary.storage_type, detail.storage_type)) ?? null,
    storage_id: readStringOrNumber(firstDefined(record.storage_id, summary.storage_id, detail.storage_id)) ?? null,
    db: readString(firstDefined(record.db, summary.db, detail.db, detail.database)) ?? null,
    measurement: readString(firstDefined(record.measurement, summary.measurement, detail.measurement)) ?? null,
    field_count: readNumber(record.field_count) ?? fields.length,
    matched_field_names: fieldNames.filter((fieldName) => fieldNameSet.has(fieldName)),
    missing_field_names: exists ? fieldNames.filter((fieldName) => !fieldNameSet.has(fieldName)) : fieldNames,
    fields,
    detail: raw
  };
}

function normalizeFields(value: unknown): QueryRouteField[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item): QueryRouteField[] => {
    if (typeof item === 'string') {
      return [{ field_name: item, raw: item }];
    }
    if (!isRecord(item)) {
      return [];
    }
    const fieldName = readString(firstDefined(item.field_name, item.name));
    if (!fieldName) {
      return [];
    }

    return [
      {
        field_name: fieldName,
        field_type: readString(firstDefined(item.field_type, item.type)) ?? null,
        tag: readString(item.tag) ?? null,
        description: readString(item.description) ?? null,
        alias_name: readString(item.alias_name) ?? null,
        raw: item
      }
    ];
  });
}

function normalizeFilterGroups(value: unknown): QueryRouteFilterGroup[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item) => ({
    conditions: normalizeFilterConditions(item),
    raw: item
  }));
}

function normalizeFilterConditions(value: unknown): QueryRouteFilterCondition[] {
  if (isRecord(value) && Array.isArray(value.conditions)) {
    return value.conditions.flatMap((condition) => normalizeFilterConditions(condition));
  }

  if (isRecord(value) && (value.field || value.key || value.name)) {
    const field = readString(firstDefined(value.field, value.key, value.name)) ?? 'unknown';
    return [
      {
        field,
        operator: readString(firstDefined(value.operator, value.method, value.op)) ?? '=',
        value: value.value
      }
    ];
  }

  if (!isRecord(value)) {
    return [];
  }

  return Object.entries(value)
    .filter(([key]) => key !== 'conditions')
    .map(([field, conditionValue]) => ({
      field,
      operator: '=',
      value: conditionValue
    }));
}

function normalizeDiagnostics(
  value: unknown,
  query: QueryRouteQuery,
  spaceRoutes: QueryRouteSpaceEntry[],
  dataLabelRoutes: QueryRouteDataLabelEntry[],
  details: QueryRouteResultTableDetail[]
): QueryRouteDiagnostic[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => normalizeDiagnosticItem(item, index));
  }

  return buildDiagnostics(query, spaceRoutes, dataLabelRoutes, details);
}

function normalizeDiagnosticItem(value: unknown, index: number): QueryRouteDiagnostic[] {
  if (!isRecord(value)) {
    return [];
  }

  const target = readString(value.target) ?? readString(value.table_id) ?? readString(value.data_label) ?? '-';
  const status = normalizeStatus(value.status);

  return [
    {
      id: readString(value.id) ?? `diagnostic-${index}`,
      status,
      label: readString(value.label) ?? 'diagnostic',
      target,
      message: readString(value.message) ?? target
    }
  ];
}

function buildDiagnostics(
  query: QueryRouteQuery,
  spaceRoutes: QueryRouteSpaceEntry[],
  dataLabelRoutes: QueryRouteDataLabelEntry[],
  details: QueryRouteResultTableDetail[]
): QueryRouteDiagnostic[] {
  const diagnostics: QueryRouteDiagnostic[] = [];
  const spaceTableIds = new Set(spaceRoutes.map((route) => route.table_id));
  const dataLabelTableIds = new Set(
    dataLabelRoutes.flatMap((route) => route.table_ids.map((table) => table.table_id))
  );
  const detailMap = buildDetailMap(details);
  const shouldCheckSpace = Boolean(query.spaceUid);
  const shouldCheckDataLabel = query.dataLabels.length > 0;
  const shouldCheckFields = query.fieldNames.length > 0;

  for (const tableId of query.tableIds) {
    if (shouldCheckSpace) {
      diagnostics.push(createDiagnostic('space-table', tableId, spaceTableIds.has(tableId), 'space 路由包含 table_id'));
    }
    if (shouldCheckDataLabel) {
      diagnostics.push(
        createDiagnostic('data-label-table', tableId, dataLabelTableIds.has(tableId), 'data_label 路由包含 table_id')
      );
    }
    diagnostics.push(
      createDiagnostic('detail-table', tableId, detailMap.get(tableId)?.exists === true, 'result_table_detail 存在')
    );
  }

  if (shouldCheckFields) {
    for (const detail of details) {
      for (const fieldName of detail.missing_field_names) {
        diagnostics.push({
          id: `field-${detail.table_id}-${fieldName}`,
          status: 'missing',
          label: '字段缺失',
          target: `${detail.table_id}.${fieldName}`,
          message: `${fieldName} 不存在于 result_table_detail.fields`
        });
      }
    }
  }

  if (shouldCheckSpace) {
    for (const route of dataLabelRoutes) {
      for (const table of route.table_ids) {
        diagnostics.push(
          createDiagnostic(
            'data-label-space',
            `${route.data_label}:${table.table_id}`,
            spaceTableIds.has(table.table_id),
            'data_label 对应 table_id 存在于 space 路由'
          )
        );
      }
    }
  }

  return diagnostics;
}

function createDiagnostic(
  prefix: string,
  target: string,
  ok: boolean,
  label: string
): QueryRouteDiagnostic {
  return {
    id: `${prefix}-${target}`,
    status: ok ? 'ok' : 'missing',
    label,
    target,
    message: ok ? `${target} OK` : `${target} Missing`
  };
}

function normalizeRefreshResult(payload: unknown, fromRefresh: boolean): QueryRouteRefreshResult | undefined {
  if (!fromRefresh) {
    return undefined;
  }

  const source = isRecord(payload) ? payload : {};
  const refreshResults = isRecord(source.refresh_results) ? source.refresh_results : {};
  return {
    refreshed: readBoolean(source.refreshed) ?? true,
    targets: readStringList(source.targets).concat(readRefreshTargets(refreshResults)),
    message:
      readString(source.message) ??
      '已刷新相关查询路由，后端会写 Redis 并 publish 通知 unify-query。',
    warnings: normalizeWarnings(Array.isArray(source.warnings) ? source.warnings : [])
  };
}

function normalizeRouteItems(value: unknown, keyName: string): Array<{ key: string; raw: unknown }> {
  if (Array.isArray(value)) {
    return value.flatMap((item) => {
      if (typeof item === 'string') {
        return [{ key: item, raw: { [keyName]: item } }];
      }
      if (isRecord(item)) {
        const key = readString(item[keyName]) ?? readString(item.table_id) ?? readString(item.data_label);
        return key ? [{ key, raw: item }] : [];
      }
      return [];
    });
  }

  if (isRecord(value)) {
    return Object.entries(value).map(([key, raw]) => {
      if (isRecord(raw) && !raw[keyName]) {
        return { key, raw: { ...raw, [keyName]: key } };
      }
      return { key, raw };
    });
  }

  return [];
}

function readRouteItems(value: unknown): unknown {
  if (isRecord(value) && Array.isArray(value.items)) {
    return value.items;
  }
  return value;
}

function sortByInputTableIds<T>(items: T[], inputTableIds: string[], getTableId: (item: T) => string): T[] {
  if (inputTableIds.length === 0) {
    return items;
  }
  const inputOrder = new Map(inputTableIds.map((tableId, index) => [tableId, index]));
  return [...items].sort((left, right) => {
    const leftOrder = inputOrder.get(getTableId(left)) ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = inputOrder.get(getTableId(right)) ?? Number.MAX_SAFE_INTEGER;
    return leftOrder - rightOrder;
  });
}

function buildDetailMap(details: QueryRouteResultTableDetail[]) {
  const detailMap = new Map<string, QueryRouteResultTableDetail>();
  for (const detail of details) {
    detailMap.set(detail.table_id, detail);
    if (detail.normalized_table_id) {
      detailMap.set(detail.normalized_table_id, detail);
    }
  }
  return detailMap;
}

function readRouteTableIds(value: unknown, nestedKey?: string): string[] {
  const source = nestedKey && isRecord(value) ? value[nestedKey] : value;
  if (Array.isArray(source)) {
    return source.flatMap((item) => {
      if (typeof item === 'string') {
        return [item];
      }
      if (isRecord(item)) {
        const tableId = readString(firstDefined(item.table_id, item.result_table_id));
        return tableId ? [tableId] : [];
      }
      return [];
    });
  }
  if (isRecord(source)) {
    return Object.keys(source);
  }
  return [];
}

function normalizeWarnings(warnings: unknown[]): string[] {
  return warnings.map((warning) => {
    if (typeof warning === 'string') {
      return warning;
    }
    if (isRecord(warning) && typeof warning.message === 'string') {
      return warning.message;
    }
    return String(warning);
  });
}

function normalizeStatus(value: unknown): QueryRouteDiagnostic['status'] {
  if (value === 'ok' || value === 'missing' || value === 'warning' || value === 'error') {
    return value;
  }
  if (value === true || value === 'success') {
    return 'ok';
  }
  if (value === false || value === 'fail') {
    return 'missing';
  }
  return 'warning';
}

function firstDefined(...values: unknown[]): unknown {
  return values.find((value) => value !== undefined && value !== null);
}

function readString(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined;
}

function readNestedString(value: unknown, key: string): string | undefined {
  return isRecord(value) ? readString(value[key]) : undefined;
}

function readStringOrNumber(value: unknown): string | number | undefined {
  if (typeof value === 'string' || typeof value === 'number') {
    return value;
  }
  return undefined;
}

function readStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => (typeof item === 'string' ? [item] : []));
}

function readRefreshTargets(value: Record<string, unknown>): string[] {
  return Object.values(value).flatMap((item) => {
    if (!isRecord(item)) {
      return [];
    }
    return readStringList(item.targets);
  });
}

function readBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function readNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
