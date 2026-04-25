import { Link, useLocation, useNavigate, useParams } from '@tanstack/react-router';
import { Loader2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ColumnDef } from '@tanstack/react-table';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Textarea } from '../../shared/components/ui/textarea';
import {
  buildHref,
  getStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { getDataIdComponentConfig } from './api';
import type { DataIdConfig, DataSourceDetailResponse } from './schemas';
import { useDatasourceDetail, useKafkaSample } from './queries';

export function DataSourceDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const bkDataId = Number(params.bkDataId);

  const initialTenantRef = useRef(currentTenantId);
  useEffect(() => {
    if (currentTenantId !== initialTenantRef.current) {
      void navigate({
        to: '/datasources',
        search: createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId)
      });
    }
  }, [currentTenantId, currentEnvironment?.id, navigate]);

  const detailQuery = useDatasourceDetail(currentEnvironment!, currentTenantId, bkDataId);
  const kafkaSampleMutation = useKafkaSample(currentEnvironment!);
  const [kafkaSampleResult, setKafkaSampleResult] = useState<{
    topic?: string;
    count?: number;
    items?: unknown[];
  } | null>(null);
  const [kafkaSampleError, setKafkaSampleError] = useState<string | null>(null);
  const [showKafkaSample, setShowKafkaSample] = useState(false);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const fallbackReturnHref = buildHref('/datasources', routeSearch);
  const returnTarget = getStoredReturnTarget(currentHref, fallbackReturnHref, 'DataSource 列表');

  if (!currentEnvironment || Number.isNaN(bkDataId)) {
    return <PageState title="DataSource 参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载 DataSource 详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const {
    datasource,
    options,
    space_datasources,
    result_tables,
    data_id_configs,
    kafka_cluster,
    kafka_topic_config
  } = detailQuery.data;

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">DataSource Detail</div>
          <h2>{datasource.data_name}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>
      <Card>
        <CardContent className="detail-grid">
          <Info label="bk_data_id" value={String(datasource.bk_data_id)} />
          <Info label="租户" value={datasource.bk_tenant_id} />
          <Info label="类型" value={datasource.type_label} />
          <Info label="来源" value={datasource.source_label} />
          <Info label="created_from" value={datasource.created_from} />
          <Info label="空间" value={datasource.space_uid ?? '-'} />
          <Info
            label="Kafka 集群 ID"
            value={formatOptionalValue(kafka_cluster?.cluster_id ?? datasource.mq_cluster_id)}
          />
          <Info label="Kafka 集群名称" value={getKafkaClusterName(kafka_cluster)} />
          <Info
            label="Kafka Topic 配置 ID"
            value={formatOptionalValue(kafka_topic_config?.id ?? datasource.mq_config_id)}
          />
          <Info label="启用" value={formatBoolean(datasource.is_enable)} />
          <Info label="Token" value={datasource.has_token ? '已配置' : '未配置'} />
          <Info label="创建时间" value={formatDateTime(datasource.create_time)} />
          <Info label="更新时间" value={formatDateTime(datasource.last_modify_time)} />
        </CardContent>
      </Card>
      <div className="section-stack">
        <section>
          <h3>KafkaTopic 配置</h3>
          {kafka_topic_config ? (
            <DataTable
              data={[kafka_topic_config]}
              columns={[
                { header: 'id', accessorKey: 'id' },
                { header: 'bk_data_id', accessorKey: 'bk_data_id' },
                { header: 'topic', accessorKey: 'topic' },
                { header: 'partition', accessorKey: 'partition' },
                {
                  header: 'batch_size',
                  cell: ({ row }) => formatOptionalValue(row.original.batch_size)
                },
                {
                  header: 'flush_interval',
                  cell: ({ row }) => formatOptionalValue(row.original.flush_interval)
                },
                {
                  header: 'consume_rate',
                  cell: ({ row }) => formatOptionalValue(row.original.consume_rate)
                }
              ]}
            />
          ) : (
            <PageState title="未找到 KafkaTopic 配置" />
          )}
          <div className="flex items-center gap-3">
            <Button
              variant="secondary"
              disabled={kafkaSampleMutation.isPending}
              onClick={() => {
                setKafkaSampleError(null);
                setKafkaSampleResult(null);
                kafkaSampleMutation.mutate(
                  { bkTenantId: currentTenantId, bkDataId },
                  {
                    onSuccess: (data) => {
                      setKafkaSampleResult(data);
                      setShowKafkaSample(true);
                    },
                    onError: (error) => {
                      setKafkaSampleError(String(error));
                      setShowKafkaSample(true);
                    }
                  }
                );
              }}
            >
              {kafkaSampleMutation.isPending ? (
                <Loader2 aria-hidden="true" size={16} className="animate-spin" />
              ) : null}
              拉取最新数据
            </Button>
            {kafkaSampleResult || kafkaSampleError ? (
              <Button
                variant="ghost"
                type="button"
                onClick={() => setShowKafkaSample((value) => !value)}
              >
                {showKafkaSample ? '收起数据' : '展开数据'}
              </Button>
            ) : null}
            <span className="text-sm text-muted-foreground">默认只拉取最新 1 条</span>
          </div>
          {showKafkaSample && kafkaSampleResult ? (
            <Card>
              <CardContent className="py-3 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    {kafkaSampleResult.topic ? (
                      <span>
                        topic:{' '}
                        <strong className="text-foreground">{kafkaSampleResult.topic}</strong>
                      </span>
                    ) : null}
                    {kafkaSampleResult.count !== undefined ? (
                      <span>
                        记录数:{' '}
                        <strong className="text-foreground">{kafkaSampleResult.count}</strong>
                      </span>
                    ) : null}
                  </div>
                </div>
                {kafkaSampleResult.items && kafkaSampleResult.items.length > 0 ? (
                  <JsonBlock value={kafkaSampleResult.items} />
                ) : null}
              </CardContent>
            </Card>
          ) : null}
          {showKafkaSample && kafkaSampleError ? (
            <Card className="border-destructive/50">
              <CardContent className="py-3 text-sm text-destructive">
                {kafkaSampleError}
              </CardContent>
            </Card>
          ) : null}
        </section>
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
          <h3>空间关系</h3>
          <DataTable
            data={space_datasources}
            columns={[
              { header: 'space_uid', accessorKey: 'space_uid' },
              { header: 'space_type_id', accessorKey: 'space_type_id' },
              { header: 'space_id', accessorKey: 'space_id' },
              {
                header: 'from_authorization',
                cell: ({ row }) => formatBoolean(row.original.from_authorization)
              }
            ]}
          />
        </section>
        <section>
          <h3>结果表关系</h3>
          <DataTable
            data={result_tables}
            columns={[
              {
                header: 'table_id',
                cell: ({ row }) => (
                  <Link
                    to="/result-tables/$tableId"
                    params={{
                      tableId: row.original.table_id
                    }}
                    search={routeSearch}
                    onClick={() =>
                      rememberReturnTarget(
                        buildHref(`/result-tables/${row.original.table_id}`, routeSearch),
                        {
                          href: currentHref,
                          label: 'DataSource 详情'
                        }
                      )
                    }
                    className="link"
                  >
                    {row.original.table_id}
                  </Link>
                )
              },
              { header: '中文名', accessorKey: 'table_name_zh' },
              { header: '业务', accessorKey: 'bk_biz_id' },
              { header: 'data_label', accessorKey: 'data_label' },
              {
                header: '状态',
                cell: ({ row }) => (
                  <div className="badge-row">
                    <Badge tone={row.original.is_enable ? 'success' : 'danger'}>
                      {row.original.is_enable ? '启用' : '停用'}
                    </Badge>
                    <Badge tone={row.original.is_deleted ? 'danger' : 'muted'}>
                      {row.original.is_deleted ? '已删除' : '未删除'}
                    </Badge>
                  </div>
                )
              }
            ]}
          />
        </section>
        <section>
          <h3>DataIdConfig</h3>
          {data_id_configs && data_id_configs.length > 0 ? (
            <DataIdConfigTable
              configs={data_id_configs}
              currentEnvironment={currentEnvironment}
              currentTenantId={currentTenantId}
            />
          ) : (
            <PageState title="无 DataIdConfig" />
          )}
        </section>
      </div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function getKafkaClusterName(cluster: DataSourceDetailResponse['kafka_cluster']) {
  if (!cluster) {
    return '-';
  }

  return cluster.display_name || cluster.cluster_name || `#${cluster.cluster_id}`;
}

function formatOptionalValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') {
    return '-';
  }

  return String(value);
}

interface DataIdComponentConfigState {
  loading: boolean;
  data: unknown;
  error: string | null;
}

function DataIdConfigTable({
  configs,
  currentEnvironment,
  currentTenantId
}: {
  configs: DataIdConfig[];
  currentEnvironment: NonNullable<ReturnType<typeof useEnvironmentConfig>['currentEnvironment']>;
  currentTenantId: string;
}) {
  const [fetchedConfigs, setFetchedConfigs] = useState<Record<string, DataIdComponentConfigState>>(
    {}
  );
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const handleFetch = useCallback(
    async (config: DataIdConfig) => {
      const key = `${config.namespace}::${config.kind}::${config.name}`;
      setFetchedConfigs((prev) => ({ ...prev, [key]: { loading: true, data: null, error: null } }));
      setExpandedRows((prev) => new Set(prev).add(key));

      try {
        const result = await getDataIdComponentConfig(currentEnvironment, {
          bkTenantId: currentTenantId,
          namespace: config.namespace,
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
    [currentEnvironment, currentTenantId]
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

  const columns = useMemo<Array<ColumnDef<DataIdConfig>>>(
    () => [
      { header: 'namespace', accessorKey: 'namespace' },
      { header: 'kind', accessorKey: 'kind' },
      { header: 'name', accessorKey: 'name' },
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
    [fetchedConfigs, expandedRows, handleFetch, toggleExpand]
  );

  const renderExpandedRow = useCallback(
    (row: DataIdConfig) => {
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

      return (
        <Textarea
          readOnly
          className="min-h-40 font-mono text-xs"
          value={config.data != null ? JSON.stringify(config.data, null, 2) : 'null'}
        />
      );
    },
    [fetchedConfigs]
  );

  return <DataTable data={configs} columns={columns} renderExpandedRow={renderExpandedRow} />;
}
