import { Link, useNavigate, useParams } from '@tanstack/react-router';
import { ExternalLink, Loader2 } from 'lucide-react';
import type { ColumnDef } from '@tanstack/react-table';
import { useCallback, useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { Truncated } from '../../shared/components/Truncated';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { useEsStorageList } from '../es-storage/queries';
import { esStorageListQuerySchema } from '../es-storage/schemas';
import { getComponentConfig } from './api';
import { CLUSTER_TYPE_TONE } from './constants';
import { useClusterInfoDetail } from './queries';
import { ES_STORAGE_TABLE_KIND_LABEL, ES_STORAGE_TABLE_KIND_TONE } from '../es-storage/constants';
import type { ClusterConfig } from './schemas';

export function ClusterInfoDetailPage() {
  const params = useParams({ strict: false });
  const navigate = useNavigate();
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const clusterId = Number(params.clusterId);

  const [esStoragePage, setEsStoragePage] = useState(1);
  const [esStoragePageSize, setEsStoragePageSize] = useState(20);

  const detailQuery = useClusterInfoDetail(currentEnvironment!, currentTenantId, clusterId);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const esStoragePreviewQueryParams = esStorageListQuerySchema.parse({
    bkTenantId: currentTenantId,
    storageClusterId: Number.isNaN(clusterId) ? undefined : clusterId,
    page: esStoragePage,
    pageSize: esStoragePageSize
  });
  const esStoragePreviewQuery = useEsStorageList(
    currentEnvironment!,
    esStoragePreviewQueryParams,
    detailQuery.data?.cluster_info.cluster_type === 'elasticsearch'
  );

  if (!currentEnvironment || Number.isNaN(clusterId)) {
    return <PageState title="存储集群参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载存储集群详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const { cluster_info, cluster_configs, related_result_tables, related_datasources } =
    detailQuery.data;
  const datasourceSearch =
    cluster_info.cluster_type === 'kafka'
      ? { ...routeSearch, mqClusterId: cluster_info.cluster_id }
      : routeSearch;
  const resultTableSearch = routeSearch;
  const esStorageSearch = { ...routeSearch, storageClusterId: cluster_info.cluster_id };

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">存储集群详情</div>
          <h2>{cluster_info.cluster_name}</h2>
        </div>
        <Button variant="secondary" onClick={() => void navigate({ to: '/clusters', search: routeSearch })}>
          返回 存储集群列表
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info label="cluster_name" value={cluster_info.cluster_name} />
          <Info label="display_name" value={cluster_info.display_name ?? '–'} />
          <Info
            label="cluster_type"
            value={
              <Badge tone={CLUSTER_TYPE_TONE[cluster_info.cluster_type] ?? 'default'}>
                {cluster_info.cluster_type}
              </Badge>
            }
            raw
          />
          <Info label="version" value={cluster_info.version ?? '–'} />
          <Info label="description" value={cluster_info.description ?? '–'} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="detail-grid">
            <h3 className="col-span-full text-sm font-semibold">连接信息</h3>
            <Info label="domain_name" value={cluster_info.domain_name ?? '–'} />
            <Info label="port" value={String(cluster_info.port ?? '–')} />
            <Info label="schema" value="–" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="detail-grid">
            <h3 className="col-span-full text-sm font-semibold">安全配置</h3>
            <Info label="SSL" value="–" />
            <Info label="Auth" value="–" />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info
            label="默认集群"
            value={
              <Badge tone={cluster_info.is_default_cluster ? 'success' : 'muted'}>
                {formatBoolean(cluster_info.is_default_cluster)}
              </Badge>
            }
            raw
          />
          <Info label="注册系统" value={cluster_info.registered_system ?? '–'} />
          <Info label="label" value={cluster_info.label ?? '–'} />
          <Info label="创建时间" value={formatDateTime(cluster_info.create_time)} />
          <Info label="更新时间" value={formatDateTime(cluster_info.last_modify_time)} />
        </CardContent>
      </Card>

      <section className="min-w-0">
        <h3>ClusterConfig</h3>
        {cluster_configs.length === 0 ? (
          <PageState title="暂无 ClusterConfig" />
        ) : (
          <ClusterConfigTable
            configs={cluster_configs}
            currentEnvironment={currentEnvironment}
            currentTenantId={currentTenantId}
            clusterId={cluster_info.cluster_id}
          />
        )}
      </section>

      <Card>
        <CardContent className="detail-grid">
          <Info
            label="关联结果表"
            value={
              <Link
                to="/result-tables"
                search={resultTableSearch}
                className="link"
              >
                {related_result_tables}
              </Link>
            }
            raw
          />
          {cluster_info.cluster_type === 'elasticsearch' ? (
            <Info
              label="关联 ESStorage"
              value={
                <Link
                  to="/es-storages"
                  search={esStorageSearch}
                  className="link"
                >
                  {cluster_info.associated_storages}
                </Link>
              }
              raw
            />
          ) : null}
          <Info
            label="关联数据源"
            value={
              <Link
                to="/datasources"
                search={datasourceSearch}
                className="link"
              >
                {related_datasources}
              </Link>
            }
            raw
          />
        </CardContent>
      </Card>

      {cluster_info.cluster_type === 'elasticsearch' ? (
        <section className="min-w-0">
          <div className="mb-3 flex items-center gap-2">
            <h3>关联 ESStorage</h3>
            <Link
              to="/es-storages"
              search={esStorageSearch}
              className="link inline-flex items-center"
              title="查看全部 ESStorage"
            >
              <ExternalLink aria-hidden="true" size={14} />
            </Link>
          </div>
          {esStoragePreviewQuery.isLoading ? (
            <PageState title="正在加载关联 ESStorage..." />
          ) : esStoragePreviewQuery.isError ? (
            <PageState
              title="关联 ESStorage 加载失败"
              description={String(esStoragePreviewQuery.error)}
            />
          ) : (
            <>
              <DataTable
                data={esStoragePreviewQuery.data?.items ?? []}
                emptyText="暂无关联 ESStorage"
                columns={[
                  {
                    header: 'table_id',
                    size: 260,
                    cell: ({ row }) => (
                      <Link
                        to="/es-storages/$tableId"
                        params={{ tableId: row.original.table_id }}
                        search={routeSearch}
                        className="link inline-block"
                      >
                        <Truncated text={row.original.table_id} maxW="240px" />
                      </Link>
                    )
                  },
                  {
                    header: 'table_kind',
                    cell: ({ row }) => {
                      const kind = row.original.table_kind;
                      return (
                        <Badge tone={ES_STORAGE_TABLE_KIND_TONE[kind]}>
                          {ES_STORAGE_TABLE_KIND_LABEL[kind]}
                        </Badge>
                      );
                    }
                  },
                  {
                    header: 'origin_table_id',
                    size: 220,
                    cell: ({ row }) => {
                      const v = row.original.origin_table_id;
                      if (!v)
                        return <span className="muted-text whitespace-nowrap">{'\u2013'}</span>;
                      return <Truncated text={v} maxW="200px" />;
                    }
                  },
                  {
                    header: 'index_set',
                    size: 200,
                    cell: ({ row }) => {
                      const v = row.original.index_set;
                      if (!v)
                        return <span className="muted-text whitespace-nowrap">{'\u2013'}</span>;
                      return <Truncated text={v} maxW="180px" />;
                    }
                  },
                  { header: 'retention', accessorKey: 'retention' }
                ]}
              />
              <Pagination
                page={esStoragePage}
                pageSize={esStoragePageSize}
                total={esStoragePreviewQuery.data?.total ?? 0}
                onPageChange={setEsStoragePage}
                onPageSizeChange={(size) => {
                  setEsStoragePageSize(size);
                  setEsStoragePage(1);
                }}
              />
            </>
          )}
        </section>
      ) : null}
    </section>
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

interface ComponentConfigState {
  loading: boolean;
  data: unknown;
  error: string | null;
}

function ClusterConfigTable({
  configs,
  currentEnvironment,
  currentTenantId,
  clusterId
}: {
  configs: ClusterConfig[];
  currentEnvironment: NonNullable<ReturnType<typeof useEnvironmentConfig>['currentEnvironment']>;
  currentTenantId: string;
  clusterId: number;
}) {
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const [fetchedConfigs, setFetchedConfigs] = useState<Record<string, ComponentConfigState>>({});
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const handleFetch = useCallback(
    async (config: ClusterConfig) => {
      const key = `${config.namespace}::${config.kind}::${config.name}`;
      setFetchedConfigs((prev) => ({ ...prev, [key]: { loading: true, data: null, error: null } }));
      setExpandedRows((prev) => new Set(prev).add(key));

      try {
        const result = await getComponentConfig(currentEnvironment, {
          bkTenantId: currentTenantId,
          clusterId,
          namespace: config.namespace,
          kind: config.kind,
          name: config.name
        });
        setFetchedConfigs((prev) => ({
          ...prev,
          [key]: { loading: false, data: result.component_config, error: null }
        }));
      } catch (err) {
        setFetchedConfigs((prev) => ({
          ...prev,
          [key]: { loading: false, data: null, error: String(err) }
        }));
      }
    },
    [currentEnvironment, currentTenantId, clusterId]
  );

  const toggleExpand = useCallback((key: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const columns = useMemo<Array<ColumnDef<ClusterConfig>>>(
    () => [
      { header: 'namespace', accessorKey: 'namespace' },
      { header: 'kind', accessorKey: 'kind' },
      {
        header: 'name',
        cell: ({ row }) => {
          const config = row.original;
          return (
            <Link
              to="/data-links/detail"
              search={{
                ...routeSearch,
                kind: 'ClusterConfig',
                clusterKind: config.kind,
                namespace: config.namespace,
                name: config.name
              }}
              className="link"
            >
              {config.name}
            </Link>
          );
        }
      },
      {
        header: 'created_at',
        cell: ({ row }) => formatDateTime(row.original.created_at)
      },
      {
        header: 'updated_at',
        cell: ({ row }) => formatDateTime(row.original.updated_at)
      },
      {
        header: '操作',
        cell: ({ row }) => {
          const config = row.original;
          const key = `${config.namespace}::${config.kind}::${config.name}`;
          const fetched = fetchedConfigs[key];
          const isExpanded = expandedRows.has(key);

          return (
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={fetched?.loading}
                onClick={() => handleFetch(config)}
              >
                {fetched?.loading ? (
                  <Loader2 aria-hidden="true" size={14} className="animate-spin" />
                ) : null}
                获取配置
              </Button>
              {fetched && !fetched.loading ? (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => toggleExpand(key)}
                >
                  {isExpanded ? '收起' : '展开'}
                </button>
              ) : null}
            </div>
          );
        }
      }
    ],
    [fetchedConfigs, expandedRows, handleFetch, toggleExpand, routeSearch]
  );

  const renderExpandedRow = useCallback(
    (row: ClusterConfig) => {
      const key = `${row.namespace}::${row.kind}::${row.name}`;
      const config = fetchedConfigs[key];
      if (!config) return null;

      if (config.loading) {
        return (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 aria-hidden="true" size={14} className="animate-spin" />
            加载中...
          </div>
        );
      }

      if (config.error) {
        return <div className="text-sm text-destructive">{config.error}</div>;
      }

      return <JsonBlock value={config.data} />;
    },
    [fetchedConfigs]
  );

  return <DataTable data={configs} columns={columns} renderExpandedRow={renderExpandedRow} />;
}
