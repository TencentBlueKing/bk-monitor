import { Link, useLocation, useNavigate, useParams } from '@tanstack/react-router';
import { ChevronLeft, ChevronRight, ExternalLink, Search } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import { Label } from '../../shared/components/ui/label';
import {
  buildHref,
  getStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { ES_STORAGE_TABLE_KIND_LABEL, ES_STORAGE_TABLE_KIND_TONE } from '../es-storage/constants';
import { useQueryRoute } from '../query-route/queries';
import type { QueryRouteResultTableDetail } from '../query-route/schemas';
import { useResultTableDetail, useResultTableFields } from './queries';
import { resultTableFieldListQuerySchema, type ResultTableField } from './schemas';

export function ResultTableDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const tableId = params.tableId ?? '';
  const [fieldName, setFieldName] = useState('');
  const [fieldTag, setFieldTag] = useState('');
  const [fieldPage, setFieldPage] = useState(1);
  const [selectedField, setSelectedField] = useState<ResultTableField | null>(null);

  const initialTenantRef = useRef(currentTenantId);
  useEffect(() => {
    if (currentTenantId !== initialTenantRef.current) {
      void navigate({
        to: '/result-tables',
        search: createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId)
      });
    }
  }, [currentTenantId, currentEnvironment?.id, navigate]);

  const detailQuery = useResultTableDetail(currentEnvironment!, currentTenantId, tableId);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const fallbackReturnHref = buildHref('/result-tables', routeSearch);
  const returnTarget = getStoredReturnTarget(currentHref, fallbackReturnHref, 'ResultTable 列表');
  const fieldQueryParams = resultTableFieldListQuerySchema.parse({
    bkTenantId: currentTenantId,
    tableId,
    fieldName: fieldName || undefined,
    tag: fieldTag || undefined,
    page: fieldPage,
    pageSize: 20
  });
  const fieldQuery = useResultTableFields(currentEnvironment!, fieldQueryParams);

  const dataLabels = useMemo(() => {
    const label = detailQuery.data?.result_table.data_label;
    if (!label) return [] as string[];
    return label
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }, [detailQuery.data?.result_table.data_label]);

  const routeQuery = useQueryRoute(
    currentEnvironment!,
    {
      bkTenantId: currentTenantId,
      tableIds: [tableId],
      dataLabels,
      fieldNames: []
    },
    Boolean(currentEnvironment && tableId)
  );

  if (!currentEnvironment || !tableId) {
    return <PageState title="ResultTable 参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载 ResultTable 详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const { result_table, options, datasources, custom_groups, es_storages, vm_record } =
    detailQuery.data;

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ResultTable Detail</div>
          <h2>{result_table.table_id}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>
      <Card>
        <CardContent className="detail-grid">
          <Info label="中文名" value={result_table.table_name_zh} />
          <Info label="租户" value={result_table.bk_tenant_id} />
          <Info label="业务" value={String(result_table.bk_biz_id)} />
          <Info label="schema" value={result_table.schema_type} />
          <Info label="默认存储" value={result_table.default_storage ?? '-'} />
          <Info label="label" value={result_table.label} />
          <Info label="data_label" value={result_table.data_label ?? '-'} />
          <Info label="启用" value={formatBoolean(result_table.is_enable)} />
          <Info label="删除" value={formatBoolean(result_table.is_deleted)} />
          <Info label="更新时间" value={formatDateTime(result_table.last_modify_time)} />
        </CardContent>
      </Card>
      <div className="section-stack">
        <section>
          <h3>Options</h3>
          <DataTable
            data={options}
            columns={[
              { header: 'name', accessorKey: 'name' },
              { header: 'value_type', accessorKey: 'value_type' },
              { header: 'creator', accessorKey: 'creator' },
              { header: 'value', cell: ({ row }) => <JsonBlock value={row.original.value} /> }
            ]}
          />
        </section>
        <section>
          <h3>字段</h3>
          <form
            className="inline-filter"
            onSubmit={(event) => {
              event.preventDefault();
              setFieldPage(1);
            }}
          >
            <div className="flex items-end gap-3">
              <div className="grid gap-1.5">
                <Label>field_name</Label>
                <Input value={fieldName} onChange={(event) => setFieldName(event.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="field-tag">tag</Label>
                <select
                  id="field-tag"
                  className="h-10 rounded-lg border border-border bg-card px-3 text-sm"
                  value={fieldTag}
                  onChange={(event) => {
                    setFieldTag(event.target.value);
                    setFieldPage(1);
                  }}
                >
                  <option value="">全部</option>
                  <option value="metric">metric</option>
                  <option value="dimension">dimension</option>
                </select>
              </div>
            </div>
            <Button type="submit">
              <Search aria-hidden="true" size={16} />
              过滤
            </Button>
          </form>
          {fieldQuery.isLoading ? (
            <PageState title="正在加载字段..." />
          ) : fieldQuery.isError ? (
            <PageState title="字段加载失败" description={String(fieldQuery.error)} />
          ) : (
            <>
              <DataTable
                data={fieldQuery.data?.items ?? []}
                columns={[
                  { header: 'field_name', accessorKey: 'field_name' },
                  { header: 'field_type', accessorKey: 'field_type' },
                  { header: 'tag', accessorKey: 'tag' },
                  { header: 'description', accessorKey: 'description' },
                  { header: 'unit', accessorKey: 'unit' },
                  {
                    header: '用户配置',
                    cell: ({ row }) => formatBoolean(row.original.is_config_by_user)
                  },
                  {
                    header: '禁用',
                    cell: ({ row }) => (
                      <Badge tone={row.original.is_disabled ? 'danger' : 'success'}>
                        {formatBoolean(row.original.is_disabled)}
                      </Badge>
                    )
                  },
                  {
                    header: 'options',
                    cell: ({ row }) => (
                      <FieldOptionsButton
                        field={row.original}
                        onClick={() => setSelectedField(row.original)}
                      />
                    )
                  }
                ]}
              />
              <Card>
                <CardContent className="pager">
                  <Button
                    variant="secondary"
                    disabled={fieldPage <= 1}
                    onClick={() => setFieldPage((value) => value - 1)}
                  >
                    <ChevronLeft aria-hidden="true" size={16} />
                    上一页
                  </Button>
                  <span>
                    第 {fieldPage} 页 / 共 {fieldQuery.data?.total ?? 0} 个字段
                  </span>
                  <Button
                    variant="secondary"
                    disabled={(fieldQuery.data?.items.length ?? 0) < fieldQueryParams.pageSize}
                    onClick={() => setFieldPage((value) => value + 1)}
                  >
                    下一页
                    <ChevronRight aria-hidden="true" size={16} />
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </section>
        <section>
          <h3>数据源</h3>
          <DataTable
            data={datasources}
            columns={[
              {
                header: 'bk_data_id',
                cell: ({ row }) => (
                  <Link
                    to="/datasources/$bkDataId"
                    params={{
                      bkDataId: String(row.original.bk_data_id)
                    }}
                    search={routeSearch}
                    onClick={() =>
                      rememberReturnTarget(
                        buildHref(`/datasources/${String(row.original.bk_data_id)}`, routeSearch),
                        {
                          href: currentHref,
                          label: 'ResultTable 详情'
                        }
                      )
                    }
                    className="link"
                  >
                    {row.original.bk_data_id}
                  </Link>
                )
              },
              { header: 'data_name', accessorKey: 'data_name' },
              { header: 'created_from', accessorKey: 'created_from' },
              { header: 'source_label', accessorKey: 'source_label' },
              { header: 'type_label', accessorKey: 'type_label' },
              { header: '启用', cell: ({ row }) => formatBoolean(row.original.is_enable) }
            ]}
          />
        </section>
        <section>
          <h3>自定义分组</h3>
          <JsonBlock value={custom_groups} />
        </section>
        <section className="two-column">
          <div>
            <h3>ESStorage</h3>
            <DataTable
              data={es_storages}
              emptyText="无 ESStorage"
              columns={[
                {
                  header: 'table_id',
                  cell: ({ row }) => (
                    <Link
                      to="/es-storages/$tableId"
                      params={{ tableId: row.original.table_id }}
                      search={routeSearch}
                      onClick={() =>
                        rememberReturnTarget(
                          buildHref(`/es-storages/${row.original.table_id}`, routeSearch),
                          {
                            href: currentHref,
                            label: 'ResultTable 详情'
                          }
                        )
                      }
                      className="link"
                    >
                      {row.original.table_id}
                    </Link>
                  )
                },
                {
                  header: 'table_kind',
                  cell: ({ row }) => {
                    const tableKind = row.original.table_kind ?? 'physical';
                    return (
                      <Badge tone={ES_STORAGE_TABLE_KIND_TONE[tableKind]}>
                        {ES_STORAGE_TABLE_KIND_LABEL[tableKind]}
                      </Badge>
                    );
                  }
                },
                {
                  header: 'origin_table_id',
                  cell: ({ row }) =>
                    row.original.origin_table_id ? (
                      <Link
                        to="/es-storages/$tableId"
                        params={{ tableId: row.original.origin_table_id }}
                        search={routeSearch}
                        onClick={() =>
                          rememberReturnTarget(
                            buildHref(`/es-storages/${row.original.origin_table_id}`, routeSearch),
                            {
                              href: currentHref,
                              label: 'ResultTable 详情'
                            }
                          )
                        }
                        className="link"
                      >
                        {row.original.origin_table_id}
                      </Link>
                    ) : (
                      <span className="muted-text">-</span>
                    )
                },
                { header: 'storage_cluster_id', accessorKey: 'storage_cluster_id' },
                { header: 'index_set', accessorKey: 'index_set' },
                {
                  header: 'need_create_index',
                  cell: ({ row }) => formatBoolean(row.original.need_create_index)
                }
              ]}
            />
          </div>
          <div>
            <h3>AccessVMRecord</h3>
            <JsonBlock value={vm_record ?? { message: '无 AccessVMRecord' }} />
          </div>
        </section>
        <QueryRouteSection
          tableId={tableId}
          queryRoute={routeQuery}
          currentHref={currentHref}
          routeSearch={routeSearch}
        />
      </div>
      {selectedField != null ? (
        <FieldOptionsDialog field={selectedField} onClose={() => setSelectedField(null)} />
      ) : null}
    </section>
  );
}

function FieldOptionsButton({ field, onClick }: { field: ResultTableField; onClick: () => void }) {
  const count = field.option_count;
  if (count === 0) {
    return <span className="muted-text">0</span>;
  }
  return (
    <button type="button" className="link text-sm" onClick={onClick}>
      {count}
    </button>
  );
}

function FieldOptionsDialog({ field, onClose }: { field: ResultTableField; onClose: () => void }) {
  const options = field.options ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <button
        type="button"
        className="fixed inset-0 bg-black/40"
        aria-label="关闭"
        onClick={onClose}
      />
      <Card className="relative z-10 max-h-[70vh] w-full max-w-md overflow-auto">
        <CardContent className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-xs text-muted-foreground">字段选项</div>
              <h3 className="text-base font-semibold">{field.field_name}</h3>
            </div>
            <Button variant="ghost" size="sm" onClick={onClose}>
              关闭
            </Button>
          </div>
          {options.length === 0 ? (
            <div className="muted-text rounded-lg border border-border p-4 text-sm">无选项</div>
          ) : (
            <DataTable
              data={options}
              columns={[
                { header: 'name', accessorKey: 'name' },
                { header: 'value_type', accessorKey: 'value_type' },
                {
                  header: 'value',
                  accessorKey: 'value',
                  cell: ({ row }) => {
                    const v = row.original.value;
                    if (v === null || v === undefined || v === '') return '-';
                    if (typeof v === 'object') return JSON.stringify(v);
                    if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
                      return String(v);
                    return '-';
                  }
                }
              ]}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function findDetail(
  details: QueryRouteResultTableDetail[],
  tableId: string
): QueryRouteResultTableDetail | null {
  return details.find((d) => d.table_id === tableId || d.normalized_table_id === tableId) ?? null;
}

function readDetailField(detail: QueryRouteResultTableDetail | null, key: string): string {
  if (!detail?.detail) return '-';
  const raw = detail.detail as Record<string, unknown>;
  const summary = isRecord(raw.summary) ? raw.summary[key] : undefined;
  const inner = isRecord(raw.detail) ? raw.detail[key] : undefined;
  const value = summary ?? inner;
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
    return String(value);
  return '-';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function QueryRouteSection({
  tableId,
  queryRoute,
  currentHref,
  routeSearch
}: {
  tableId: string;
  queryRoute: ReturnType<typeof useQueryRoute>;
  currentHref: string;
  routeSearch: Record<string, string>;
}) {
  if (queryRoute.isLoading) {
    return (
      <section>
        <h3>查询路由</h3>
        <PageState title="查询路由中..." />
      </section>
    );
  }

  if (queryRoute.isError) {
    return (
      <section>
        <h3>查询路由</h3>
        <PageState title="路由查询失败" description={String(queryRoute.error)} />
      </section>
    );
  }

  const response = queryRoute.data;
  if (!response) return null;

  const detail = findDetail(response.result_table_details, tableId);
  const spaceRoute = response.space_routes.find((r) => r.table_id === tableId);
  const dataLabelRoutes = response.data_label_routes.filter((r) =>
    r.table_ids.some((t) => t.table_id === tableId)
  );

  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <h3>查询路由</h3>
        <Link
          to="/query-route/$tableId"
          params={{ tableId }}
          search={routeSearch}
          className="link inline-flex items-center"
          title="查看完整路由详情"
          onClick={() =>
            rememberReturnTarget(buildHref(`/query-route/${tableId}`, routeSearch), {
              href: currentHref,
              label: 'ResultTable 详情'
            })
          }
        >
          <ExternalLink aria-hidden="true" size={14} />
        </Link>
      </div>
      <div className="section-stack mt-3">
        <Card>
          <CardContent className="detail-grid p-4 text-sm">
            <Info
              label="result_table_detail 存在"
              value={
                <Badge tone={detail?.exists ? 'success' : 'danger'}>
                  {detail?.exists ? 'OK' : 'Missing'}
                </Badge>
              }
            />
            <Info label="storage_type" value={detail?.storage_type ?? '-'} />
            <Info label="storage_id" value={String(detail?.storage_id ?? '-')} />
            <Info label="db" value={detail?.db ?? '-'} />
            <Info label="measurement" value={detail?.measurement ?? '-'} />
            <Info label="measurement_type" value={readDetailField(detail, 'measurement_type')} />
            <Info label="bcs_cluster_id" value={readDetailField(detail, 'bcs_cluster_id')} />
            <Info label="field_count" value={String(detail?.field_count ?? 0)} />
          </CardContent>
        </Card>

        {spaceRoute != null ? (
          <div>
            <h4 className="mb-2 text-sm font-medium">Space 路由</h4>
            <Card>
              <CardContent className="p-3 text-sm">
                <div className="grid gap-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">table_id:</span>
                    <Link
                      to="/query-route/$tableId"
                      params={{ tableId: spaceRoute.table_id }}
                      search={routeSearch}
                      className="link font-mono text-xs"
                      onClick={() =>
                        rememberReturnTarget(
                          buildHref(`/query-route/${spaceRoute.table_id}`, routeSearch),
                          { href: currentHref, label: 'ResultTable 详情' }
                        )
                      }
                    >
                      {spaceRoute.table_id} <ExternalLink aria-hidden="true" size={12} />
                    </Link>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">filters:</span>
                    {spaceRoute.filters.length > 0
                      ? spaceRoute.filters.map((group, gi) =>
                          group.conditions.map((cond, ci) => (
                            <Badge key={`${gi}-${ci}`} tone="muted">
                              {cond.field} {cond.operator} {String(cond.value)}
                            </Badge>
                          ))
                        )
                      : null}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {dataLabelRoutes.length > 0 ? (
          <div>
            <h4 className="mb-2 text-sm font-medium">DataLabel 路由 ({dataLabelRoutes.length})</h4>
            <DataTable
              data={dataLabelRoutes}
              columns={[
                {
                  header: 'data_label',
                  accessorKey: 'data_label'
                },
                {
                  header: 'exists',
                  cell: ({ row }) => (
                    <Badge tone={row.original.exists ? 'success' : 'danger'}>
                      {row.original.exists ? 'OK' : 'Missing'}
                    </Badge>
                  )
                },
                {
                  header: 'table exists',
                  cell: ({ row }) => {
                    const found = row.original.table_ids.some((t) => t.table_id === tableId);
                    return (
                      <Badge tone={found ? 'success' : 'danger'}>{found ? 'OK' : 'Missing'}</Badge>
                    );
                  }
                }
              ]}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
