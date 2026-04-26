import { Link, useNavigate, useParams } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Truncated } from '../../shared/components/Truncated';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import { Label } from '../../shared/components/ui/label';
import { DataTable } from '../../shared/table/DataTable';
import { formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { useApmApplicationDetail, useApmServiceList } from './queries';
import { apmServiceListQuerySchema, type ApmService } from './schemas';

export function ApmApplicationDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const applicationId = Number(params.applicationId);
  const [serviceName, setServiceName] = useState('');
  const [servicePage, setServicePage] = useState(1);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const detailQuery = useApmApplicationDetail(
    currentEnvironment!,
    {
      bkTenantId: currentTenantId,
      applicationId
    },
    Boolean(currentEnvironment && Number.isFinite(applicationId))
  );
  const serviceQueryParams = apmServiceListQuerySchema.parse({
    bkTenantId: currentTenantId,
    applicationId,
    serviceName: serviceName || undefined,
    page: servicePage,
    pageSize: 20
  });
  const serviceQuery = useApmServiceList(
    currentEnvironment!,
    serviceQueryParams,
    Boolean(currentEnvironment && Number.isFinite(applicationId))
  );

  const serviceColumns = useMemo<Array<ColumnDef<ApmService>>>(
    () => [
      {
        header: 'service_name',
        cell: ({ row }) => <Truncated text={row.original.service_name} maxW="240px" />
      },
      { header: 'topo_key', cell: ({ row }) => <Truncated text={row.original.topo_key} /> },
      { header: 'kind', accessorKey: 'kind' },
      { header: 'category', accessorKey: 'category' },
      { header: 'instances', accessorKey: 'instance_count' },
      { header: 'endpoints', accessorKey: 'endpoint_count' },
      {
        header: 'last_seen',
        cell: ({ row }) => formatDateTime(row.original.last_seen_time)
      }
    ],
    []
  );

  if (!currentEnvironment || !Number.isFinite(applicationId)) {
    return <PageState title="APM 参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载 APM 详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const {
    application,
    datasources,
    result_tables,
    custom_reports,
    service_summary,
    topo_summary,
    topo_nodes_preview,
    topo_relations_preview
  } = detailQuery.data;

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">APM Detail</div>
          <h2>{application.app_name}</h2>
        </div>
        <Button
          variant="secondary"
          onClick={() => void navigate({ to: '/apm/applications', search: routeSearch })}
        >
          返回 APM 列表
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info label="application_id" value={String(application.application_id)} />
          <Info label="别名" value={application.app_alias ?? '-'} />
          <Info label="租户" value={application.bk_tenant_id} />
          <Info label="业务" value={String(application.bk_biz_id)} />
          <Info label="status" value={<Badge>{application.status ?? '-'}</Badge>} />
          <Info label="Service" value={String(application.service_count)} />
          <Info label="Topo" value={String(application.topo_node_count)} />
          <Info label="更新时间" value={formatDateTime(application.last_modify_time)} />
        </CardContent>
      </Card>

      <div className="section-stack">
        <section>
          <h3>DataSource</h3>
          <DataTable
            data={datasources}
            columns={[
              {
                header: 'bk_data_id',
                cell: ({ row }) => (
                  <Link
                    to="/datasources/$bkDataId"
                    params={{ bkDataId: String(row.original.bk_data_id) }}
                    search={routeSearch}
                    className="link"
                  >
                    {row.original.bk_data_id}
                  </Link>
                )
              },
              {
                header: 'data_name',
                cell: ({ row }) => <Truncated text={row.original.data_name} />
              },
              { header: 'source_label', accessorKey: 'source_label' },
              { header: 'type_label', accessorKey: 'type_label' },
              { header: 'is_enable', cell: ({ row }) => String(row.original.is_enable) }
            ]}
          />
        </section>

        <section>
          <h3>ResultTable</h3>
          <DataTable
            data={result_tables}
            columns={[
              {
                header: 'table_id',
                cell: ({ row }) => (
                  <Link
                    to="/result-tables/$tableId"
                    params={{ tableId: row.original.table_id }}
                    search={routeSearch}
                    className="link"
                  >
                    <Truncated text={row.original.table_id} />
                  </Link>
                )
              },
              { header: 'table_name_zh', accessorKey: 'table_name_zh' },
              { header: 'data_label', accessorKey: 'data_label' },
              { header: 'field_count', accessorKey: 'field_count' }
            ]}
          />
        </section>

        <section>
          <h3>自定义上报关联</h3>
          <DataTable
            data={custom_reports}
            columns={[
              {
                header: 'group_id',
                cell: ({ row }) => (
                  <Link
                    to="/custom-reports/$reportType/$groupId"
                    params={{
                      reportType: row.original.report_type,
                      groupId: String(row.original.group_id)
                    }}
                    search={routeSearch}
                    className="link"
                  >
                    {row.original.group_id}
                  </Link>
                )
              },
              { header: 'report_type', accessorKey: 'report_type' },
              {
                header: 'group_name',
                cell: ({ row }) => <Truncated text={row.original.group_name} />
              },
              { header: 'bk_data_id', accessorKey: 'bk_data_id' },
              {
                header: 'table_id',
                cell: ({ row }) => <Truncated text={row.original.table_id ?? '-'} />
              }
            ]}
          />
        </section>

        <section>
          <h3>Service</h3>
          <form
            className="inline-filter"
            onSubmit={(event) => {
              event.preventDefault();
              setServicePage(1);
            }}
          >
            <div className="grid gap-1.5">
              <Label>service_name</Label>
              <Input value={serviceName} onChange={(event) => setServiceName(event.target.value)} />
            </div>
            <Button type="submit">
              <Search aria-hidden="true" size={16} />
              过滤
            </Button>
          </form>
          {serviceQuery.isLoading ? (
            <PageState title="正在加载 Service..." />
          ) : serviceQuery.isError ? (
            <PageState title="Service 加载失败" description={String(serviceQuery.error)} />
          ) : (
            <>
              <DataTable data={serviceQuery.data?.items ?? []} columns={serviceColumns} />
              <Card>
                <CardContent className="pager">
                  <Button
                    variant="secondary"
                    disabled={servicePage <= 1}
                    onClick={() => setServicePage((value) => value - 1)}
                  >
                    <ChevronLeft aria-hidden="true" size={16} />
                    上一页
                  </Button>
                  <span>
                    第 {servicePage} 页 / 共 {serviceQuery.data?.total ?? 0} 个 Service
                  </span>
                  <Button
                    variant="secondary"
                    disabled={(serviceQuery.data?.items.length ?? 0) < serviceQueryParams.pageSize}
                    onClick={() => setServicePage((value) => value + 1)}
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
          <h3>Topo 摘要</h3>
          <div className="grid two-column gap-4">
            <JsonBlock value={{ service_summary, topo_summary, topo_nodes_preview }} />
            <JsonBlock value={topo_relations_preview} />
          </div>
        </section>
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
