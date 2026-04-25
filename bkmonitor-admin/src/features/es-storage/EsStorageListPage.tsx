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
  buildHref,
  getOptionalStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean } from '../../shared/utils/format';
import { useClusterInfoList } from '../cluster-info/queries';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import {
  ES_STORAGE_TABLE_KIND_LABEL,
  ES_STORAGE_TABLE_KIND_OPTIONS,
  ES_STORAGE_TABLE_KIND_TONE
} from './constants';
import { useEsStorageList } from './queries';
import {
  esStorageListQuerySchema,
  type EsStorageSummary,
  type EsStorageTableKind
} from './schemas';

const BASE_FILTER_FIELDS: FilterField[] = [
  {
    key: 'tableId',
    label: '表 ID',
    type: 'text',
    placeholder: '匹配 table_id / origin_table_id'
  },
  {
    key: 'dataLabel',
    label: 'data_label',
    type: 'text',
    placeholder: '精确匹配 ResultTable.data_label'
  },
  {
    key: 'tableKind',
    label: '表类型',
    type: 'select',
    options: ES_STORAGE_TABLE_KIND_OPTIONS
  },
  { key: 'sourceType', label: 'source_type', type: 'text', advanced: true },
  { key: 'needCreateIndex', label: '需要创建索引', type: 'boolean', advanced: true }
];

export function EsStorageListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const search = useSearch({ strict: false });
  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const returnTarget = getOptionalStoredReturnTarget(currentHref);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const esClusterQuery = useClusterInfoList(currentEnvironment!, {
    bkTenantId: currentTenantId,
    clusterType: 'elasticsearch',
    include: [],
    page: 1,
    pageSize: 100
  });
  const filterFields = useMemo(
    () => [
      ...BASE_FILTER_FIELDS.slice(0, 3),
      {
        key: 'storageClusterId',
        label: 'ES 集群 ID',
        type: 'combobox' as const,
        placeholder: '输入集群 ID 或选择',
        options:
          esClusterQuery.data?.items.map((cluster) => ({
            value: String(cluster.cluster_id),
            label: `${cluster.cluster_id} - ${cluster.display_name || cluster.cluster_name}`
          })) ?? []
      },
      ...BASE_FILTER_FIELDS.slice(3)
    ],
    [esClusterQuery.data?.items]
  );

  const query = esStorageListQuerySchema.parse({
    bkTenantId: currentTenantId,
    tableId: activeFilters.tableId || undefined,
    dataLabel: activeFilters.dataLabel || undefined,
    tableKind: normalizeTableKind(activeFilters.tableKind),
    storageClusterId: activeFilters.storageClusterId || undefined,
    sourceType: activeFilters.sourceType || undefined,
    needCreateIndex: activeFilters.needCreateIndex
      ? activeFilters.needCreateIndex === 'true'
      : undefined,
    page,
    pageSize
  });
  const esStorageQuery = useEsStorageList(currentEnvironment!, query);

  const columns = useMemo<Array<ColumnDef<EsStorageSummary>>>(
    () => [
      {
        header: 'table_id',
        cell: ({ row }) => {
          const storage = row.original;
          const detailHref = buildHref(`/es-storages/${storage.table_id}`, routeSearch);

          return (
            <div className="grid gap-1">
              <Link
                to="/es-storages/$tableId"
                params={{ tableId: storage.table_id }}
                search={routeSearch}
                className="link"
                onClick={() =>
                  rememberReturnTarget(detailHref, {
                    href: currentHref,
                    label: 'ESStorage 列表'
                  })
                }
              >
                {storage.table_id}
              </Link>
            </div>
          );
        }
      },
      {
        header: '表类型',
        cell: ({ row }) => (
          <Badge tone={ES_STORAGE_TABLE_KIND_TONE[row.original.table_kind]}>
            {ES_STORAGE_TABLE_KIND_LABEL[row.original.table_kind]}
          </Badge>
        )
      },
      {
        header: 'origin_table_id',
        cell: ({ row }) => {
          const originTableId = row.original.origin_table_id;
          if (!originTableId) return <span className="muted-text">-</span>;

          return (
            <Link
              to="/es-storages/$tableId"
              params={{ tableId: originTableId }}
              search={routeSearch}
              className="link"
              onClick={() =>
                rememberReturnTarget(buildHref(`/es-storages/${originTableId}`, routeSearch), {
                  href: currentHref,
                  label: 'ESStorage 列表'
                })
              }
            >
              {originTableId}
            </Link>
          );
        }
      },
      {
        header: 'storage cluster',
        cell: ({ row }) => {
          const clusterId = row.original.storage_cluster_id;
          const cluster = row.original.storage_cluster;
          if (!clusterId) return <span className="muted-text">-</span>;

          return (
            <Link
              to="/clusters/$clusterId"
              params={{ clusterId: String(clusterId) }}
              search={routeSearch}
              className="link"
              onClick={() =>
                rememberReturnTarget(buildHref(`/clusters/${String(clusterId)}`, routeSearch), {
                  href: currentHref,
                  label: 'ESStorage 列表'
                })
              }
            >
              {cluster?.display_name || cluster?.cluster_name || `#${clusterId}`}
            </Link>
          );
        }
      },
      {
        header: 'retention',
        cell: ({ row }) => formatOptional(row.original.retention, '天')
      },
      {
        header: 'slice',
        cell: ({ row }) => (
          <span>
            size {formatOptional(row.original.slice_size)} / gap {formatOptional(row.original.slice_gap)}
          </span>
        )
      },
      {
        header: 'need_create_index',
        cell: ({ row }) => (
          <Badge tone={row.original.need_create_index ? 'success' : 'muted'}>
            {formatBoolean(row.original.need_create_index)}
          </Badge>
        )
      },
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
          <h2>ESStorage</h2>
        </div>
        {returnTarget ? (
          <Button asChild variant="secondary">
            <a href={returnTarget.href}>返回 {returnTarget.label}</a>
          </Button>
        ) : null}
      </div>
      <FilterToolbar
        fields={filterFields}
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
        loading={esStorageQuery.isLoading}
      />
      {esStorageQuery.isError ? (
        <PageState title="加载失败" description={String(esStorageQuery.error)} />
      ) : esStorageQuery.isLoading ? (
        <PageState title="正在加载 ESStorage..." />
      ) : (
        <>
          <DataTable data={esStorageQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={esStorageQuery.data?.total ?? 0}
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

function normalizeTableKind(value: FilterValue | undefined): EsStorageTableKind | undefined {
  return value === 'physical' || value === 'virtual' ? value : undefined;
}

function formatOptional(value: string | number | null | undefined, suffix = '') {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return `${String(value)}${suffix}`;
}

function getInitialFilters(search: object): Record<string, FilterValue> {
  return {
    ...getStringSearchFilter(search, 'tableId'),
    ...getStringSearchFilter(search, 'dataLabel'),
    ...getStringSearchFilter(search, 'tableKind'),
    ...getStringSearchFilter(search, 'storageClusterId'),
    ...getStringSearchFilter(search, 'sourceType'),
    ...getStringSearchFilter(search, 'needCreateIndex')
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
  if (typeof value === 'boolean') {
    return { [key]: String(value) };
  }
  return {};
}
