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
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { CUSTOM_REPORT_CREATED_FROM_OPTIONS, CUSTOM_REPORT_TYPE_TABS } from './constants';
import { useCustomReportList } from './queries';
import {
  customReportListQuerySchema,
  customReportTypeSchema,
  type CustomReportSummary
} from './schemas';

const FILTER_FIELDS: FilterField[] = [
  { key: 'bkBizId', label: 'bk_biz_id', type: 'number' },
  { key: 'groupName', label: 'group_name', type: 'text' },
  { key: 'bkDataId', label: 'bk_data_id', type: 'number', advanced: true },
  { key: 'tableId', label: 'table_id', type: 'text', advanced: true },
  {
    key: 'createdFrom',
    label: 'created_from',
    type: 'combobox',
    options: [...CUSTOM_REPORT_CREATED_FROM_OPTIONS],
    allowCustom: true,
    advanced: true
  } as FilterField,
  { key: 'hasApm', label: '关联 APM', type: 'boolean', advanced: true }
];

export function CustomReportListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const search = useSearch({ strict: false });
  const navigate = useNavigate();
  const [activeReportType, setActiveReportType] = useState(() => getReportTypeFromSearch(search));
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  useEffect(() => {
    setActiveReportType(getReportTypeFromSearch(search));
  }, [search]);

  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  useEffect(() => {
    const initFilters = getInitialFilters(search);
    setDrafts(initFilters);
    setActiveFilters(initFilters);
    setPage(1);
  }, [activeReportType, search]);

  const query = customReportListQuerySchema.parse({
    bkTenantId: currentTenantId,
    reportType: activeReportType,
    bkBizId: activeFilters.bkBizId || undefined,
    bkDataId: activeFilters.bkDataId || undefined,
    tableId: activeFilters.tableId || undefined,
    groupName: activeFilters.groupName || undefined,
    createdFrom: activeFilters.createdFrom || undefined,
    hasApm: activeFilters.hasApm ? activeFilters.hasApm === 'true' : undefined,
    page,
    pageSize
  });
  const reportQuery = useCustomReportList(currentEnvironment!, query);

  const columns = useMemo<Array<ColumnDef<CustomReportSummary>>>(
    () => [
      {
        header: 'group_id',
        size: 90,
        cell: ({ row }) => (
          <Link
            to="/custom-reports/$reportType/$groupId"
            params={{
              reportType: row.original.report_type,
              groupId: String(row.original.group_id)
            }}
            search={routeSearch}
            className="link whitespace-nowrap"
          >
            {row.original.group_id}
          </Link>
        )
      },
      {
        header: '名称',
        size: 220,
        cell: ({ row }) => <Truncated text={row.original.group_name} maxW="220px" />
      },
      {
        header: 'bk_data_id',
        size: 110,
        cell: ({ row }) =>
          row.original.bk_data_id ? (
            <Link
              to="/datasources/$bkDataId"
              params={{ bkDataId: String(row.original.bk_data_id) }}
              search={routeSearch}
              className="link whitespace-nowrap"
            >
              {row.original.bk_data_id}
            </Link>
          ) : (
            <span className="muted-text">-</span>
          )
      },
      {
        header: 'table_id',
        size: 220,
        cell: ({ row }) =>
          row.original.table_id ? (
            <Link
              to="/result-tables/$tableId"
              params={{ tableId: row.original.table_id }}
              search={routeSearch}
              className="link"
            >
              <Truncated text={row.original.table_id} maxW="220px" />
            </Link>
          ) : (
            <span className="muted-text">-</span>
          )
      },
      { header: '业务', accessorKey: 'bk_biz_id', size: 80 },
      {
        header: '启用',
        size: 70,
        cell: ({ row }) => (
          <Badge tone={row.original.is_enable ? 'success' : 'muted'}>
            {formatBoolean(row.original.is_enable)}
          </Badge>
        )
      },
      {
        header: '指标/字段',
        size: 100,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            {row.original.report_type === 'custom_metric'
              ? row.original.metric_count
              : row.original.field_count}
          </span>
        )
      },
      {
        header: '关联',
        size: 160,
        cell: ({ row }) => (
          <div className="badge-row">
            {row.original.monitor_web_source ? (
              <Badge tone="muted">{row.original.monitor_web_source}</Badge>
            ) : null}
            {row.original.apm_application_count > 0 ? (
              <Badge tone="success">APM {row.original.apm_application_count}</Badge>
            ) : null}
          </div>
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

  const handleTabChange = useCallback(
    (reportType: CustomReportSummary['report_type']) => {
      setActiveReportType(reportType);
      void navigate({
        to: '/custom-reports',
        search: {
          env: getSearchValue(search, 'env'),
          tenant: getSearchValue(search, 'tenant'),
          reportType
        }
      });
    },
    [navigate, search]
  );

  const handleSearch = useCallback(() => {
    const nextFilters = { ...drafts };
    setActiveFilters(nextFilters);
    setPage(1);
    void navigate({
      to: '/custom-reports',
      search: {
        env: getSearchValue(search, 'env'),
        tenant: getSearchValue(search, 'tenant'),
        reportType: activeReportType,
        ...Object.fromEntries(
          Object.entries(nextFilters).filter(([, value]) => value !== '' && value !== undefined)
        )
      },
      replace: true
    });
  }, [activeReportType, drafts, navigate, search]);

  const handleReset = useCallback(() => {
    setDrafts({});
    setActiveFilters({});
    setPage(1);
    void navigate({
      to: '/custom-reports',
      search: {
        env: getSearchValue(search, 'env'),
        tenant: getSearchValue(search, 'tenant'),
        reportType: activeReportType
      },
      replace: true
    });
  }, [activeReportType, navigate, search]);

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Resource</div>
          <h2>自定义上报</h2>
        </div>
      </div>

      <div className="mb-4 flex gap-1 border-b">
        {CUSTOM_REPORT_TYPE_TABS.map((tab) => (
          <button
            key={tab.reportType}
            type="button"
            onClick={() => handleTabChange(tab.reportType)}
            className={`inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              activeReportType === tab.reportType
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:border-muted-foreground/30 hover:text-foreground'
            }`}
          >
            <tab.icon size={16} aria-hidden="true" />
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      <FilterToolbar
        fields={FILTER_FIELDS}
        values={drafts}
        onChange={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
        onSearch={handleSearch}
        onReset={handleReset}
        loading={reportQuery.isLoading}
      />
      {reportQuery.isError ? (
        <PageState title="加载失败" description={String(reportQuery.error)} />
      ) : reportQuery.isLoading ? (
        <PageState title="正在加载自定义上报..." />
      ) : (
        <>
          <DataTable data={reportQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={reportQuery.data?.total ?? 0}
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

function getReportTypeFromSearch(search: object): CustomReportSummary['report_type'] {
  const value = getSearchValue(search, 'reportType');
  const parsed = customReportTypeSchema.safeParse(value);
  return parsed.success ? parsed.data : 'custom_metric';
}

function getInitialFilters(search: object): Record<string, FilterValue> {
  return {
    ...getStringSearchFilter(search, 'bkBizId'),
    ...getStringSearchFilter(search, 'groupName'),
    ...getStringSearchFilter(search, 'bkDataId'),
    ...getStringSearchFilter(search, 'tableId'),
    ...getStringSearchFilter(search, 'createdFrom'),
    ...getStringSearchFilter(search, 'hasApm')
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
