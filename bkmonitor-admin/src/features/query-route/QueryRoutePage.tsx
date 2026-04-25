import { useQueryClient } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { RefreshCcw, Search } from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';

import { Badge } from '../../shared/components/Badge';
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
import { queryRouteQueryKey, useQueryRoute, useRefreshQueryRoute } from './queries';
import {
  queryRouteQuerySchema,
  type QueryRouteDataLabelEntry,
  type QueryRouteFilterGroup,
  type QueryRouteQuery,
  type QueryRouteResultTableDetail,
  type QueryRouteSpaceEntry
} from './schemas';
import {
  QUERY_ROUTE_PAGE_SIZE,
  buildQueryRouteQuery,
  buildQueryRouteSearch,
  filterItems,
  getQueryRouteDraftFromSearch,
  hasQueryRouteDraftInput,
  paginate,
  type QueryRouteDraft
} from './utils';

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

const SPACE_ROUTE_PAGE_SIZE = 10;

export function QueryRoutePage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const search = useSearch({ strict: false });
  const initialDraft = useMemo(() => getQueryRouteDraftFromSearch(search), [search]);
  const [draft, setDraft] = useState<QueryRouteDraft>(initialDraft);
  const [activeQuery, setActiveQuery] = useState<QueryRouteQuery | null>(() =>
    hasQueryRouteDraftInput(initialDraft) ? buildQueryRouteQuery(initialDraft, currentTenantId) : null
  );
  const [spacePage, setSpacePage] = useState(1);
  const [dataLabelPage, setDataLabelPage] = useState(1);
  const [detailPage, setDetailPage] = useState(1);
  const [spacePageSize, setSpacePageSize] = useState(SPACE_ROUTE_PAGE_SIZE);
  const [pageSize, setPageSize] = useState(QUERY_ROUTE_PAGE_SIZE);
  const [refreshOpen, setRefreshOpen] = useState(false);
  const [refreshTargets, setRefreshTargets] = useState<RefreshTargets>({
    space: false,
    table: true,
    dataLabel: true
  });
  const [spaceKeyword, setSpaceKeyword] = useState('');
  const [dataLabelKeyword, setDataLabelKeyword] = useState('');
  const [detailKeyword, setDetailKeyword] = useState('');

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
  const routeSearch = buildQueryRouteSearch(
    activeQuery ?? buildQueryRouteQuery(draft, currentTenantId),
    createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId)
  );

  const spaceColumns = useMemo<Array<ColumnDef<QueryRouteSpaceEntry>>>(
    () => [
      {
        header: 'table_id',
        cell: ({ row }) => (
          <TableIdLink
            tableId={row.original.table_id}
            routeSearch={routeSearch}
            currentHref={currentHref}
            highlighted={row.original.in_input_table_ids}
          />
        )
      },
      {
        header: 'filters',
        cell: ({ row }) => <FilterGroups groups={row.original.filters} />
      }
    ],
    [currentHref, routeSearch]
  );

  const dataLabelColumns = useMemo<Array<ColumnDef<QueryRouteDataLabelEntry>>>(
    () => [
      { header: 'data_label', accessorKey: 'data_label' },
      {
        header: 'exists',
        cell: ({ row }) => <CheckBadge value={row.original.exists} checked />
      },
      {
        header: 'table_ids',
        cell: ({ row }) => (
          <div className="flex max-w-[720px] flex-wrap gap-1.5">
            {row.original.table_ids.map((table) => (
              <TableIdPill
                key={`${row.original.data_label}-${table.table_id}`}
                tableId={table.table_id}
                routeSearch={routeSearch}
                currentHref={currentHref}
                highlighted={table.in_input_table_ids}
              />
            ))}
          </div>
        )
      }
    ],
    [currentHref, routeSearch]
  );

  const detailColumns = useMemo<Array<ColumnDef<QueryRouteResultTableDetail>>>(
    () => [
      {
        header: 'table_id',
        cell: ({ row }) => (
          <TableIdLink
            tableId={row.original.table_id}
            routeSearch={routeSearch}
            currentHref={currentHref}
            highlighted={Boolean(activeQuery?.tableIds.includes(row.original.table_id))}
          />
        )
      },
      { header: 'storage_type', accessorKey: 'storage_type' },
      { header: 'storage_id', accessorKey: 'storage_id' },
      { header: 'db', accessorKey: 'db' },
      { header: 'measurement', accessorKey: 'measurement' },
      { header: 'field_count', accessorKey: 'field_count' }
    ],
    [activeQuery?.tableIds, currentHref, routeSearch]
  );

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextQuery = buildQueryRouteQuery(draft, currentTenantId);
    setActiveQuery(nextQuery);
    resetPages();
    void navigate({
      to: '/query-route',
      search: buildQueryRouteSearch(nextQuery, createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId))
    });
  }

  async function handleRefresh() {
    if (!currentEnvironment) {
      return;
    }

    const baseQuery = buildQueryRouteQuery(draft, currentTenantId);
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
    const queryAfterRefresh = buildQueryRouteQuery(draft, currentTenantId);
    setActiveQuery(queryAfterRefresh);
    await queryClient.fetchQuery({
      queryKey: queryRouteQueryKey(currentEnvironment, queryAfterRefresh),
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
          <DiagnosticPanel
            query={activeQuery}
            spaceRoutes={response.space_routes}
            dataLabelRoutes={response.data_label_routes}
            details={response.result_table_details}
            routeSearch={routeSearch}
            currentHref={currentHref}
          />

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
            <DataTable data={paginate(filteredSpaceRoutes, spacePage, spacePageSize)} columns={spaceColumns} />
            <LocalPagination
              page={spacePage}
              pageSize={spacePageSize}
              total={filteredSpaceRoutes.length}
              onPageChange={setSpacePage}
              onPageSizeChange={(size) => {
                setSpacePageSize(size);
                setSpacePage(1);
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

        </div>
      ) : null}
    </section>
  );

  function resetPages() {
    setSpacePage(1);
    setDataLabelPage(1);
    setDetailPage(1);
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

function DiagnosticPanel({
  query,
  spaceRoutes,
  dataLabelRoutes,
  details,
  routeSearch,
  currentHref
}: {
  query: QueryRouteQuery;
  spaceRoutes: QueryRouteSpaceEntry[];
  dataLabelRoutes: QueryRouteDataLabelEntry[];
  details: QueryRouteResultTableDetail[];
  routeSearch: Record<string, string>;
  currentHref: string;
}) {
  const spaceTableIds = new Set(spaceRoutes.map((route) => route.table_id));
  const dataLabelTableIds = new Set(
    dataLabelRoutes.flatMap((route) => route.table_ids.map((table) => table.table_id))
  );
  const detailMap = new Map(details.map((detail) => [detail.table_id, detail]));

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3>诊断明细</h3>
            <p className="text-sm text-muted-foreground">
              聚焦输入表在 Space / DataLabel / result_table_detail 中的存在关系，以及字段是否存在。
            </p>
          </div>
        </div>

        {query.tableIds.length > 0 ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40">
                <tr>
                  <th className="px-3 py-2">table_id</th>
                  <th className="px-3 py-2">Space</th>
                  <th className="px-3 py-2">DataLabel</th>
                  <th className="px-3 py-2">TableDetail</th>
                  <th className="px-3 py-2">field_names</th>
                </tr>
              </thead>
              <tbody>
                {query.tableIds.map((tableId) => {
                  const detail = detailMap.get(tableId);
                  return (
                    <tr key={tableId} className="border-t border-border">
                      <td className="px-3 py-2">
                        <TableIdLink
                          tableId={tableId}
                          routeSearch={routeSearch}
                          currentHref={currentHref}
                          highlighted
                        />
                      </td>
                      <td className="px-3 py-2">
                        <CheckBadge value={spaceTableIds.has(tableId)} checked={Boolean(query.spaceUid)} uncheckedText="未查询" />
                      </td>
                      <td className="px-3 py-2">
                        <CheckBadge
                          value={dataLabelTableIds.has(tableId)}
                          checked={query.dataLabels.length > 0}
                          uncheckedText="未查询"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <CheckBadge value={detail?.exists === true} checked />
                      </td>
                      <td className="px-3 py-2">
                        <FieldDiagnostics detail={detail} fieldNames={query.fieldNames} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="muted-text rounded-lg border border-border p-3 text-sm">
            未输入 table_ids，跳过表维度诊断。
          </div>
        )}

        {query.dataLabels.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {query.dataLabels.map((dataLabel) => {
              const route = dataLabelRoutes.find((item) => item.data_label === dataLabel);
              return (
                <span key={dataLabel} className="inline-flex items-center gap-2 rounded-md border border-border px-2 py-1 text-sm">
                  <span className="font-mono">{dataLabel}</span>
                  <CheckBadge value={route?.exists === true} checked />
                  {route ? <Badge tone="muted">{route.table_ids.length} tables</Badge> : null}
                </span>
              );
            })}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function FieldDiagnostics({
  detail,
  fieldNames
}: {
  detail: QueryRouteResultTableDetail | undefined;
  fieldNames: string[];
}) {
  if (fieldNames.length === 0) {
    return <Badge tone="muted">未输入</Badge>;
  }
  if (!detail?.exists) {
    return <Badge tone="muted">未查询到 detail</Badge>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {fieldNames.map((fieldName) => {
        const matched = detail.matched_field_names.includes(fieldName);
        return (
          <Badge key={fieldName} tone={matched ? 'success' : 'danger'}>
            {fieldName}
          </Badge>
        );
      })}
    </div>
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

function CheckBadge({
  value,
  checked,
  uncheckedText = '未检查'
}: {
  value: boolean;
  checked: boolean;
  uncheckedText?: string;
}) {
  if (!checked) {
    return <Badge tone="muted">{uncheckedText}</Badge>;
  }
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
  currentHref,
  highlighted = false
}: {
  tableId: string;
  routeSearch: Record<string, string>;
  currentHref: string;
  highlighted?: boolean;
}) {
  const targetHref = buildHref(`/query-route/${tableId}`, routeSearch);

  return (
    <Link
      to="/query-route/$tableId"
      params={{ tableId }}
      search={routeSearch}
      className={highlighted ? 'link rounded bg-warning/10 px-1 font-semibold' : 'link'}
      onClick={() =>
        rememberReturnTarget(targetHref, {
          href: currentHref,
          label: '查询路由'
        })
      }
    >
      {tableId}
    </Link>
  );
}

function TableIdPill({
  tableId,
  routeSearch,
  currentHref,
  highlighted = false
}: {
  tableId: string;
  routeSearch: Record<string, string>;
  currentHref: string;
  highlighted?: boolean;
}) {
  return (
    <Link
      to="/query-route/$tableId"
      params={{ tableId }}
      search={routeSearch}
      className={
        highlighted
          ? 'inline-flex items-center rounded-full border border-warning bg-warning/10 px-2 py-0.5 font-mono text-xs font-semibold hover:bg-warning/20'
          : 'inline-flex items-center rounded-full border border-border px-2 py-0.5 font-mono text-xs hover:bg-muted'
      }
      onClick={() =>
        rememberReturnTarget(buildHref(`/query-route/${tableId}`, routeSearch), {
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

function formatValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}
