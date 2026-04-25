import { Link, useLocation, useParams, useSearch } from '@tanstack/react-router';
import { useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import {
  buildHref,
  getStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { createEnvironmentSearch } from '../environments/search';
import { useEnvironmentConfig } from '../environments/hooks';
import { useQueryRoute } from './queries';
import type { QueryRouteField, QueryRouteResultTableDetail } from './schemas';
import {
  QUERY_ROUTE_PAGE_SIZE,
  buildQueryRouteQuery,
  buildQueryRouteSearch,
  filterItems,
  getQueryRouteDraftFromSearch,
  paginate
} from './utils';

export function QueryRouteDetailPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const search = useSearch({ strict: false });
  const params = useParams({ strict: false }) as { tableId?: string };
  const tableId = params.tableId ?? '';
  const [fieldKeyword, setFieldKeyword] = useState('');
  const [fieldPage, setFieldPage] = useState(1);
  const [pageSize, setPageSize] = useState(QUERY_ROUTE_PAGE_SIZE);

  const envSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const draft = useMemo(() => getQueryRouteDraftFromSearch(search), [search]);
  const listQuery = useMemo(
    () => buildQueryRouteQuery(draft, currentTenantId),
    [currentTenantId, draft]
  );
  const detailQuery = useMemo(
    () =>
      buildQueryRouteQuery(
        {
          ...draft,
          tableIdsText: tableId
        },
        currentTenantId
      ),
    [currentTenantId, draft, tableId]
  );
  const backSearch = buildQueryRouteSearch(listQuery, envSearch);
  const queryRoute = useQueryRoute(
    currentEnvironment!,
    detailQuery,
    Boolean(currentEnvironment && tableId)
  );
  const detail = useMemo(
    () => findDetail(queryRoute.data?.result_table_details ?? [], tableId),
    [queryRoute.data?.result_table_details, tableId]
  );
  const filteredFields = useMemo(
    () => filterItems(detail?.fields ?? [], fieldKeyword.trim().toLowerCase()),
    [detail?.fields, fieldKeyword]
  );
  const pagedFields = paginate(filteredFields, fieldPage, pageSize);
  const routeDetail = useMemo(() => getInnerRouteDetail(detail?.detail), [detail?.detail]);
  const detailWithoutFields = useMemo(() => omitFieldsFromDetail(routeDetail), [routeDetail]);
  const returnTarget = getStoredReturnTarget(
    currentHref,
    buildHref('/query-route', backSearch),
    '查询路由'
  );

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  if (!tableId) {
    return <PageState title="缺少 table_id" />;
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ResultTable Detail Route</div>
          <h2>{tableId}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" asChild>
            <Link to="/query-route" search={backSearch}>
              返回查询路由
            </Link>
          </Button>
          <Button variant="secondary" asChild>
            <Link
              to="/result-tables/$tableId"
              params={{ tableId }}
              search={envSearch}
              onClick={() =>
                rememberReturnTarget(buildHref(`/result-tables/${tableId}`, envSearch), {
                  href: currentHref,
                  label: '路由详情'
                })
              }
            >
              查看 ResultTable
            </Link>
          </Button>
        </div>
      </div>

      {queryRoute.isError ? (
        <PageState title="查询失败" description={String(queryRoute.error)} />
      ) : queryRoute.isLoading ? (
        <PageState title="正在查询 result_table_detail 路由..." />
      ) : detail ? (
        <div className="section-stack">
          <Card>
            <CardContent className="grid gap-3 p-4 text-sm lg:grid-cols-4">
              <SummaryItem
                label="exists"
                value={detail.exists ? 'OK' : 'Missing'}
                tone={detail.exists ? 'success' : 'danger'}
              />
              <SummaryItem label="storage_type" value={detail.storage_type ?? '-'} />
              <SummaryItem label="storage_id" value={String(detail.storage_id ?? '-')} />
              <SummaryItem label="storage_name" value={readDetailText(detail, 'storage_name')} />
              <SummaryItem label="field_count" value={String(detail.field_count)} />
              <SummaryItem label="db" value={detail.db ?? '-'} />
              <SummaryItem label="measurement" value={detail.measurement ?? '-'} />
              <SummaryItem
                label="measurement_type"
                value={readDetailText(detail, 'measurement_type')}
              />
              <SummaryItem
                label="bcs_cluster_id"
                value={readDetailText(detail, 'bcs_cluster_id')}
              />
            </CardContent>
          </Card>

          <section>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <h3>fields</h3>
                <Badge tone="muted">{filteredFields.length}</Badge>
              </div>
              <Input
                className="max-w-xs"
                value={fieldKeyword}
                placeholder="过滤 field_name"
                onChange={(event) => {
                  setFieldKeyword(event.target.value);
                  setFieldPage(1);
                }}
              />
            </div>
            {pagedFields.length > 0 ? (
              <FieldNameGrid fields={pagedFields} />
            ) : (
              <div className="muted-text rounded-lg border border-border p-4 text-sm">
                无 fields
              </div>
            )}
            <Pagination
              page={fieldPage}
              pageSize={pageSize}
              total={filteredFields.length}
              onPageChange={setFieldPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setFieldPage(1);
              }}
            />
          </section>

          <section>
            <h3>完整 result_table_detail 路由</h3>
            <KeyValueTable value={detailWithoutFields ?? { exists: false }} />
          </section>
        </div>
      ) : (
        <PageState title="未找到 result_table_detail 路由" description={returnTarget.label} />
      )}
    </section>
  );
}

function SummaryItem({
  label,
  value,
  tone = 'muted'
}: {
  label: string;
  value: string;
  tone?: 'success' | 'danger' | 'muted';
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1">
        <Badge tone={tone}>{value}</Badge>
      </div>
    </div>
  );
}

function findDetail(details: QueryRouteResultTableDetail[], tableId: string) {
  return (
    details.find(
      (detail) => detail.table_id === tableId || detail.normalized_table_id === tableId
    ) ?? null
  );
}

function FieldNameGrid({ fields }: { fields: QueryRouteField[] }) {
  return (
    <div className="grid gap-2 rounded-lg border border-border p-3 md:grid-cols-2">
      {fields.map((field, index) => (
        <div
          key={`${field.field_name}-${index}`}
          className="truncate rounded-md bg-muted/40 px-2 py-1 font-mono text-xs"
          title={field.field_name}
        >
          {field.field_name}
        </div>
      ))}
    </div>
  );
}

function KeyValueTable({ value }: { value: unknown }) {
  if (!isRecord(value)) {
    return <div className="rounded-lg border border-border p-3 text-sm">{formatValue(value)}</div>;
  }

  const entries = Object.entries(value);
  if (entries.length === 0) {
    return <div className="muted-text rounded-lg border border-border p-4 text-sm">无数据</div>;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <tbody>
          {entries.map(([key, entryValue]) => (
            <tr key={key} className="border-b border-border last:border-b-0">
              <th className="w-56 bg-muted/40 px-3 py-2 align-top font-mono text-xs font-medium">
                {key}
              </th>
              <td className="px-3 py-2 align-top font-mono text-xs">{formatValue(entryValue)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function getInnerRouteDetail(value: unknown): unknown {
  if (!isRecord(value)) {
    return value;
  }
  return isRecord(value.detail) ? value.detail : value;
}

function omitFieldsFromDetail(value: unknown): unknown {
  if (!isRecord(value)) {
    return value;
  }

  const withoutTopLevelFields = omitFieldKey(value);
  if (isRecord(withoutTopLevelFields.detail)) {
    return {
      ...withoutTopLevelFields,
      detail: omitFieldKey(withoutTopLevelFields.detail)
    };
  }
  return withoutTopLevelFields;
}

function omitFieldKey(value: Record<string, unknown>) {
  const { fields: _fields, ...rest } = value;
  return rest;
}

function readDetailText(detail: QueryRouteResultTableDetail, key: string): string {
  const raw = detail.detail;
  const summaryValue = isRecord(raw) && isRecord(raw.summary) ? raw.summary[key] : undefined;
  const detailValue = isRecord(raw) && isRecord(raw.detail) ? raw.detail[key] : undefined;
  return formatValue(summaryValue ?? detailValue);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
