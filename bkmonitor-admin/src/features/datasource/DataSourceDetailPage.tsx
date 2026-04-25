import { Link, useNavigate, useParams } from '@tanstack/react-router';
import { Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import type { DataSourceDetailResponse } from './schemas';
import { useDatasourceDetail, useKafkaSample } from './queries';

export function DataSourceDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
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
    data_id_config,
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
          <Link to="/datasources" search={routeSearch}>
            返回列表
          </Link>
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
            <Badge tone="muted">safety_level: inspect</Badge>
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
                  <Button variant="ghost" size="sm" onClick={() => setShowKafkaSample(false)}>
                    收起
                  </Button>
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
          <JsonBlock value={data_id_config ?? { message: '无 DataIdConfig' }} />
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
