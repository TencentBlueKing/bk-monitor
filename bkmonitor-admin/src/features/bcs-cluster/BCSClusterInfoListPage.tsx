import { Link } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { FilterToolbar, type FilterField } from '../../shared/components/FilterToolbar';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { DataTable } from '../../shared/table/DataTable';
import { formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { BCS_STATUS_OPTIONS, BCS_STATUS_TONE } from './constants';
import { bcsClusterListQuerySchema, type BcsClusterSummary } from './schemas';
import { useBcsClusterList } from './queries';

const FILTER_FIELDS: FilterField[] = [
  { key: 'clusterId', label: 'cluster_id', type: 'text' },
  { key: 'bkBizId', label: 'bk_biz_id', type: 'number' },
  { key: 'status', label: 'status', type: 'select', options: BCS_STATUS_OPTIONS }
];

function DataIdsSummary({ row }: { row: BcsClusterSummary }) {
  const items: Array<{ label: string; value: number }> = [
    { label: 'K8s指标', value: row.K8sMetricDataID ?? 0 },
    { label: '自定义指标', value: row.CustomMetricDataID ?? 0 },
    { label: 'K8s事件', value: row.K8sEventDataID ?? 0 },
    { label: '自定义事件', value: row.CustomEventDataID ?? 0 },
    { label: '系统日志', value: row.SystemLogDataID ?? 0 },
    { label: '自定义日志', value: row.CustomLogDataID ?? 0 }
  ];

  const active = items.filter((item) => item.value > 0);

  if (active.length === 0) {
    return <span className="muted-text">–</span>;
  }

  return (
    <div className="flex flex-wrap gap-1 text-xs">
      {active.map((item) => (
        <span key={item.label} className="rounded bg-muted px-1.5 py-0.5">
          {item.label}:{item.value}
        </span>
      ))}
    </div>
  );
}

export function BCSClusterInfoListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const query = bcsClusterListQuerySchema.parse({
    bkTenantId: currentTenantId,
    clusterId: activeFilters.clusterId || undefined,
    bkBizId: activeFilters.bkBizId || undefined,
    status: activeFilters.status || undefined,
    page,
    pageSize
  });
  const bcsQuery = useBcsClusterList(currentEnvironment!, query);

  const columns = useMemo<Array<ColumnDef<BcsClusterSummary>>>(
    () => [
      {
        header: 'cluster_id',
        cell: ({ row }) => (
          <Link
            to="/bcs-clusters/$clusterId"
            params={{ clusterId: row.original.cluster_id }}
            search={routeSearch}
            className="link"
          >
            {row.original.cluster_id}
          </Link>
        )
      },
      { header: 'API cluster ID', accessorKey: 'bcs_api_cluster_id' },
      { header: '业务', accessorKey: 'bk_biz_id' },
      { header: '项目', accessorKey: 'project_id' },
      {
        header: '状态',
        cell: ({ row }) => (
          <Badge tone={BCS_STATUS_TONE[row.original.status] ?? 'default'}>
            {BCS_STATUS_OPTIONS.find((o) => o.value === row.original.status)?.label ??
              row.original.status}
          </Badge>
        )
      },
      { header: '环境', accessorKey: 'bk_env' },
      {
        header: 'DataIDs',
        cell: ({ row }) => <DataIdsSummary row={row.original} />
      },
      { header: 'operator_ns', accessorKey: 'operator_ns' },
      {
        header: '更新时间',
        cell: ({ row }) => formatDateTime(row.original.last_modify_time)
      }
    ],
    [routeSearch]
  );

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Resource</div>
          <h2>K8s 集群</h2>
        </div>
      </div>
      <FilterToolbar
        fields={FILTER_FIELDS}
        values={drafts}
        onChange={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
        onSearch={() => {
          setActiveFilters({ ...drafts });
          setPage(1);
        }}
        onReset={() => {
          setDrafts({});
          setActiveFilters({});
          setPage(1);
        }}
        loading={bcsQuery.isLoading}
      />
      {bcsQuery.isError ? (
        <PageState title="加载失败" description={String(bcsQuery.error)} />
      ) : bcsQuery.isLoading ? (
        <PageState title="正在加载 K8s 集群..." />
      ) : (
        <>
          <DataTable data={bcsQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={bcsQuery.data?.total ?? 0}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </>
      )}
    </section>
  );
}
