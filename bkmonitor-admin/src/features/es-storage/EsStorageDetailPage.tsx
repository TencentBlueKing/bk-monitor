import { Link, useLocation, useNavigate, useParams } from '@tanstack/react-router';
import { Loader2 } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import {
  buildHref,
  getStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { ES_STORAGE_TABLE_KIND_LABEL, ES_STORAGE_TABLE_KIND_TONE } from './constants';
import { useEsRuntimeOverview, useEsStorageDetail, useEsStorageSample } from './queries';
import type { EsRuntimeIndex, EsRuntimeOverviewResponse, EsSampleResponse } from './schemas';

export function EsStorageDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const tableId = params.tableId ?? '';
  const [runtimeOverview, setRuntimeOverview] = useState<EsRuntimeOverviewResponse | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [sampleByIndex, setSampleByIndex] = useState<Record<string, EsSampleResponse>>({});
  const [sampleErrors, setSampleErrors] = useState<Record<string, string>>({});

  const initialTenantRef = useRef(currentTenantId);
  useEffect(() => {
    if (currentTenantId !== initialTenantRef.current) {
      void navigate({
        to: '/es-storages',
        search: createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId)
      });
    }
  }, [currentTenantId, currentEnvironment?.id, navigate]);

  const detailQuery = useEsStorageDetail(currentEnvironment!, currentTenantId, tableId);
  const runtimeMutation = useEsRuntimeOverview(currentEnvironment!);
  const sampleMutation = useEsStorageSample(currentEnvironment!);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const fallbackReturnHref = buildHref('/es-storages', routeSearch);
  const returnTarget = getStoredReturnTarget(currentHref, fallbackReturnHref, 'ESStorage 列表');

  if (!currentEnvironment || !tableId) {
    return <PageState title="ESStorage 参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载 ESStorage 详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const {
    es_storage,
    result_table,
    storage_cluster,
    storage_cluster_records,
    result_table_options,
    field_aliases,
    physical_table,
    virtual_tables,
    warnings
  } = detailQuery.data;
  const isVirtual = es_storage.table_kind === 'virtual';

  function loadRuntimeOverview() {
    setRuntimeError(null);
    runtimeMutation.mutate(
      { bkTenantId: currentTenantId, tableId },
      {
        onSuccess: (data) => setRuntimeOverview(data),
        onError: (error) => setRuntimeError(String(error))
      }
    );
  }

  function loadSample(index: string) {
    setSampleErrors((prev) => ({ ...prev, [index]: '' }));
    sampleMutation.mutate(
      { bkTenantId: currentTenantId, tableId, index, timeField: 'dtEventTimeStamp' },
      {
        onSuccess: (data) => setSampleByIndex((prev) => ({ ...prev, [index]: data })),
        onError: (error) => setSampleErrors((prev) => ({ ...prev, [index]: String(error) }))
      }
    );
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ESStorage Detail</div>
          <h2>{es_storage.table_id}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>

      {isVirtual ? (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="py-3 text-sm text-yellow-900">
            该 ESStorage 是虚拟表，运行时 ES 信息按自身 index_set 与时间分片规则查询；
            origin_table_id 仅表示实体表关联关系。
          </CardContent>
        </Card>
      ) : null}

      {warnings && warnings.length > 0 ? (
        <Card className="border-yellow-200">
          <CardContent className="py-3 text-sm text-yellow-900">
            {warnings.map((warning) => (
              <div key={warning}>{warning}</div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="detail-grid">
          <Info label="table_id" value={es_storage.table_id} />
          <Info
            label="表类型"
            value={
              <Badge tone={ES_STORAGE_TABLE_KIND_TONE[es_storage.table_kind]}>
                {ES_STORAGE_TABLE_KIND_LABEL[es_storage.table_kind]}
              </Badge>
            }
            raw
          />
          <Info
            label="origin_table_id"
            value={
              es_storage.origin_table_id ? (
                <StorageLink
                  tableId={es_storage.origin_table_id}
                  routeSearch={routeSearch}
                  currentHref={currentHref}
                />
              ) : (
                '-'
              )
            }
            raw
          />
          <Info
            label="ResultTable"
            value={
              result_table ? (
                <Link
                  to="/result-tables/$tableId"
                  params={{ tableId: result_table.table_id }}
                  search={routeSearch}
                  className="link"
                  onClick={() =>
                    rememberReturnTarget(
                      buildHref(`/result-tables/${result_table.table_id}`, routeSearch),
                      {
                        href: currentHref,
                        label: 'ESStorage 详情'
                      }
                    )
                  }
                >
                  {result_table.table_name_zh || result_table.table_id}
                </Link>
              ) : (
                '-'
              )
            }
            raw
          />
          <Info
            label="ClusterInfo"
            value={
              es_storage.storage_cluster_id ? (
                <ClusterLink
                  clusterId={es_storage.storage_cluster_id}
                  clusterName={storage_cluster?.display_name || storage_cluster?.cluster_name}
                  routeSearch={routeSearch}
                  currentHref={currentHref}
                />
              ) : (
                '-'
              )
            }
            raw
          />
          <Info label="更新时间" value={formatDateTime(es_storage.last_modify_time)} />
        </CardContent>
      </Card>

      <div className="section-stack">
        <section>
          <h3>存储配置</h3>
          <Card>
            <CardContent className="detail-grid">
              <Info label="retention" value={formatOptional(es_storage.retention, '天')} />
              <Info label="slice_size" value={formatOptional(es_storage.slice_size)} />
              <Info label="slice_gap" value={formatOptional(es_storage.slice_gap)} />
              <Info label="date_format" value={es_storage.date_format ?? '-'} />
              <Info label="time_zone" value={es_storage.time_zone ?? '-'} />
              <Info label="source_type" value={es_storage.source_type ?? '-'} />
              <Info label="index_set" value={es_storage.index_set ?? '-'} />
              <Info label="need_create_index" value={formatBoolean(es_storage.need_create_index)} />
              <Info
                label="warm_phase_days"
                value={formatOptional(es_storage.warm_phase_days, '天')}
              />
              <Info
                label="archive_index_days"
                value={formatOptional(es_storage.archive_index_days, '天')}
              />
            </CardContent>
          </Card>
        </section>

        <section>
          <h3>实体/虚拟关系</h3>
          {isVirtual ? (
            <Card>
              <CardContent className="py-3 text-sm">
                关联实体表:{' '}
                {physical_table?.table_id ? (
                  <StorageLink
                    tableId={physical_table.table_id}
                    routeSearch={routeSearch}
                    currentHref={currentHref}
                  />
                ) : (
                  <span className="muted-text">未返回实体表</span>
                )}
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="text-sm text-muted-foreground">
                当前实体表关联 {virtual_tables.length} 个虚拟表。
                <Link
                  to="/es-storages"
                  search={{ ...routeSearch, tableId: es_storage.table_id, tableKind: 'virtual' }}
                  className="ml-2 link"
                  onClick={() =>
                    rememberReturnTarget(
                      buildHref('/es-storages', {
                        ...routeSearch,
                        tableId: es_storage.table_id,
                        tableKind: 'virtual'
                      }),
                      { href: currentHref, label: 'ESStorage 详情' }
                    )
                  }
                >
                  查看列表
                </Link>
              </div>
              <DataTable
                data={virtual_tables}
                columns={[
                  {
                    header: 'table_id',
                    cell: ({ row }) => (
                      <StorageLink
                        tableId={row.original.table_id}
                        routeSearch={routeSearch}
                        currentHref={currentHref}
                      />
                    )
                  },
                  {
                    header: 'ResultTable',
                    cell: ({ row }) =>
                      row.original.result_table?.table_name_zh ||
                      row.original.result_table?.table_id ||
                      '-'
                  }
                ]}
              />
            </>
          )}
        </section>

        <section>
          <h3>集群迁移历史</h3>
          <DataTable
            data={storage_cluster_records}
            columns={[
              { header: 'table_id', accessorKey: 'table_id' },
              {
                header: 'cluster_id',
                cell: ({ row }) =>
                  row.original.cluster_id ? (
                    <ClusterLink
                      clusterId={row.original.cluster_id}
                      clusterName={
                        row.original.cluster?.display_name || row.original.cluster?.cluster_name
                      }
                      routeSearch={routeSearch}
                      currentHref={currentHref}
                    />
                  ) : (
                    '-'
                  )
              },
              {
                header: '当前',
                cell: ({ row }) => (
                  <Badge tone={row.original.is_current ? 'success' : 'muted'}>
                    {row.original.is_current ? '当前写入' : '历史'}
                  </Badge>
                )
              },
              {
                header: 'enable_time',
                cell: ({ row }) => formatDateTime(row.original.enable_time)
              },
              {
                header: 'disable_time',
                cell: ({ row }) => formatDateTime(row.original.disable_time)
              },
              {
                header: 'delete_time',
                cell: ({ row }) => formatDateTime(row.original.delete_time)
              },
              { header: 'creator', accessorKey: 'creator' }
            ]}
          />
        </section>

        <section>
          <h3>字段查询别名</h3>
          <p className="muted-text">
            ESFieldQueryAliasOption 会影响 query_alias 到 field_path 的解释，并可对应 mapping
            alias。
          </p>
          <DataTable
            data={field_aliases}
            columns={[
              { header: 'query_alias', accessorKey: 'query_alias' },
              { header: 'field_path', accessorKey: 'field_path' },
              { header: 'path_type', accessorKey: 'path_type' },
              {
                header: 'mapping_alias',
                cell: ({ row }) => <JsonBlock value={row.original.mapping_alias ?? {}} />
              }
            ]}
          />
        </section>

        <section>
          <h3>ResultTable Options</h3>
          <DataTable
            data={result_table_options}
            columns={[
              { header: 'name', accessorKey: 'name' },
              { header: 'value_type', accessorKey: 'value_type' },
              { header: 'value', cell: ({ row }) => <JsonBlock value={row.original.value} /> }
            ]}
          />
        </section>

        <section>
          <h3>配置 JSON</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <ConfigJson title="index_settings" value={es_storage.index_settings} />
            <ConfigJson title="mapping_settings" value={es_storage.mapping_settings} />
            <ConfigJson title="warm_phase_settings" value={es_storage.warm_phase_settings} />
            <ConfigJson
              title="long_term_storage_settings"
              value={es_storage.long_term_storage_settings}
            />
          </div>
        </section>

        <section>
          <div className="flex flex-wrap items-center gap-3">
            <h3>ES 实时信息</h3>
            <Button
              type="button"
              variant="secondary"
              disabled={runtimeMutation.isPending}
              onClick={loadRuntimeOverview}
            >
              {runtimeMutation.isPending ? (
                <Loader2 aria-hidden="true" size={16} className="animate-spin" />
              ) : null}
              加载 ES 实时信息
            </Button>
            <span className="text-sm text-muted-foreground">会访问目标 ES 集群</span>
          </div>
          {runtimeError ? (
            <Card className="border-destructive/50">
              <CardContent className="py-3 text-sm text-destructive">{runtimeError}</CardContent>
            </Card>
          ) : null}
          {runtimeOverview ? (
            <RuntimeOverview
              overview={runtimeOverview}
              sampleByIndex={sampleByIndex}
              sampleErrors={sampleErrors}
              samplePending={sampleMutation.isPending}
              needCreateIndex={es_storage.need_create_index}
              tableId={es_storage.table_id}
              onLoadSample={loadSample}
            />
          ) : (
            <PageState
              title="尚未加载实时信息"
              description="点击按钮后读取索引、mapping 与别名。"
            />
          )}
        </section>
      </div>
    </section>
  );
}

function RuntimeOverview({
  overview,
  sampleByIndex,
  sampleErrors,
  samplePending,
  needCreateIndex,
  tableId,
  onLoadSample
}: {
  overview: EsRuntimeOverviewResponse;
  sampleByIndex: Record<string, EsSampleResponse>;
  sampleErrors: Record<string, string>;
  samplePending: boolean;
  needCreateIndex: boolean | null | undefined;
  tableId: string;
  onLoadSample: (index: string) => void;
}) {
  return (
    <div className="section-stack">
      {overview.warnings.length > 0 ? (
        <Card className="border-yellow-200">
          <CardContent className="py-3 text-sm text-yellow-900">
            {overview.warnings.map((warning) => (
              <div key={warning}>{warning}</div>
            ))}
          </CardContent>
        </Card>
      ) : null}
      <Card>
        <CardContent className="detail-grid">
          <Info label="index_set" value={overview.index_set ?? '-'} />
          <Info label="index_pattern" value={overview.index_pattern ?? '-'} />
        </CardContent>
      </Card>
      <section>
        <h3>索引列表</h3>
        <DataTable
          data={overview.indices}
          columns={[
            { header: 'index', accessorKey: 'index' },
            { header: 'health', accessorKey: 'health' },
            { header: 'status', accessorKey: 'status' },
            { header: 'docs_count', accessorKey: 'docs_count' },
            {
              header: 'store_size',
              cell: ({ row }) => <StoreSize value={row.original.store_size} />
            },
            { header: 'creation_date', accessorKey: 'creation_date' },
            {
              header: '操作',
              cell: ({ row }) => (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={samplePending}
                  onClick={() => onLoadSample(row.original.index)}
                >
                  查询最新数据
                </Button>
              )
            }
          ]}
        />
        {overview.indices.map((index) => (
          <SampleResult
            key={index.index}
            index={index}
            sample={sampleByIndex[index.index]}
            error={sampleErrors[index.index]}
          />
        ))}
      </section>
      <AliasOverview raw={overview.aliases} needCreateIndex={needCreateIndex} tableId={tableId} />
      <section>
        <h3>Mapping</h3>
        <JsonBlock value={overview.mapping ?? { message: '无 mapping' }} />
      </section>
    </div>
  );
}

function SampleResult({
  index,
  sample,
  error
}: {
  index: EsRuntimeIndex;
  sample?: EsSampleResponse | undefined;
  error?: string | undefined;
}) {
  if (!sample && !error) {
    return null;
  }

  return (
    <Card className={error ? 'border-destructive/50' : undefined}>
      <CardContent className="space-y-3 py-3">
        <h4 className="text-sm font-semibold">{index.index} 最新数据</h4>
        {error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : (
          <JsonBlock value={sample} />
        )}
      </CardContent>
    </Card>
  );
}

function AliasOverview({
  raw,
  needCreateIndex,
  tableId
}: {
  raw: unknown;
  needCreateIndex: boolean | null | undefined;
  tableId: string;
}) {
  const todayStr = useMemo(() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    return `${y}${m}${d}`;
  }, []);

  const aliasRows = useMemo(() => {
    if (!raw || typeof raw !== 'object') return [];
    const rows: Array<{ index: string; readAliases: string[]; writeAliases: string[] }> = [];
    for (const [index, value] of Object.entries(raw as Record<string, unknown>)) {
      const aliasesObj = (value as Record<string, unknown>)?.aliases;
      if (!aliasesObj || typeof aliasesObj !== 'object') continue;
      const write: string[] = [];
      const read: string[] = [];
      for (const alias of Object.keys(aliasesObj)) {
        if (alias.startsWith('write_')) {
          write.push(alias);
        } else if (alias.endsWith('_read')) {
          read.push(alias);
        }
      }
      if (write.length > 0 || read.length > 0) {
        rows.push({ index, readAliases: read, writeAliases: write });
      }
    }
    return rows;
  }, [raw]);

  const tableIdUnder = tableId.replace(/\./g, '_');
  const expectedWrite = `write_${todayStr}_${tableIdUnder}`;
  const expectedRead = `${tableIdUnder}_${todayStr}_read`;

  const allAliases = useMemo(
    () => new Set(aliasRows.flatMap((r) => [...r.readAliases, ...r.writeAliases])),
    [aliasRows]
  );
  const writeOk = allAliases.has(expectedWrite);
  const readOk = allAliases.has(expectedRead);

  return (
    <section>
      <h3>别名</h3>
      {needCreateIndex ? (
        <Card className={writeOk && readOk ? 'border-green-300' : 'border-destructive/50'}>
          <CardContent className="py-3 space-y-2 text-sm">
            <p className="font-medium">检查日期: {todayStr}</p>
            <div>
              <span className={writeOk ? 'text-green-600' : 'text-destructive'}>
                {writeOk ? '✓' : '✗'}
              </span>{' '}
              写别名 <code className="text-xs bg-muted px-1 rounded">{expectedWrite}</code>
            </div>
            <div>
              <span className={readOk ? 'text-green-600' : 'text-destructive'}>
                {readOk ? '✓' : '✗'}
              </span>{' '}
              读别名 <code className="text-xs bg-muted px-1 rounded">{expectedRead}</code>
            </div>
          </CardContent>
        </Card>
      ) : null}
      <DataTable
        data={aliasRows}
        columns={[
          { header: '索引', accessorKey: 'index' },
          {
            header: '读别名',
            cell: ({ row }) => (
              <div className="space-y-0.5 text-sm">
                {row.original.readAliases.length === 0
                  ? '-'
                  : row.original.readAliases.map((a) => <div key={a}>{a}</div>)}
              </div>
            )
          },
          {
            header: '写别名',
            cell: ({ row }) => (
              <div className="space-y-0.5 text-sm">
                {row.original.writeAliases.length === 0
                  ? '-'
                  : row.original.writeAliases.map((a) => <div key={a}>{a}</div>)}
              </div>
            )
          }
        ]}
      />
    </section>
  );
}

function ConfigJson({ title, value }: { title: string; value: unknown }) {
  return (
    <Card>
      <CardContent className="space-y-3 py-3">
        <h4 className="text-sm font-semibold">{title}</h4>
        <JsonBlock value={value ?? {}} />
      </CardContent>
    </Card>
  );
}

function StorageLink({
  tableId,
  routeSearch,
  currentHref
}: {
  tableId: string;
  routeSearch: ReturnType<typeof createEnvironmentSearch>;
  currentHref: string;
}) {
  return (
    <Link
      to="/es-storages/$tableId"
      params={{ tableId }}
      search={routeSearch}
      className="link"
      onClick={() =>
        rememberReturnTarget(buildHref(`/es-storages/${tableId}`, routeSearch), {
          href: currentHref,
          label: 'ESStorage 详情'
        })
      }
    >
      {tableId}
    </Link>
  );
}

function ClusterLink({
  clusterId,
  clusterName,
  routeSearch,
  currentHref
}: {
  clusterId: number;
  clusterName?: string | null | undefined;
  routeSearch: ReturnType<typeof createEnvironmentSearch>;
  currentHref: string;
}) {
  return (
    <Link
      to="/clusters/$clusterId"
      params={{ clusterId: String(clusterId) }}
      search={routeSearch}
      className="link"
      onClick={() =>
        rememberReturnTarget(buildHref(`/clusters/${String(clusterId)}`, routeSearch), {
          href: currentHref,
          label: 'ESStorage 详情'
        })
      }
    >
      {clusterName || `#${clusterId}`}
    </Link>
  );
}

function Info({ label, value, raw }: { label: string; value: React.ReactNode; raw?: boolean }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      {raw ? value : <strong>{value}</strong>}
    </div>
  );
}

function formatOptional(value: string | number | null | undefined, suffix = '') {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return `${String(value)}${suffix}`;
}

function StoreSize({ value }: { value: string | null | undefined }) {
  if (!value) {
    return <span className="muted-text">-</span>;
  }

  return <span title={`原始值: ${value}`}>{formatStoreSize(value)}</span>;
}

function formatStoreSize(value: string) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) {
    return value;
  }

  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let unitIndex = 0;
  let size = bytes;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  const formattedSize = unitIndex === 0 || size >= 100 ? size.toFixed(0) : size.toFixed(1);
  return `${formattedSize} ${units[unitIndex]}`;
}
