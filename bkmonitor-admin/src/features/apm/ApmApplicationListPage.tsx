import { Link, useNavigate, useSearch } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { useCallback, useMemo, useState } from 'react';

import {
  FilterToolbar,
  type FilterField,
  type FilterValue
} from '../../shared/components/FilterToolbar';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
import { Truncated } from '../../shared/components/Truncated';
import { Badge } from '../../shared/components/Badge';
import { DataTable } from '../../shared/table/DataTable';
import { formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { APM_STATUS_OPTIONS } from './constants';
import { useApmApplicationList } from './queries';
import { apmApplicationListQuerySchema, type ApmApplicationSummary } from './schemas';

const FILTER_FIELDS: FilterField[] = [
  { key: 'bkBizId', label: 'bk_biz_id', type: 'number' },
  { key: 'appName', label: 'app_name', type: 'text' },
  {
    key: 'status',
    label: 'status',
    type: 'combobox',
    options: [...APM_STATUS_OPTIONS],
    advanced: true
  },
  { key: 'bkDataId', label: 'bk_data_id', type: 'number', advanced: true },
  { key: 'tableId', label: 'table_id', type: 'text', advanced: true }
];

export function ApmApplicationListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const search = useSearch({ strict: false });
  const navigate = useNavigate();
  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const query = apmApplicationListQuerySchema.parse({
    bkTenantId: currentTenantId,
    bkBizId: activeFilters.bkBizId || undefined,
    appName: activeFilters.appName || undefined,
    status: activeFilters.status || undefined,
    bkDataId: activeFilters.bkDataId || undefined,
    tableId: activeFilters.tableId || undefined,
    page,
    pageSize
  });
  const appQuery = useApmApplicationList(currentEnvironment!, query);

  const columns = useMemo<Array<ColumnDef<ApmApplicationSummary>>>(
    () => [
      {
        header: 'application_id',
        size: 120,
        cell: ({ row }) => (
          <Link
            to="/apm/applications/$applicationId"
            params={{ applicationId: String(row.original.application_id) }}
            search={routeSearch}
            className="link whitespace-nowrap"
          >
            {row.original.application_id}
          </Link>
        )
      },
      {
        header: '应用',
        size: 220,
        cell: ({ row }) => (
          <div className="grid gap-1">
            <Truncated text={row.original.app_name} maxW="220px" />
            {row.original.app_alias ? (
              <span className="muted-text">{row.original.app_alias}</span>
            ) : null}
          </div>
        )
      },
      { header: '业务', accessorKey: 'bk_biz_id', size: 80 },
      {
        header: 'status',
        size: 100,
        cell: ({ row }) => <Badge>{row.original.status ?? '-'}</Badge>
      },
      {
        header: 'DataID',
        size: 260,
        cell: ({ row }) => (
          <div className="badge-row">
            <DataIdLink label="metric" value={row.original.metric_data_id} search={routeSearch} />
            <DataIdLink label="trace" value={row.original.trace_data_id} search={routeSearch} />
            <DataIdLink label="log" value={row.original.log_data_id} search={routeSearch} />
          </div>
        )
      },
      {
        header: 'Service',
        size: 90,
        cell: ({ row }) => <span className="whitespace-nowrap">{row.original.service_count}</span>
      },
      {
        header: 'Topo',
        size: 90,
        cell: ({ row }) => <span className="whitespace-nowrap">{row.original.topo_node_count}</span>
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
      to: '/apm/applications',
      search: {
        env: getSearchValue(search, 'env'),
        tenant: getSearchValue(search, 'tenant'),
        ...Object.fromEntries(
          Object.entries(nextFilters).filter(([, value]) => value !== '' && value !== undefined)
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
      to: '/apm/applications',
      search: {
        env: getSearchValue(search, 'env'),
        tenant: getSearchValue(search, 'tenant')
      },
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
          <h2>APM</h2>
        </div>
      </div>
      <FilterToolbar
        fields={FILTER_FIELDS}
        values={drafts}
        onChange={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
        onSearch={handleSearch}
        onReset={handleReset}
        loading={appQuery.isLoading}
      />
      {appQuery.isError ? (
        <PageState title="加载失败" description={String(appQuery.error)} />
      ) : appQuery.isLoading ? (
        <PageState title="正在加载 APM 应用..." />
      ) : (
        <>
          <DataTable data={appQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={appQuery.data?.total ?? 0}
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

function DataIdLink({
  label,
  value,
  search
}: {
  label: string;
  value: number | null | undefined;
  search: Record<string, string>;
}) {
  if (!value) return null;
  return (
    <Link
      to="/datasources/$bkDataId"
      params={{ bkDataId: String(value) }}
      search={search}
      className="link"
    >
      <Badge tone="muted">
        {label}: {value}
      </Badge>
    </Link>
  );
}

function getInitialFilters(search: object): Record<string, FilterValue> {
  return {
    ...getStringSearchFilter(search, 'bkBizId'),
    ...getStringSearchFilter(search, 'appName'),
    ...getStringSearchFilter(search, 'status'),
    ...getStringSearchFilter(search, 'bkDataId'),
    ...getStringSearchFilter(search, 'tableId')
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

function getSearchValue(search: object, key: string): string {
  if (!(key in search)) {
    return '';
  }

  const value = search[key as keyof typeof search];
  return typeof value === 'string' ? value : '';
}
