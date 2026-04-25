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
}

interface RefreshTargets {
  space: boolean;
  table: boolean;
  dataLabel: boolean;
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
  const [refreshOpen, setRefreshOpen] = useState(false);
  const [refreshTargets, setRefreshTargets] = useState<RefreshTargets>({
    space: false,
    table: true,
    dataLabel: true
  });
  const [spaceKeyword, setSpaceKeyword] = useState('');
  const [dataLabelKeyword, setDataLabelKeyword] = useState('');
  const [detailKeyword, setDetailKeyword] = useState('');
  const [fieldKeyword, setFieldKeyword] = useState('');

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const queryRoute = useQueryRoute(currentEnvironment!, activeQuery ?? EMPTY_QUERY, Boolean(activeQuery));
  const refreshRoute = useRefreshQueryRoute(currentEnvironment!);
  const response = queryRoute.data ?? refreshRoute.data;

  const filteredSpaceRoutes = useMemo(
    () => filterItems(response?.space_routes ?? [], spaceKeyword.trim().toLowerCase()),
    [response?.space_routes, spaceKeyword]
  );
  const filteredDataLabelRoutes = useMemo(
    () => filterItems(response?.data_label_routes ?? [], dataLabelKeyword.trim().toLowerCase()),
    [dataLabelKeyword, response?.data_label_routes]
  );
  const filteredDetails = useMemo(
    () => filterItems(response?.result_table_details ?? [], detailKeyword.trim().toLowerCase()),
    [detailKeyword, response?.result_table_details]
  );
  const summary = useMemo(() => summarizeDiagnostics(response?.diagnostics ?? []), [response?.diagnostics]);
  const expandedDetail =
    response?.result_table_details.find((detail) => detail.table_id === expandedTableId) ?? null;
  const filteredFields = useMemo(
    () => filterItems(expandedDetail?.fields ?? [], fieldKeyword.trim().toLowerCase()),
    [expandedDetail?.fields, fieldKeyword]
  );
  const pagedFields = paginate(filteredFields, fieldPage, pageSize);

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

    const baseQuery = buildQuery(draft, currentTenantId);
    const nextQuery = buildRefreshQuery(baseQuery, refreshTargets);
    if (!hasRefreshTarget(nextQuery)) {
      window.alert('请先在刷新操作区选择刷新类型，并填写对应的 space_uid、table_ids 或 data_labels。');
      return;
    }

    const confirmed = window.confirm(
      '刷新相关路由会写 Redis 并 publish 通知 unify-query。确认刷新当前查询对象/相关路由并重新查询吗？'
    );
    if (!confirmed) {
      return;
    }

    setActiveQuery(nextQuery);
    resetPages();
    await refreshRoute.mutateAsync(nextQuery);
    const queryAfterRefresh = buildQuery(draft, currentTenantId);
    setActiveQuery(queryAfterRefresh);
    await queryClient.fetchQuery({
      queryKey: ['query-route', currentEnvironment.id, currentEnvironment, 'query', queryAfterRefresh],
      queryFn: () => queryRoutes(currentEnvironment, queryAfterRefresh)
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
              <Button type="submit" disabled={queryRoute.isFetching}>
                <Search aria-hidden="true" size={16} />
                查询
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="space-y-3 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3>路由刷新</h3>
            </div>
            <Button type="button" variant="secondary" onClick={() => setRefreshOpen((value) => !value)}>
              {refreshOpen ? '收起' : '展开'}
            </Button>
          </div>
          {refreshOpen ? (
            <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border p-3">
              <RefreshCheckbox
                label="刷新 Space 路由"
                description="使用 space_uid"
                checked={refreshTargets.space}
                onChange={(value) => setRefreshTargets((prev) => ({ ...prev, space: value }))}
              />
              <RefreshCheckbox
                label="刷新表详情路由"
                description="使用 table_ids"
                checked={refreshTargets.table}
                onChange={(value) => setRefreshTargets((prev) => ({ ...prev, table: value }))}
              />
              <RefreshCheckbox
                label="刷新 DataLabel 路由"
                description="使用 data_labels / table_ids"
                checked={refreshTargets.dataLabel}
                onChange={(value) => setRefreshTargets((prev) => ({ ...prev, dataLabel: value }))}
              />
              <Button
                type="button"
                variant="secondary"
                title="会写 Redis 并 publish 通知 unify-query"
                disabled={refreshRoute.isPending}
                onClick={() => void handleRefresh()}
              >
                <RefreshCcw aria-hidden="true" size={16} />
                执行刷新并重新查询
              </Button>
            </div>
          ) : null}
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
          <SummaryCards summary={summary} diagnostics={response.diagnostics} />

          <section id="space-routes">
            <SectionTitle
              title="Space 路由"
              count={filteredSpaceRoutes.length}
              keyword={spaceKeyword}
              placeholder="过滤 table_id / filters"
              onKeywordChange={(value) => {
                setSpaceKeyword(value);
                setSpacePage(1);
              }}
            />
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
            <SectionTitle
              title="DataLabel 路由"
              count={filteredDataLabelRoutes.length}
              keyword={dataLabelKeyword}
              placeholder="过滤 data_label / table_id"
              onKeywordChange={(value) => {
                setDataLabelKeyword(value);
                setDataLabelPage(1);
              }}
            />
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
            <SectionTitle
              title="ResultTable Detail"
              count={filteredDetails.length}
              keyword={detailKeyword}
              placeholder="过滤 table_id / storage / measurement"
              onKeywordChange={(value) => {
                setDetailKeyword(value);
                setDetailPage(1);
              }}
            />
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
                  <SectionTitle
                    title="fields"
                    count={filteredFields.length}
                    keyword={fieldKeyword}
                    placeholder="过滤 field_name / tag / type"
                    onKeywordChange={(value) => {
                      setFieldKeyword(value);
                      setFieldPage(1);
                    }}
                  />
                  <DataTable data={pagedFields} columns={fieldColumns} emptyText="无 fields" />
                  <LocalPagination
                    page={fieldPage}
                    pageSize={pageSize}
                    total={filteredFields.length}
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

function RefreshCheckbox({
  label,
  description,
  checked,
  onChange
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2 text-sm">
      <input
        type="checkbox"
        className="mt-1"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <span className="block font-medium">{label}</span>
        <span className="text-xs text-muted-foreground">{description}</span>
      </span>
    </label>
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

function SectionTitle({
  title,
  count,
  keyword,
  placeholder,
  onKeywordChange
}: {
  title: string;
  count: number;
  keyword?: string;
  placeholder?: string;
  onKeywordChange?: (value: string) => void;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <h3>{title}</h3>
        <Badge tone="muted">{count}</Badge>
      </div>
      {onKeywordChange ? (
        <Input
          className="max-w-xs"
          value={keyword ?? ''}
          placeholder={placeholder ?? '本区域过滤'}
          onChange={(event) => onKeywordChange(event.target.value)}
        />
      ) : null}
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
    fieldNames: parseList(draft.fieldNamesText)
  });
}

function getInitialDraft(search: object): QueryRouteDraft {
  return {
    spaceUid: getStringSearch(search, 'space_uid') ?? getStringSearch(search, 'spaceUid') ?? '',
    tableIdsText: getStringSearch(search, 'table_ids') ?? getStringSearch(search, 'tableIds') ?? '',
    dataLabelsText: getStringSearch(search, 'data_labels') ?? getStringSearch(search, 'dataLabels') ?? '',
    fieldNamesText: getStringSearch(search, 'field_names') ?? getStringSearch(search, 'fieldNames') ?? ''
  };
}

function buildRefreshQuery(query: QueryRouteQuery, targets: RefreshTargets): QueryRouteQuery {
  return queryRouteQuerySchema.parse({
    bkTenantId: query.bkTenantId,
    spaceUid: targets.space ? query.spaceUid : undefined,
    tableIds: targets.table || targets.dataLabel ? query.tableIds : [],
    dataLabels: targets.dataLabel ? query.dataLabels : [],
    fieldNames: [],
    refreshTargets: [
      ...(targets.space ? (['space'] as const) : []),
      ...(targets.table ? (['table'] as const) : []),
      ...(targets.dataLabel ? (['data_label'] as const) : [])
    ]
  });
}

function hasRefreshTarget(query: QueryRouteQuery): boolean {
  return Boolean(query.spaceUid || query.tableIds.length > 0 || query.dataLabels.length > 0);
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
