import { Link, useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { useCallback, useEffect, useMemo, useState } from 'react';

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
import { formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import {
  DATA_LINK_KIND_TABS,
  CLUSTER_CONFIG_KIND_OPTIONS,
  DATA_LINK_STRATEGY_OPTIONS,
  NAMESPACE_OPTIONS
} from './constants';
import { useClusterConfigList, useComponentList, useDataLinkList } from './queries';
import type {
  ClusterConfigListItem,
  ComponentListItem,
  ComponentListQuery,
  ClusterConfigListQuery,
  DataLinkListItem
} from './schemas';

function getSearchString(search: object, key: string): string | undefined {
  if (!(key in search)) return undefined;
  const value = (search as Record<string, unknown>)[key];
  return typeof value === 'string' ? value : undefined;
}

function getEnvFromSearch(search: object): string {
  return getSearchString(search, 'env') ?? '';
}

function getTenantFromSearch(search: object): string {
  return getSearchString(search, 'tenant') ?? '';
}

function getKindFromSearch(search: object): string {
  return getSearchString(search, 'kind') ?? 'DataLink';
}

function getStringFilter(value: FilterValue | undefined): string | undefined {
  if (typeof value === 'string' && value) {
    return value;
  }
  return undefined;
}

function getNumberFilter(value: FilterValue | undefined): number | undefined {
  const s = getStringFilter(value);
  if (s) {
    const num = Number(s);
    if (Number.isFinite(num)) return num;
  }
  return undefined;
}

function getBooleanFilter(value: FilterValue | undefined): boolean | undefined {
  const s = getStringFilter(value);
  if (s === 'true') return true;
  if (s === 'false') return false;
  return undefined;
}

function getInitialFilters(search: object): Record<string, FilterValue> {
  const filters: Record<string, FilterValue> = {};
  const filterKeys = [
    'namespace',
    'search',
    'status',
    'bk_data_id',
    'data_type',
    'vmClusterName',
    'esClusterName',
    'dorisClusterName',
    'hasDataLink',
    'dataLinkStrategy',
    'clusterKind'
  ];

  for (const key of filterKeys) {
    const value = getSearchString(search, key);
    if (value) {
      filters[key] = value;
    }
  }

  return filters;
}

export function DataLinkListPage() {
  const navigate = useNavigate();
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const search = useSearch({ strict: false });
  const [activeKind, setActiveKind] = useState<string>(() => getKindFromSearch(search));

  useEffect(() => {
    const urlKind = getSearchString(search, 'kind');
    if (urlKind) {
      setActiveKind(urlKind);
    }
  }, [search]);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);

  useEffect(() => {
    const initFilters = getInitialFilters(search);
    setDrafts(initFilters);
    setActiveFilters(initFilters);
    setPage(1);
  }, [activeKind, search]);

  const handleTabChange = useCallback(
    (kind: string) => {
      setActiveKind(kind);
      void navigate({
        to: '/data-links',
        search: {
          env: getEnvFromSearch(search),
          tenant: getTenantFromSearch(search),
          kind
        }
      });
    },
    [navigate, search]
  );

  const filterFields = useMemo<FilterField[]>(() => {
    if (activeKind === 'DataLink') {
      return [
        {
          key: 'namespace',
          label: 'namespace',
          type: 'combobox',
          options: NAMESPACE_OPTIONS.map((o) => ({ ...o })),
          placeholder: '输入或选择'
        },
        { key: 'search', label: 'search', type: 'text' },
        {
          key: 'dataLinkStrategy',
          label: '策略',
          type: 'select',
          options: DATA_LINK_STRATEGY_OPTIONS.map((o) => ({ ...o }))
        },
        { key: 'bk_data_id', label: 'bk_data_id', type: 'number' }
      ];
    }

    if (activeKind === 'ClusterConfig') {
      return [
        {
          key: 'namespace',
          label: 'namespace',
          type: 'combobox',
          options: NAMESPACE_OPTIONS.map((o) => ({ ...o })),
          placeholder: '输入或选择'
        },
        { key: 'search', label: 'search', type: 'text' },
        {
          key: 'clusterKind',
          label: 'kind',
          type: 'select',
          options: CLUSTER_CONFIG_KIND_OPTIONS.map((o) => ({ ...o }))
        }
      ];
    }

    const fields: FilterField[] = [
      {
        key: 'namespace',
        label: 'namespace',
        type: 'combobox',
        options: NAMESPACE_OPTIONS.map((o) => ({ ...o })),
        placeholder: '输入或选择'
      },
      { key: 'search', label: 'search', type: 'text' }
    ];

    if (activeKind === 'DataId' || activeKind === 'Databus') {
      fields.push({ key: 'bk_data_id', label: 'bk_data_id', type: 'number' });
    }

    if (activeKind === 'ResultTable') {
      fields.push({ key: 'data_type', label: 'data_type', type: 'text' });
    }

    if (activeKind === 'VmStorageBinding') {
      fields.push({ key: 'vmClusterName', label: 'vm_cluster_name', type: 'text' });
    }

    if (activeKind === 'ElasticSearchBinding') {
      fields.push({ key: 'esClusterName', label: 'es_cluster_name', type: 'text' });
    }

    if (activeKind === 'DorisBinding') {
      fields.push({ key: 'dorisClusterName', label: 'doris_cluster_name', type: 'text' });
    }

    fields.push({ key: 'status', label: 'status', type: 'text' });

    if (activeKind !== 'DataId' && activeKind !== 'DataLink') {
      fields.push({
        key: 'hasDataLink',
        label: 'has_data_link',
        type: 'boolean'
      });
    }

    return fields;
  }, [activeKind]);

  const componentKind = (
    ['DataLink', 'ClusterConfig'].includes(activeKind) ? 'DataId' : activeKind
  ) as ComponentListQuery['kind'];

  const componentQuery = useComponentList(currentEnvironment!, {
    bkTenantId: currentTenantId,
    kind: componentKind,
    namespace: getStringFilter(activeFilters.namespace),
    search: getStringFilter(activeFilters.search),
    status: getStringFilter(activeFilters.status),
    bkDataId: getNumberFilter(activeFilters.bkDataId),
    dataType: getStringFilter(activeFilters.dataType),
    vmClusterName: getStringFilter(activeFilters.vmClusterName),
    esClusterName: getStringFilter(activeFilters.esClusterName),
    dorisClusterName: getStringFilter(activeFilters.dorisClusterName),
    hasDataLink: getBooleanFilter(activeFilters.hasDataLink),
    page,
    pageSize
  });

  const clusterConfigQuery = useClusterConfigList(currentEnvironment!, {
    bkTenantId: currentTenantId,
    kind: (getStringFilter(activeFilters.clusterKind) ??
      undefined) as ClusterConfigListQuery['kind'],
    namespace: getStringFilter(activeFilters.namespace),
    search: getStringFilter(activeFilters.search),
    page,
    pageSize
  });

  const datalinkQuery = useDataLinkList(currentEnvironment!, {
    bkTenantId: currentTenantId,
    namespace: getStringFilter(activeFilters.namespace),
    search: getStringFilter(activeFilters.search),
    dataLinkStrategy: getStringFilter(activeFilters.dataLinkStrategy),
    bkDataId: getNumberFilter(activeFilters.bkDataId),
    page,
    pageSize
  });

  const isLoading =
    (activeKind !== 'ClusterConfig' && activeKind !== 'DataLink' && componentQuery.isLoading) ||
    (activeKind === 'ClusterConfig' && clusterConfigQuery.isLoading) ||
    (activeKind === 'DataLink' && datalinkQuery.isLoading);

  const isError =
    (activeKind !== 'ClusterConfig' && activeKind !== 'DataLink' && componentQuery.isError) ||
    (activeKind === 'ClusterConfig' && clusterConfigQuery.isError) ||
    (activeKind === 'DataLink' && datalinkQuery.isError);

  const errorMessage: string =
    activeKind !== 'ClusterConfig' && activeKind !== 'DataLink'
      ? String(componentQuery.error ?? '')
      : activeKind === 'ClusterConfig'
        ? String(clusterConfigQuery.error ?? '')
        : String(datalinkQuery.error ?? '');

  const items =
    (activeKind !== 'ClusterConfig' && activeKind !== 'DataLink'
      ? componentQuery.data?.items
      : activeKind === 'ClusterConfig'
        ? clusterConfigQuery.data?.items
        : datalinkQuery.data?.items) ?? [];

  const total =
    (activeKind !== 'ClusterConfig' && activeKind !== 'DataLink'
      ? componentQuery.data?.total
      : activeKind === 'ClusterConfig'
        ? clusterConfigQuery.data?.total
        : datalinkQuery.data?.total) ?? 0;

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const dataLinkColumns = useMemo<Array<ColumnDef<DataLinkListItem>>>(
    () => [
      {
        header: 'dataLinkName',
        size: 200,
        cell: ({ row }) => {
          const item = row.original;
          return (
            <Link
              to="/data-links/detail"
              search={{
                ...routeSearch,
                kind: 'DataLink',
                dataLinkName: item.data_link_name
              }}
              className="link whitespace-nowrap"
            >
              <Truncated text={item.data_link_name} maxW="200px" />
            </Link>
          );
        }
      },
      {
        header: 'namespace',
        size: 120,
        cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
      },
      {
        header: '策略',
        size: 200,
        cell: ({ row }) => <Truncated text={row.original.data_link_strategy} maxW="200px" />
      },
      { header: 'bk_data_id', accessorKey: 'bk_data_id' as const, size: 100 },
      { header: 'table_ids 数', accessorKey: 'table_ids_count' as const, size: 100 },
      {
        header: 'createdAt',
        size: 160,
        cell: ({ row }) => formatDateTime(row.original.created_at)
      }
    ],
    [routeSearch]
  );

  const componentColumns = useMemo<Array<ColumnDef<ComponentListItem>>>(() => {
    const commonCols: Array<ColumnDef<ComponentListItem>> = [
      {
        header: 'name',
        size: 200,
        cell: ({ row }) => {
          const item = row.original;
          return (
            <Link
              to="/data-links/detail"
              search={{
                ...routeSearch,
                kind: activeKind,
                namespace: item.namespace,
                name: item.name
              }}
              className="link whitespace-nowrap"
            >
              <Truncated text={item.name} maxW="200px" />
            </Link>
          );
        }
      }
    ];

    if (activeKind === 'DataId') {
      commonCols.push(
        { header: 'bk_data_id', accessorKey: 'bk_data_id' as const, size: 100 },
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    } else if (activeKind === 'ResultTable') {
      commonCols.push(
        {
          header: 'tableId',
          size: 200,
          cell: ({ row }) => <Truncated text={row.original.table_id ?? '-'} maxW="200px" />
        },
        { header: 'data_type', accessorKey: 'data_type' as const, size: 80 },
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    } else if (activeKind === 'VmStorageBinding') {
      commonCols.push(
        {
          header: 'vmClusterName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.vm_cluster_name ?? '-'} maxW="150px" />
        },
        {
          header: 'bkbaseResultTableName',
          size: 200,
          cell: ({ row }) => (
            <Truncated text={row.original.bkbase_result_table_name ?? '-'} maxW="200px" />
          )
        },
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    } else if (activeKind === 'ElasticSearchBinding') {
      commonCols.push(
        {
          header: 'esClusterName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.es_cluster_name ?? '-'} maxW="150px" />
        },
        {
          header: 'bkbaseResultTableName',
          size: 200,
          cell: ({ row }) => (
            <Truncated text={row.original.bkbase_result_table_name ?? '-'} maxW="200px" />
          )
        },
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    } else if (activeKind === 'DorisBinding') {
      commonCols.push(
        {
          header: 'dorisClusterName',
          size: 150,
          cell: ({ row }) => (
            <Truncated text={row.original.doris_cluster_name ?? '-'} maxW="150px" />
          )
        },
        {
          header: 'bkbaseResultTableName',
          size: 200,
          cell: ({ row }) => (
            <Truncated text={row.original.bkbase_result_table_name ?? '-'} maxW="200px" />
          )
        },
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    } else if (activeKind === 'Databus') {
      commonCols.push(
        {
          header: 'dataIdName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_id_name ?? '-'} maxW="150px" />
        },
        { header: 'bk_data_id', accessorKey: 'bk_data_id' as const, size: 100 },
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    } else if (activeKind === 'ConditionalSink') {
      commonCols.push(
        {
          header: 'namespace',
          size: 120,
          cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
        },
        { header: 'status', accessorKey: 'status' as const, size: 80 },
        {
          header: 'dataLinkName',
          size: 150,
          cell: ({ row }) => <Truncated text={row.original.data_link_name ?? '-'} maxW="150px" />
        },
        {
          header: 'createdAt',
          size: 160,
          cell: ({ row }) => formatDateTime(row.original.created_at)
        }
      );
    }

    return commonCols;
  }, [activeKind, routeSearch]);

  const clusterConfigColumns = useMemo<Array<ColumnDef<ClusterConfigListItem>>>(
    () => [
      {
        header: 'name',
        size: 200,
        cell: ({ row }) => {
          const item = row.original;
          return (
            <Link
              to="/data-links/detail"
              search={{
                ...routeSearch,
                kind: 'ClusterConfig',
                clusterKind: item.kind,
                namespace: item.namespace,
                name: item.name
              }}
              className="link whitespace-nowrap"
            >
              <Truncated text={item.name} maxW="200px" />
            </Link>
          );
        }
      },
      { header: 'kind', size: 140, cell: ({ row }) => <Badge>{row.original.kind}</Badge> },
      {
        header: 'namespace',
        size: 120,
        cell: ({ row }) => <Truncated text={row.original.namespace} maxW="120px" />
      },
      {
        header: 'createdAt',
        size: 160,
        cell: ({ row }) => formatDateTime(row.original.created_at)
      },
      { header: 'updatedAt', size: 160, cell: ({ row }) => formatDateTime(row.original.updated_at) }
    ],
    [routeSearch]
  );

  const columns =
    activeKind === 'DataLink'
      ? dataLinkColumns
      : activeKind === 'ClusterConfig'
        ? clusterConfigColumns
        : componentColumns;

  const handleSearch = useCallback(() => {
    const nextFilters = { ...drafts };
    setActiveFilters(nextFilters);
    setPage(1);
    void navigate({
      to: '/data-links',
      search: {
        env: getEnvFromSearch(search),
        tenant: getTenantFromSearch(search),
        kind: activeKind,
        ...Object.fromEntries(
          Object.entries(nextFilters).filter(
            ([, v]) => v !== '' && v !== undefined && (!Array.isArray(v) || v.length > 0)
          )
        )
      },
      replace: true
    });
  }, [drafts, navigate, search, activeKind]);

  const handleReset = useCallback(() => {
    setDrafts({});
    setActiveFilters({});
    setPage(1);
    void navigate({
      to: '/data-links',
      search: {
        env: getEnvFromSearch(search),
        tenant: getTenantFromSearch(search),
        kind: activeKind
      },
      replace: true
    });
  }, [navigate, search, activeKind]);

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">DataLink</div>
          <h2>数据链路管理</h2>
        </div>
      </div>

      <div className="flex gap-1 mb-4 border-b">
        {DATA_LINK_KIND_TABS.map((tab) => (
          <button
            key={tab.kind}
            type="button"
            onClick={() => handleTabChange(tab.kind)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeKind === tab.kind
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30'
            }`}
          >
            <tab.icon size={16} aria-hidden="true" />
            {tab.label}
          </button>
        ))}
      </div>

      <FilterToolbar
        fields={filterFields}
        values={drafts}
        onChange={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
        onSearch={handleSearch}
        onReset={handleReset}
        loading={isLoading}
      />

      {isError ? (
        <PageState title="加载失败" description={errorMessage} />
      ) : isLoading ? (
        <PageState title="正在加载 DataLink..." />
      ) : (
        <>
          <DataTable data={items as never[]} columns={columns as never} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
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
