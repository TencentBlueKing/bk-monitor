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
import { Truncated } from '../../shared/components/Truncated';
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
        size: 90,
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
            className="link whitespace-nowrap"
          >
            {row.original.cluster_id}
          </Link>
        )
      },
      {
        header: 'cluster_name',
        size: 200,
        cell: ({ row }) => <Truncated text={row.original.cluster_name} maxW="200px" />
      },
      {
        header: 'display_name',
        size: 200,
        cell: ({ row }) => {
          const v = row.original.display_name;
          if (v == null) return <span className="muted-text whitespace-nowrap">-</span>;
          return <Truncated text={v} maxW="200px" />;
        }
      },
      {
        header: 'cluster_type',
        size: 130,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            <Badge tone={CLUSTER_TYPE_TONE[row.original.cluster_type] ?? 'default'}>
              {row.original.cluster_type}
            </Badge>
          </span>
        )
      },
      {
        header: 'domain',
        size: 220,
        cell: ({ row }) => {
          if (!row.original.domain_name)
            return <span className="muted-text whitespace-nowrap">–</span>;
          const text = `${row.original.domain_name}:${row.original.port ?? ''}`;
          return <Truncated text={text} maxW="220px" />;
        }
      },
      {
        header: 'version',
        size: 80,
        cell: ({ row }) => {
          const v = row.original.version;
          if (v == null) return <span className="muted-text whitespace-nowrap">-</span>;
          return <span className="whitespace-nowrap">{v}</span>;
        }
      },
      {
        header: '默认集群',
        size: 100,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            <Badge tone={row.original.is_default_cluster ? 'success' : 'muted'}>
              {formatBoolean(row.original.is_default_cluster)}
            </Badge>
          </span>
        )
      },
      {
        header: '系统',
        size: 120,
        cell: ({ row }) => {
          const v = row.original.registered_system;
          if (v == null) return <span className="muted-text whitespace-nowrap">-</span>;
          return <Truncated text={v} maxW="120px" />;
        }
      },
      {
        header: '关联DS',
        size: 80,
        cell: ({ row }) =>
          row.original.cluster_type === 'kafka' && row.original.associated_datasources > 0 ? (
            <Link
              to="/datasources"
              search={{ ...routeSearch, mqClusterId: row.original.cluster_id }}
              className="link whitespace-nowrap"
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
            <span className="whitespace-nowrap">{row.original.associated_datasources}</span>
          )
      },
      {
        header: '关联存储',
        size: 90,
        cell: ({ row }) =>
          row.original.cluster_type === 'elasticsearch' && row.original.associated_storages > 0 ? (
            <Link
              to="/es-storages"
              search={{ ...routeSearch, storageClusterId: row.original.cluster_id }}
              className="link whitespace-nowrap"
              onClick={() =>
                rememberReturnTarget(
                  buildHref('/es-storages', {
                    ...routeSearch,
                    storageClusterId: row.original.cluster_id
                  }),
                  {
                    href: currentHref,
                    label: '存储集群列表'
                  }
                )
              }
            >
              {row.original.associated_storages}
            </Link>
          ) : (
            <span className="whitespace-nowrap">{row.original.associated_storages}</span>
          )
      },
      {
        header: '更新时间',
        size: 150,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">{formatDateTime(row.original.last_modify_time)}</span>
        )
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
