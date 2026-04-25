import { Link, useLocation, useSearch } from '@tanstack/react-router';
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
import { Button } from '../../shared/components/ui/button';
import {
  getOptionalStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { CREATED_FROM_OPTIONS, SOURCE_LABEL_COMMON, TYPE_LABEL_COMMON } from './constants';
import { datasourceListQuerySchema, type DataSourceSummary } from './schemas';
import { useDatasourceList } from './queries';

const FILTER_FIELDS: FilterField[] = [
  { key: 'bkDataId', label: 'bk_data_id', type: 'number' },
  { key: 'dataName', label: 'data_name', type: 'text' },
  { key: 'tableId', label: 'table_id', type: 'text' },
  {
    key: 'sourceLabel',
    label: 'source_label',
    type: 'combobox',
    suggestions: SOURCE_LABEL_COMMON,
    placeholder: '输入或选择',
    advanced: true
  },
  {
    key: 'typeLabel',
    label: 'type_label',
    type: 'combobox',
    suggestions: TYPE_LABEL_COMMON,
    placeholder: '输入或选择',
    advanced: true
  },
  {
    key: 'createdFrom',
    label: 'created_from',
    type: 'select',
    options: CREATED_FROM_OPTIONS,
    advanced: true
  },
  { key: 'mqClusterId', label: 'mq_cluster_id', type: 'number', advanced: true },
  { key: 'spaceUid', label: 'space_uid', type: 'text', advanced: true },
  { key: 'isEnable', label: 'is_enable', type: 'boolean', advanced: true },
  { key: 'isCustomSource', label: 'is_custom_source', type: 'boolean', advanced: true },
  { key: 'isPlatformDataId', label: 'is_platform_data_id', type: 'boolean', advanced: true }
];

export function DataSourceListPage() {
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const search = useSearch({ strict: false });
  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);
  const returnTarget = getOptionalStoredReturnTarget(currentHref);

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const returnSearch = {
    env: currentEnvironment?.id ?? 'local',
    tenant: currentTenantId
  } satisfies Record<string, unknown>;

  const query = datasourceListQuerySchema.parse({
    bkTenantId: currentTenantId,
    bkDataId: activeFilters.bkDataId || undefined,
    dataName: activeFilters.dataName || undefined,
    tableId: activeFilters.tableId || undefined,
    sourceLabel: activeFilters.sourceLabel || undefined,
    typeLabel: activeFilters.typeLabel || undefined,
    createdFrom: activeFilters.createdFrom || undefined,
    spaceUid: activeFilters.spaceUid || undefined,
    mqClusterId: activeFilters.mqClusterId || undefined,
    isEnable: activeFilters.isEnable ? activeFilters.isEnable === 'true' : undefined,
    isCustomSource: activeFilters.isCustomSource
      ? activeFilters.isCustomSource === 'true'
      : undefined,
    isPlatformDataId: activeFilters.isPlatformDataId
      ? activeFilters.isPlatformDataId === 'true'
      : undefined,
    page,
    pageSize
  });
  const datasourceQuery = useDatasourceList(currentEnvironment!, query);
  const columns = useMemo<Array<ColumnDef<DataSourceSummary>>>(
    () => [
      {
        header: 'bk_data_id',
        cell: ({ row }) => {
          const datasource = row.original;
          const detailHref = createScopedHref(
            `/datasources/${String(datasource.bk_data_id)}`,
            returnSearch
          );

          return (
            <Link
              to="/datasources/$bkDataId"
              params={{
                bkDataId: String(datasource.bk_data_id)
              }}
              search={routeSearch}
              onClick={() =>
                rememberReturnTarget(detailHref, {
                  href: currentHref,
                  label: 'DataSource 列表'
                })
              }
              className="link"
            >
              {datasource.bk_data_id}
            </Link>
          );
        }
      },
      { header: '名称', accessorKey: 'data_name' },
      { header: '租户', accessorKey: 'bk_tenant_id' },
      {
        header: '类型',
        cell: ({ row }) => (
          <div className="badge-row">
            <Badge>{row.original.type_label}</Badge>
            <Badge tone="muted">{row.original.source_label}</Badge>
          </div>
        )
      },
      { header: '来源', accessorKey: 'created_from' },
      {
        header: 'Kafka 集群',
        cell: ({ row }) => {
          const datasource = row.original;
          const cluster = datasource.kafka_cluster;
          const clusterId = cluster?.cluster_id ?? datasource.mq_cluster_id;
          const clusterName = cluster ? getKafkaClusterName(cluster) : null;

          if (!clusterId) {
            return <span className="muted-text">-</span>;
          }

          const clusterHref = createScopedHref(`/clusters/${String(clusterId)}`, returnSearch);

          return (
            <Link
              to="/clusters/$clusterId"
              params={{ clusterId: String(clusterId) }}
              search={routeSearch}
              onClick={() =>
                rememberReturnTarget(clusterHref, {
                  href: currentHref,
                  label: 'DataSource 列表'
                })
              }
              className="link"
            >
              {clusterName || `#${clusterId}`}
            </Link>
          );
        }
      },
      {
        header: '启用',
        cell: ({ row }) => (
          <Badge tone={row.original.is_enable ? 'success' : 'danger'}>
            {formatBoolean(row.original.is_enable)}
          </Badge>
        )
      },
      { header: '空间', accessorKey: 'space_uid' },
      { header: 'RT 数', accessorKey: 'result_table_count' },
      {
        header: '更新时间',
        cell: ({ row }) => formatDateTime(row.original.last_modify_time)
      }
    ],
    [currentHref, returnSearch, routeSearch]
  );

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Resource</div>
          <h2>DataSource</h2>
        </div>
        {returnTarget ? (
          <Button asChild variant="secondary">
            <a href={returnTarget.href}>返回 {returnTarget.label}</a>
          </Button>
        ) : null}
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
        loading={datasourceQuery.isLoading}
      />
      {datasourceQuery.isError ? (
        <PageState title="加载失败" description={String(datasourceQuery.error)} />
      ) : datasourceQuery.isLoading ? (
        <PageState title="正在加载 DataSource..." />
      ) : (
        <>
          <DataTable data={datasourceQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={datasourceQuery.data?.total ?? 0}
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

function getKafkaClusterName(cluster: NonNullable<DataSourceSummary['kafka_cluster']>) {
  return cluster.display_name || cluster.cluster_name || `#${cluster.cluster_id}`;
}

function createScopedHref(pathname: string, search: Record<string, unknown>) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(search)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      params.set(key, String(value));
    }
  }

  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function getInitialFilters(search: object): Record<string, FilterValue> {
  return {
    ...getStringSearchFilter(search, 'bkDataId'),
    ...getStringSearchFilter(search, 'dataName'),
    ...getStringSearchFilter(search, 'tableId'),
    ...getStringSearchFilter(search, 'sourceLabel'),
    ...getStringSearchFilter(search, 'typeLabel'),
    ...getStringSearchFilter(search, 'createdFrom'),
    ...getStringSearchFilter(search, 'mqClusterId'),
    ...getStringSearchFilter(search, 'spaceUid')
  };
}

function getStringSearchFilter(search: object, key: string): Record<string, string> {
  if (!(key in search)) {
    return {};
  }

  const value = search[key as keyof typeof search];
  if (typeof value === 'string' && value) {
    return { [key]: value };
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return { [key]: String(value) };
  }
  return {};
}
