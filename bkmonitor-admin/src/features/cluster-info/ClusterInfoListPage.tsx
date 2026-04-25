import { Link, useLocation } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import {
  FilterToolbar,
  type FilterField,
  type FilterValue
} from '../../shared/components/FilterToolbar';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { buildHref, rememberReturnTarget } from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { CLUSTER_TYPE_OPTIONS, CLUSTER_TYPE_TONE } from './constants';
import { clusterInfoListQuerySchema, type ClusterInfoSummary } from './schemas';
import { useClusterInfoList } from './queries';

const FILTER_FIELDS: FilterField[] = [
  { key: 'clusterName', label: 'cluster_name', type: 'text' },
  { key: 'clusterType', label: 'cluster_type', type: 'select', options: CLUSTER_TYPE_OPTIONS },
  { key: 'isDefaultCluster', label: 'is_default_cluster', type: 'boolean', advanced: true },
  { key: 'registeredSystem', label: 'registered_system', type: 'text', advanced: true }
];

export function ClusterInfoListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [drafts, setDrafts] = useState<Record<string, FilterValue>>({});
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>({});

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const query = clusterInfoListQuerySchema.parse({
    bkTenantId: currentTenantId,
    clusterName: activeFilters.clusterName || undefined,
    clusterType: activeFilters.clusterType || undefined,
    isDefaultCluster: activeFilters.isDefaultCluster
      ? activeFilters.isDefaultCluster === 'true'
      : undefined,
    registeredSystem: activeFilters.registeredSystem || undefined,
    page,
    pageSize
  });
  const clusterQuery = useClusterInfoList(currentEnvironment!, query);

  const columns = useMemo<Array<ColumnDef<ClusterInfoSummary>>>(
    () => [
      {
        header: 'cluster_id',
        cell: ({ row }) => (
          <Link
            to="/clusters/$clusterId"
            params={{ clusterId: String(row.original.cluster_id) }}
            search={routeSearch}
            onClick={() =>
              rememberReturnTarget(
                buildHref(`/clusters/${String(row.original.cluster_id)}`, routeSearch),
                {
                  href: currentHref,
                  label: '存储集群列表'
                }
              )
            }
            className="link"
          >
            {row.original.cluster_id}
          </Link>
        )
      },
      { header: 'cluster_name', accessorKey: 'cluster_name' },
      { header: 'display_name', accessorKey: 'display_name' },
      {
        header: 'cluster_type',
        cell: ({ row }) => (
          <Badge tone={CLUSTER_TYPE_TONE[row.original.cluster_type] ?? 'default'}>
            {row.original.cluster_type}
          </Badge>
        )
      },
      {
        header: 'domain',
        cell: ({ row }) => {
          if (!row.original.domain_name) return <span className="muted-text">–</span>;
          return `${row.original.domain_name}:${row.original.port ?? ''}`;
        }
      },
      { header: 'version', accessorKey: 'version' },
      {
        header: '默认集群',
        cell: ({ row }) => (
          <Badge tone={row.original.is_default_cluster ? 'success' : 'muted'}>
            {formatBoolean(row.original.is_default_cluster)}
          </Badge>
        )
      },
      { header: '系统', accessorKey: 'registered_system' },
      {
        header: '关联DS',
        cell: ({ row }) =>
          row.original.cluster_type === 'kafka' && row.original.associated_datasources > 0 ? (
            <Link
              to="/datasources"
              search={{ ...routeSearch, mqClusterId: row.original.cluster_id }}
              className="link"
              onClick={() =>
                rememberReturnTarget(
                  buildHref('/datasources', {
                    ...routeSearch,
                    mqClusterId: row.original.cluster_id
                  }),
                  {
                    href: currentHref,
                    label: '存储集群列表'
                  }
                )
              }
            >
              {row.original.associated_datasources}
            </Link>
          ) : (
            row.original.associated_datasources
          )
      },
      { header: '关联存储', accessorKey: 'associated_storages' },
      {
        header: '更新时间',
        cell: ({ row }) => formatDateTime(row.original.last_modify_time)
      }
    ],
    [currentHref, routeSearch]
  );

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Resource</div>
          <h2>存储集群</h2>
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
        loading={clusterQuery.isLoading}
      />
      {clusterQuery.isError ? (
        <PageState title="加载失败" description={String(clusterQuery.error)} />
      ) : clusterQuery.isLoading ? (
        <PageState title="正在加载存储集群..." />
      ) : (
        <>
          <DataTable data={clusterQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={clusterQuery.data?.total ?? 0}
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
