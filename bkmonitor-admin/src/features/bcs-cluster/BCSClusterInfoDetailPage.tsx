import { Link, useLocation, useParams } from '@tanstack/react-router';

import { Badge } from '../../shared/components/Badge';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import {
  buildHref,
  getStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { BCS_STATUS_TONE } from './constants';
import { useBcsClusterDetail } from './queries';
import { DataTable } from '../../shared/table/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';

export function BCSClusterInfoDetailPage() {
  const params = useParams({ strict: false });
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const clusterId = params.clusterId ?? '';

  const detailQuery = useBcsClusterDetail(currentEnvironment!, currentTenantId, clusterId);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const fallbackReturnHref = buildHref('/bcs-clusters', routeSearch);
  const returnTarget = getStoredReturnTarget(currentHref, fallbackReturnHref, 'K8s 集群列表');

  const dsColumns = useMemo<
    Array<
      ColumnDef<{
        bk_data_id: number;
        data_name: string;
        source_label: string;
        type_label: string;
        is_enable: boolean;
      }>
    >
  >(
    () => [
      {
        header: 'bk_data_id',
        cell: ({ row }) => (
          <Link
            to="/datasources/$bkDataId"
            params={{ bkDataId: String(row.original.bk_data_id) }}
            search={routeSearch}
            onClick={() =>
              rememberReturnTarget(
                buildHref(`/datasources/${String(row.original.bk_data_id)}`, routeSearch),
                {
                  href: currentHref,
                  label: 'K8s 集群详情'
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
      { header: 'source_label', accessorKey: 'source_label' },
      { header: 'type_label', accessorKey: 'type_label' },
      {
        header: '启用',
        cell: ({ row }) => (
          <Badge tone={row.original.is_enable ? 'success' : 'danger'}>
            {formatBoolean(row.original.is_enable)}
          </Badge>
        )
      }
    ],
    [currentHref, routeSearch]
  );

  if (!currentEnvironment || !clusterId) {
    return <PageState title="K8s 集群参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载 K8s 集群详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const { cluster, datasource_summaries } = detailQuery.data;

  const dataIdFields = [
    { label: 'K8sMetricDataID', value: cluster.K8sMetricDataID },
    { label: 'CustomMetricDataID', value: cluster.CustomMetricDataID },
    { label: 'K8sEventDataID', value: cluster.K8sEventDataID },
    { label: 'CustomEventDataID', value: cluster.CustomEventDataID },
    { label: 'SystemLogDataID', value: cluster.SystemLogDataID },
    { label: 'CustomLogDataID', value: cluster.CustomLogDataID }
  ];

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">K8s 集群详情</div>
          <h2>{cluster.cluster_id}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info label="cluster_id" value={cluster.cluster_id} />
          <Info label="bcs_api_cluster_id" value={cluster.bcs_api_cluster_id ?? '–'} />
          <Info label="bk_biz_id" value={String(cluster.bk_biz_id ?? '–')} />
          <Info label="project_id" value={cluster.project_id ?? '–'} />
          <Info
            label="status"
            value={
              <Badge tone={BCS_STATUS_TONE[cluster.status] ?? 'default'}>{cluster.status}</Badge>
            }
            raw
          />
          <Info label="bk_env" value={cluster.bk_env ?? '–'} />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="detail-grid">
          <h3 className="col-span-full text-sm font-semibold">连接信息</h3>
          <Info label="domain_name" value={cluster.domain_name ?? '–'} />
          <Info label="port" value={String(cluster.port ?? '–')} />
          <Info label="server_address_path" value={cluster.server_address_path ?? '–'} />
          <Info label="api_key_type" value={cluster.api_key_type ?? '–'} />
          <Info
            label="has_api_key"
            value={
              <Badge tone={cluster.has_api_key ? 'success' : 'muted'}>
                {formatBoolean(cluster.has_api_key)}
              </Badge>
            }
            raw
          />
          <Info
            label="skip_ssl_verify"
            value={
              <Badge tone={cluster.is_skip_ssl_verify ? 'warning' : 'muted'}>
                {formatBoolean(cluster.is_skip_ssl_verify)}
              </Badge>
            }
            raw
          />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          <h3 className="mb-3 text-sm font-semibold">Data IDs</h3>
          <div className="flex flex-wrap gap-3">
            {dataIdFields.map((field) => (
              <div
                key={field.label}
                className="rounded-md border border-border bg-muted/30 px-4 py-3 text-center min-w-[140px]"
              >
                <div className="text-xs text-muted-foreground mb-1">{field.label}</div>
                {field.value && field.value > 0 ? (
                  <Link
                    to="/datasources/$bkDataId"
                    params={{ bkDataId: String(field.value) }}
                    search={routeSearch}
                    onClick={() =>
                      rememberReturnTarget(
                        buildHref(`/datasources/${String(field.value)}`, routeSearch),
                        {
                          href: currentHref,
                          label: 'K8s 集群详情'
                        }
                      )
                    }
                    className="link text-base"
                  >
                    {field.value}
                  </Link>
                ) : (
                  <span className="text-base muted-text">–</span>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="detail-grid">
          <Info label="operator_ns" value={cluster.operator_ns ?? '–'} />
          <Info label="创建时间" value={formatDateTime(cluster.create_time)} />
          <Info label="更新时间" value={formatDateTime(cluster.last_modify_time)} />
        </CardContent>
      </Card>

      {datasource_summaries && datasource_summaries.length > 0 ? (
        <section>
          <h3>关联数据源</h3>
          <DataTable data={datasource_summaries} columns={dsColumns} />
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
