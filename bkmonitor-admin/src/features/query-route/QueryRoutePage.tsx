import { useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useSearch } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { RefreshCcw, Search } from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import { Label } from '../../shared/components/ui/label';
import { Textarea } from '../../shared/components/ui/textarea';
import { buildHref, rememberReturnTarget } from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { queryRoutes } from './api';
import { useQueryRoute, useRefreshQueryRoute } from './queries';
import {
  queryRouteQuerySchema,
  type QueryRouteDataLabelEntry,
  type QueryRouteDiagnostic,
  type QueryRouteDiagnosticStatus,
  type QueryRouteField,
  type QueryRouteFilterGroup,
  type QueryRouteQuery,
  type QueryRouteResultTableDetail,
  type QueryRouteSpaceEntry
} from './schemas';

interface QueryRouteDraft {
  spaceUid: string;
  tableIdsText: string;
  dataLabelsText: string;
  fieldNamesText: string;
  keyword: string;
}

const EMPTY_QUERY = queryRouteQuerySchema.parse({
  tableIds: [],
  dataLabels: [],
  fieldNames: []
});

const STATUS_TONE: Record<QueryRouteDiagnosticStatus, 'default' | 'success' | 'danger' | 'warning' | 'muted'> = {
  ok: 'success',
  missing: 'danger',
  warning: 'warning',
  error: 'danger'
};

export function QueryRoutePage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const queryClient = useQueryClient();
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const search = useSearch({ strict: false });
  const initialDraft = useMemo(() => getInitialDraft(search), [search]);
  const [draft, setDraft] = useState<QueryRouteDraft>(initialDraft);
  const [activeQuery, setActiveQuery] = useState<QueryRouteQuery | null>(() =>
    hasDraftInput(initialDraft) ? buildQuery(initialDraft, currentTenantId) : null
  );
  const [spacePage, setSpacePage] = useState(1);
  const [dataLabelPage, setDataLabelPage] = useState(1);
  const [detailPage, setDetailPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [expandedTableId, setExpandedTableId] = useState<string | null>(null);
  const [fieldPage, setFieldPage] = useState(1);

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const queryRoute = useQueryRoute(currentEnvironment!, activeQuery ?? EMPTY_QUERY, Boolean(activeQuery));
  const refreshRoute = useRefreshQueryRoute(currentEnvironment!);
  const response = queryRoute.data ?? refreshRoute.data;
  const keyword = draft.keyword.trim().toLowerCase();

  const filteredSpaceRoutes = useMemo(
    () => filterItems(response?.space_routes ?? [], keyword),
    [keyword, response?.space_routes]
  );
  const filteredDataLabelRoutes = useMemo(
    () => filterItems(response?.data_label_routes ?? [], keyword),
    [keyword, response?.data_label_routes]
  );
  const filteredDetails = useMemo(
    () => filterItems(response?.result_table_details ?? [], keyword),
    [keyword, response?.result_table_details]
  );
  const filteredDiagnostics = useMemo(
    () => filterItems(response?.diagnostics ?? [], keyword),
    [keyword, response?.diagnostics]
  );
  const summary = useMemo(() => summarizeDiagnostics(response?.diagnostics ?? []), [response?.diagnostics]);
  const expandedDetail =
    response?.result_table_details.find((detail) => detail.table_id === expandedTableId) ?? null;
  const pagedFields = paginate(expandedDetail?.fields ?? [], fieldPage, pageSize);

  const spaceColumns = useMemo<Array<ColumnDef<QueryRouteSpaceEntry>>>(
    () => [
      {
        header: 'table_id',
        cell: ({ row }) => (
          <TableIdLink
            tableId={row.original.table_id}
            routeSearch={routeSearch}
            currentHref={currentHref}
          />
        )
      },
      {
        header: 'filters',
        cell: ({ row }) => <FilterGroups groups={row.original.filters} />
      },
      {
        header: '输入 table_ids',
        cell: ({ row }) => <BoolBadge value={row.original.in_input_table_ids} />
      },
      {
        header: '任一 data_label',
        cell: ({ row }) => <BoolBadge value={row.original.in_any_data_label} />
      },
      {
        header: 'detail',
        cell: ({ row }) => <BoolBadge value={row.original.has_detail} />
      }
    ],
    [currentHref, routeSearch]
  );

  const dataLabelColumns = useMemo<Array<ColumnDef<QueryRouteDataLabelEntry>>>(
    () => [
      { header: 'data_label', accessorKey: 'data_label' },
      {
        header: 'table_ids',
        cell: ({ row }) => (
          <div className="flex max-w-[720px] flex-wrap gap-1.5">
            {row.original.table_ids.map((table) => (
              <Badge key={`${row.original.data_label}-${table.table_id}`} tone="default">
                {table.table_id}
              </Badge>
            ))}
          </div>
        )
      },
      {
        header: 'space/detail',
        cell: ({ row }) => (
          <div className="grid gap-1 text-xs">
            {row.original.table_ids.slice(0, 6).map((table) => (
              <span key={table.table_id} className="flex items-center gap-1">
                <span className="font-mono">{table.table_id}</span>
                <Badge tone={table.in_space ? 'success' : 'danger'}>space</Badge>
                <Badge tone={table.has_detail ? 'success' : 'danger'}>detail</Badge>
              </span>
            ))}
            {row.original.table_ids.length > 6 ? (
              <span className="muted-text">还有 {row.original.table_ids.length - 6} 个</span>
            ) : null}
          </div>
        )
      }
    ],
    []
  );

  const detailColumns = useMemo<Array<ColumnDef<QueryRouteResultTableDetail>>>(
    () => [
      {
        header: 'table_id',
        cell: ({ row }) => (
          <button
            type="button"
            className="link text-left"
            onClick={() => {
              setExpandedTableId(row.original.table_id);
              setFieldPage(1);
            }}
          >
            {row.original.table_id}
          </button>
        )
      },
      {
        header: 'exists',
        cell: ({ row }) => <BoolBadge value={row.original.exists} />
      },
      { header: 'storage_type', accessorKey: 'storage_type' },
      { header: 'storage_id', accessorKey: 'storage_id' },
      { header: 'db', accessorKey: 'db' },
      { header: 'measurement', accessorKey: 'measurement' },
      { header: 'field_count', accessorKey: 'field_count' },
      {
        header: '命中 field_names',
        cell: ({ row }) => (
          <FieldNameSummary
            matched={row.original.matched_field_names}
            missing={row.original.missing_field_names}
          />
        )
      }
    ],
    []
  );

  const fieldColumns = useMemo<Array<ColumnDef<QueryRouteField>>>(
    () => [
      { header: 'field_name', accessorKey: 'field_name' },
      { header: 'field_type', accessorKey: 'field_type' },
      { header: 'tag', accessorKey: 'tag' },
      { header: 'alias_name', accessorKey: 'alias_name' },
      { header: 'description', accessorKey: 'description' }
    ],
    []
  );

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setActiveQuery(buildQuery(draft, currentTenantId));
    resetPages();
  }

  async function handleRefresh() {
    if (!currentEnvironment) {
      return;
    }

    const confirmed = window.confirm(
      '刷新相关路由会写 Redis 并 publish 通知 unify-query。确认刷新当前查询对象/相关路由并重新查询吗？'
    );
    if (!confirmed) {
      return;
    }

    const nextQuery = buildQuery(draft, currentTenantId);
    setActiveQuery(nextQuery);
    resetPages();
    await refreshRoute.mutateAsync(nextQuery);
    await queryClient.fetchQuery({
      queryKey: ['query-route', currentEnvironment.id, currentEnvironment, 'query', nextQuery],
      queryFn: () => queryRoutes(currentEnvironment, nextQuery)
    });
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Diagnostic Tool</div>
          <h2>查询路由</h2>
        </div>
      </div>

      <Card>
        <CardContent className="p-5">
          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 lg:grid-cols-4">
              <div className="grid gap-1.5">
                <Label htmlFor="space_uid">space_uid</Label>
                <Input
                  id="space_uid"
                  value={draft.spaceUid}
                  placeholder="bkcc__2"
                  onChange={(event) => setDraft((prev) => ({ ...prev, spaceUid: event.target.value }))}
                />
              </div>
              <MultiLineInput
                id="table_ids"
                label="table_ids"
                value={draft.tableIdsText}
                placeholder="2_bkmonitor_time_series.__default__"
                onChange={(value) => setDraft((prev) => ({ ...prev, tableIdsText: value }))}
              />
              <MultiLineInput
                id="data_labels"
                label="data_labels"
                value={draft.dataLabelsText}
                placeholder="custom_metric_demo"
                onChange={(value) => setDraft((prev) => ({ ...prev, dataLabelsText: value }))}
              />
              <MultiLineInput
                id="field_names"
                label="field_names"
                value={draft.fieldNamesText}
                placeholder="time, metric_2"
                onChange={(value) => setDraft((prev) => ({ ...prev, fieldNamesText: value }))}
              />
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <div className="grid min-w-[260px] flex-1 gap-1.5">
                <Label htmlFor="keyword">keyword</Label>
                <Input
                  id="keyword"
                  value={draft.keyword}
                  placeholder="本地过滤 table_id / data_label / 字段 / filters"
                  onChange={(event) => setDraft((prev) => ({ ...prev, keyword: event.target.value }))}
                />
              </div>
              <Button type="submit" disabled={queryRoute.isFetching}>
                <Search aria-hidden="true" size={16} />
                查询
              </Button>
              <Button
                type="button"
                variant="secondary"
                title="会写 Redis 并 publish 通知 unify-query"
                disabled={refreshRoute.isPending}
                onClick={() => void handleRefresh()}
              >
                <RefreshCcw aria-hidden="true" size={16} />
                刷新相关路由并重新查询
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {refreshRoute.data?.refresh ? (
        <Card>
          <CardContent className="p-4 text-sm">
            <strong>{refreshRoute.data.refresh.message}</strong>
            {refreshRoute.data.refresh.targets.length > 0 ? (
              <span className="ml-2 text-muted-foreground">
                targets: {refreshRoute.data.refresh.targets.join(', ')}
              </span>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {!activeQuery ? (
        <PageState title="请输入查询条件" description="支持同时输入 space_uid / table_ids / data_labels / field_names。" />
      ) : queryRoute.isError ? (
        <PageState title="查询失败" description={String(queryRoute.error)} />
      ) : queryRoute.isLoading ? (
        <PageState title="正在查询路由..." />
      ) : response ? (
        <div className="section-stack">
          <SummaryCards summary={summary} diagnostics={filteredDiagnostics} />

          <section id="space-routes">
            <SectionTitle title="Space 路由" count={filteredSpaceRoutes.length} />
            <DataTable data={paginate(filteredSpaceRoutes, spacePage, pageSize)} columns={spaceColumns} />
            <LocalPagination
              page={spacePage}
              pageSize={pageSize}
              total={filteredSpaceRoutes.length}
              onPageChange={setSpacePage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                resetPages();
              }}
            />
          </section>

          <section id="data-label-routes">
            <SectionTitle title="DataLabel 路由" count={filteredDataLabelRoutes.length} />
            <DataTable
              data={paginate(filteredDataLabelRoutes, dataLabelPage, pageSize)}
              columns={dataLabelColumns}
            />
            <LocalPagination
              page={dataLabelPage}
              pageSize={pageSize}
              total={filteredDataLabelRoutes.length}
              onPageChange={setDataLabelPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                resetPages();
              }}
            />
          </section>

          <section id="result-table-details">
            <SectionTitle title="ResultTable Detail" count={filteredDetails.length} />
            <DataTable data={paginate(filteredDetails, detailPage, pageSize)} columns={detailColumns} />
            <LocalPagination
              page={detailPage}
              pageSize={pageSize}
              total={filteredDetails.length}
              onPageChange={setDetailPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                resetPages();
              }}
            />
          </section>

          {expandedDetail ? (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h3>{expandedDetail.table_id} 详情</h3>
                <Button variant="secondary" onClick={() => setExpandedTableId(null)}>
                  收起
                </Button>
              </div>
              <div className="two-column">
                <div>
                  <h3>完整 detail</h3>
                  <JsonBlock value={expandedDetail.detail ?? { exists: false }} />
                </div>
                <div>
                  <h3>fields</h3>
                  <DataTable data={pagedFields} columns={fieldColumns} emptyText="无 fields" />
                  <LocalPagination
                    page={fieldPage}
                    pageSize={pageSize}
                    total={expandedDetail.fields.length}
                    onPageChange={setFieldPage}
                    onPageSizeChange={(size) => {
                      setPageSize(size);
                      setFieldPage(1);
                    }}
                  />
                </div>
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );

  function resetPages() {
    setSpacePage(1);
    setDataLabelPage(1);
    setDetailPage(1);
    setFieldPage(1);
  }
}

function MultiLineInput({
  id,
  label,
  value,
  placeholder,
  onChange
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        className="min-h-24 font-mono text-xs"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function SummaryCards({
  summary,
  diagnostics
}: {
  summary: { ok: number; missing: number; warning: number; error: number };
  diagnostics: QueryRouteDiagnostic[];
}) {
  const missingDiagnostics = diagnostics.filter((item) => item.status !== 'ok');

  return (
    <div className="grid gap-3 lg:grid-cols-4">
      <SummaryCard href="#space-routes" label="OK" value={summary.ok} tone="success" />
      <SummaryCard href="#result-table-details" label="Missing" value={summary.missing} tone="danger" />
      <SummaryCard href="#data-label-routes" label="Warning" value={summary.warning} tone="warning" />
      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground">诊断明细</div>
          <div className="mt-2 grid max-h-24 gap-1 overflow-auto text-xs">
            {missingDiagnostics.length > 0 ? (
              missingDiagnostics.slice(0, 8).map((item) => (
                <span key={item.id}>
                  <Badge tone={STATUS_TONE[item.status]}>{item.status}</Badge> {item.message}
                </span>
              ))
            ) : (
              <span className="muted-text">暂无异常诊断</span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SummaryCard({
  href,
  label,
  value,
  tone
}: {
  href: string;
  label: string;
  value: number;
  tone: 'success' | 'danger' | 'warning';
}) {
  return (
    <a href={href}>
      <Card>
        <CardContent className="p-4">
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-1 flex items-center gap-2">
            <span className="text-2xl font-semibold">{value}</span>
            <Badge tone={tone}>{label}</Badge>
          </div>
        </CardContent>
      </Card>
    </a>
  );
}

function SectionTitle({ title, count }: { title: string; count: number }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      <h3>{title}</h3>
      <Badge tone="muted">{count}</Badge>
    </div>
  );
}

function FilterGroups({ groups }: { groups: QueryRouteFilterGroup[] }) {
  if (groups.length === 0) {
    return <span className="muted-text">无 filters</span>;
  }

  return (
    <div className="grid max-w-[520px] gap-1.5">
      {groups.map((group, index) => (
        <div key={index} className="flex flex-wrap items-center gap-1">
          {index > 0 ? <span className="text-xs font-semibold text-muted-foreground">OR</span> : null}
          <span className="text-xs text-muted-foreground">AND</span>
          {group.conditions.length > 0 ? (
            group.conditions.map((condition) => (
              <Badge key={`${condition.field}-${condition.operator}-${String(condition.value)}`} tone="muted">
                {condition.field} {condition.operator} {formatValue(condition.value)}
              </Badge>
            ))
          ) : (
            <Badge tone="muted">空条件组</Badge>
          )}
        </div>
      ))}
    </div>
  );
}

function BoolBadge({ value }: { value: boolean }) {
  return <Badge tone={value ? 'success' : 'danger'}>{value ? 'OK' : 'Missing'}</Badge>;
}

function FieldNameSummary({ matched, missing }: { matched: string[]; missing: string[] }) {
  if (matched.length === 0 && missing.length === 0) {
    return <span className="muted-text">未输入 field_names</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {matched.map((fieldName) => (
        <Badge key={`matched-${fieldName}`} tone="success">
          {fieldName}
        </Badge>
      ))}
      {missing.map((fieldName) => (
        <Badge key={`missing-${fieldName}`} tone="danger">
          {fieldName}
        </Badge>
      ))}
    </div>
  );
}

function TableIdLink({
  tableId,
  routeSearch,
  currentHref
}: {
  tableId: string;
  routeSearch: { env: string; tenant: string };
  currentHref: string;
}) {
  return (
    <Link
      to="/result-tables/$tableId"
      params={{ tableId }}
      search={routeSearch}
      className="link"
      onClick={() =>
        rememberReturnTarget(buildHref(`/result-tables/${tableId}`, routeSearch), {
          href: currentHref,
          label: '查询路由'
        })
      }
    >
      {tableId}
    </Link>
  );
}

function LocalPagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  return (
    <Pagination
      page={page}
      pageSize={pageSize}
      total={total}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    />
  );
}

function buildQuery(draft: QueryRouteDraft, bkTenantId: string): QueryRouteQuery {
  return queryRouteQuerySchema.parse({
    bkTenantId,
    spaceUid: draft.spaceUid.trim() || undefined,
    tableIds: parseList(draft.tableIdsText),
    dataLabels: parseList(draft.dataLabelsText),
    fieldNames: parseList(draft.fieldNamesText),
    keyword: draft.keyword.trim() || undefined
  });
}

function getInitialDraft(search: object): QueryRouteDraft {
  return {
    spaceUid: getStringSearch(search, 'space_uid') ?? getStringSearch(search, 'spaceUid') ?? '',
    tableIdsText: getStringSearch(search, 'table_ids') ?? getStringSearch(search, 'tableIds') ?? '',
    dataLabelsText: getStringSearch(search, 'data_labels') ?? getStringSearch(search, 'dataLabels') ?? '',
    fieldNamesText: getStringSearch(search, 'field_names') ?? getStringSearch(search, 'fieldNames') ?? '',
    keyword: getStringSearch(search, 'keyword') ?? ''
  };
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

function hasDraftInput(draft: QueryRouteDraft): boolean {
  return Boolean(
    draft.spaceUid.trim() ||
      draft.tableIdsText.trim() ||
      draft.dataLabelsText.trim() ||
      draft.fieldNamesText.trim()
  );
}

function parseList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function filterItems<T>(items: T[], keyword: string): T[] {
  if (!keyword) {
    return items;
  }

  return items.filter((item) => JSON.stringify(item).toLowerCase().includes(keyword));
}

function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

function summarizeDiagnostics(items: QueryRouteDiagnostic[]) {
  return items.reduce(
    (acc, item) => {
      acc[item.status] += 1;
      return acc;
    },
    { ok: 0, missing: 0, warning: 0, error: 0 }
  );
}

function formatValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}
