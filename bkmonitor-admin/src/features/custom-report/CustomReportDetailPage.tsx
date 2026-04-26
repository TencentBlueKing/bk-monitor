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
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { useCustomReportDetail, useCustomReportMetricList } from './queries';
import {
  customReportMetricListQuerySchema,
  customReportTypeSchema,
  type CustomReportMetric
} from './schemas';

export function CustomReportDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const reportType = customReportTypeSchema.safeParse(params.reportType).success
    ? customReportTypeSchema.parse(params.reportType)
    : null;
  const groupId = Number(params.groupId);
  const [metricFieldName, setMetricFieldName] = useState('');
  const [metricPage, setMetricPage] = useState(1);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const detailQuery = useCustomReportDetail(
    currentEnvironment!,
    {
      bkTenantId: currentTenantId,
      reportType: reportType ?? 'custom_metric',
      groupId
    },
    Boolean(currentEnvironment && reportType && Number.isFinite(groupId))
  );

  const metricQueryParams = customReportMetricListQuerySchema.parse({
    bkTenantId: currentTenantId,
    groupId,
    fieldName: metricFieldName || undefined,
    page: metricPage,
    pageSize: 20
  });
  const metricQuery = useCustomReportMetricList(
    currentEnvironment!,
    metricQueryParams,
    Boolean(currentEnvironment && reportType === 'custom_metric' && Number.isFinite(groupId))
  );

  const metricColumns = useMemo<Array<ColumnDef<CustomReportMetric>>>(
    () => [
      { header: 'field_name', cell: ({ row }) => <Truncated text={row.original.field_name} /> },
      { header: 'type', accessorKey: 'type' },
      { header: 'unit', accessorKey: 'unit' },
      { header: 'description', accessorKey: 'description' },
      {
        header: 'active',
        cell: ({ row }) => formatBoolean(row.original.is_active)
      },
      {
        header: '更新时间',
        cell: ({ row }) => formatDateTime(row.original.last_modify_time)
      }
    ],
    []
  );

  if (!currentEnvironment || !reportType || !Number.isFinite(groupId)) {
    return <PageState title="自定义上报参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载自定义上报详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const { report, datasource, result_table, monitor_web_relation, apm_relations, event_fields } =
    detailQuery.data;

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">自定义上报详情</div>
          <h2>{report.group_name}</h2>
        </div>
        <Button
          variant="secondary"
          onClick={() => void navigate({ to: '/custom-reports', search: routeSearch })}
        >
          返回自定义上报列表
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info label="report_type" value={<Badge>{report.report_type}</Badge>} />
          <Info label="group_id" value={String(report.group_id)} />
          <Info label="租户" value={report.bk_tenant_id} />
          <Info label="业务" value={String(report.bk_biz_id ?? '-')} />
          <Info label="bk_data_id" value={String(report.bk_data_id ?? '-')} />
          <Info label="table_id" value={report.table_id ?? '-'} />
          <Info label="data_label" value={report.data_label ?? '-'} />
          <Info label="created_from" value={report.created_from ?? '-'} />
          <Info label="启用" value={formatBoolean(report.is_enable)} />
          <Info label="状态" value={report.status ?? '-'} />
          <Info label="更新时间" value={formatDateTime(report.last_modify_time)} />
        </CardContent>
      </Card>

      <div className="section-stack">
        <section>
          <h3>核心关联</h3>
          <Card>
            <CardContent className="detail-grid">
              <Info
                label="DataSource"
                value={
                  datasource ? (
                    <Link
                      to="/datasources/$bkDataId"
                      params={{ bkDataId: String(datasource.bk_data_id) }}
                      search={routeSearch}
                      className="link"
                    >
                      {datasource.bk_data_id} / {datasource.data_name}
                    </Link>
                  ) : (
                    '-'
                  )
                }
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
                    >
                      {result_table.table_id}
                    </Link>
                  ) : (
                    '-'
                  )
                }
              />
              <Info label="APM 关联数" value={String(apm_relations.length)} />
              <Info label="monitor_web" value={monitor_web_relation ? '存在' : '-'} />
            </CardContent>
          </Card>
        </section>

        {report.report_type === 'custom_metric' ? (
          <section>
            <h3>TimeSeriesMetric</h3>
            <form
              className="inline-filter"
              onSubmit={(event) => {
                event.preventDefault();
                setMetricPage(1);
              }}
            >
              <div className="grid gap-1.5">
                <Label>field_name</Label>
                <Input
                  value={metricFieldName}
                  onChange={(event) => setMetricFieldName(event.target.value)}
                />
              </div>
              <Button type="submit">
                <Search aria-hidden="true" size={16} />
                过滤
              </Button>
            </form>
            {metricQuery.isLoading ? (
              <PageState title="正在加载指标..." />
            ) : metricQuery.isError ? (
              <PageState title="指标加载失败" description={String(metricQuery.error)} />
            ) : (
              <>
                <DataTable data={metricQuery.data?.items ?? []} columns={metricColumns} />
                <Card>
                  <CardContent className="pager">
                    <Button
                      variant="secondary"
                      disabled={metricPage <= 1}
                      onClick={() => setMetricPage((value) => value - 1)}
                    >
                      <ChevronLeft aria-hidden="true" size={16} />
                      上一页
                    </Button>
                    <span>
                      第 {metricPage} 页 / 共 {metricQuery.data?.total ?? 0} 个指标
                    </span>
                    <Button
                      variant="secondary"
                      disabled={(metricQuery.data?.items.length ?? 0) < metricQueryParams.pageSize}
                      onClick={() => setMetricPage((value) => value + 1)}
                    >
                      下一页
                      <ChevronRight aria-hidden="true" size={16} />
                    </Button>
                  </CardContent>
                </Card>
              </>
            )}
          </section>
        ) : null}

        {report.report_type !== 'custom_metric' ? (
          <section>
            <h3>字段/事件摘要</h3>
            <JsonBlock value={event_fields} />
          </section>
        ) : null}

        <section>
          <h3>monitor_web / APM 关系</h3>
          <div className="grid two-column gap-4">
            <JsonBlock value={monitor_web_relation ?? {}} />
            <JsonBlock value={apm_relations} />
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
