import { Link, useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { useCallback, useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import {
  FilterToolbar,
  type FilterField,
  type FilterValue
} from '../../shared/components/FilterToolbar';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { Truncated } from '../../shared/components/Truncated';
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
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const search = useSearch({ strict: false });
  const navigate = useNavigate();
  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

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
        size: 80,
        cell: ({ row }) => {
          const datasource = row.original;

          return (
            <Link
              to="/datasources/$bkDataId"
              params={{
                bkDataId: String(datasource.bk_data_id)
              }}
              search={routeSearch}
              className="link whitespace-nowrap"
            >
              {datasource.bk_data_id}
            </Link>
          );
        }
      },
      {
        header: '名称',
        size: 200,
        cell: ({ row }) => <Truncated text={row.original.data_name} maxW="200px" />
      },
      {
        header: '类型',
        size: 150,
        cell: ({ row }) => (
          <div className="badge-row whitespace-nowrap">
            <Badge>{row.original.type_label}</Badge>
            <Badge tone="muted">{row.original.source_label}</Badge>
          </div>
        )
      },
      { header: '来源', accessorKey: 'created_from', size: 100 },
      {
        header: 'Kafka 集群',
        size: 150,
        cell: ({ row }) => {
          const datasource = row.original;
          const cluster = datasource.kafka_cluster;
          const clusterId = cluster?.cluster_id ?? datasource.mq_cluster_id;
          const clusterName = cluster ? getKafkaClusterName(cluster) : null;

          if (!clusterId) {
            return <span className="muted-text whitespace-nowrap">-</span>;
          }

          const label = clusterName || `#${clusterId}`;

          return (
            <Link
              to="/clusters/$clusterId"
              params={{ clusterId: String(clusterId) }}
              search={routeSearch}
              className="link inline-block"
            >
              <Truncated text={label} maxW="140px" />
            </Link>
          );
        }
      },
      {
        header: '启用',
        size: 70,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            <Badge tone={row.original.is_enable ? 'success' : 'danger'}>
              {formatBoolean(row.original.is_enable)}
            </Badge>
          </span>
        )
      },
      {
        header: '空间',
        size: 120,
        cell: ({ row }) => {
          const v = row.original.space_uid;
          if (v == null) return <span className="muted-text whitespace-nowrap">-</span>;
          return <Truncated text={v} maxW="120px" />;
        }
      },
      {
        header: 'RT 数',
        size: 70,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">{row.original.result_table_count}</span>
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
    [routeSearch]
  );

  const handleSearch = useCallback(() => {
    const nextFilters = { ...drafts };
    setActiveFilters(nextFilters);
    setPage(1);
    void navigate({
      to: '/datasources',
      search: {
        env: (search as any)?.env ?? '',
        tenant: (search as any)?.tenant ?? '',
        ...Object.fromEntries(
          Object.entries(nextFilters).filter(([, v]) => v !== '' && v !== undefined && (!Array.isArray(v) || v.length > 0))
        )
      },
      replace: true
    });
  }, [drafts, navigate, search]);

  const handleReset = useCallback(() => {
    setDrafts({});
    setActiveFilters({});
    setPage(1);
    void navigate({
      to: '/datasources',
      search: { env: (search as any)?.env ?? '', tenant: (search as any)?.tenant ?? '' },
      replace: true
    });
  }, [navigate, search]);

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
      </div>
      <FilterToolbar
        fields={FILTER_FIELDS}
        values={drafts}
        onChange={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
        onSearch={handleSearch}
        onReset={handleReset}
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
