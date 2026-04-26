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
import { DEFAULT_STORAGE_OPTIONS, LABEL_COMMON, SCHEMA_TYPE_OPTIONS } from './constants';
import { resultTableListQuerySchema, type ResultTableSummary } from './schemas';
import { useResultTableList } from './queries';

const FILTER_FIELDS: FilterField[] = [
  { key: 'tableId', label: 'table_id', type: 'text' },
  { key: 'tableNameZh', label: 'table_name_zh', type: 'text' },
  { key: 'bkDataId', label: 'bk_data_id', type: 'number' },
  { key: 'dataLabel', label: 'data_label', type: 'text' },
  { key: 'bkBizId', label: 'bk_biz_id', type: 'number', advanced: true },
  {
    key: 'label',
    label: 'label',
    type: 'combobox',
    suggestions: LABEL_COMMON,
    placeholder: '输入或选择',
    advanced: true
  },
  {
    key: 'schemaType',
    label: 'schema_type',
    type: 'select',
    options: SCHEMA_TYPE_OPTIONS,
    advanced: true
  },
  {
    key: 'defaultStorage',
    label: 'default_storage',
    type: 'select',
    options: DEFAULT_STORAGE_OPTIONS,
    advanced: true
  },
  { key: 'isEnable', label: 'is_enable', type: 'boolean', advanced: true },
  { key: 'isDeleted', label: 'is_deleted', type: 'boolean', advanced: true },
  { key: 'isBuiltin', label: 'is_builtin', type: 'boolean', advanced: true }
];

export function ResultTableListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const search = useSearch({ strict: false });
  const navigate = useNavigate();
  const initialFilters = useMemo(() => getInitialFilters(search), [search]);
  const [drafts, setDrafts] = useState<Record<string, FilterValue>>(initialFilters);
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>(initialFilters);

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const query = resultTableListQuerySchema.parse({
    bkTenantId: currentTenantId,
    tableId: activeFilters.tableId || undefined,
    tableNameZh: activeFilters.tableNameZh || undefined,
    bkDataId: activeFilters.bkDataId || undefined,
    dataLabel: activeFilters.dataLabel || undefined,
    bkBizId: activeFilters.bkBizId || undefined,
    label: activeFilters.label || undefined,
    schemaType: activeFilters.schemaType || undefined,
    defaultStorage: activeFilters.defaultStorage || undefined,
    isEnable: activeFilters.isEnable ? activeFilters.isEnable === 'true' : undefined,
    isDeleted: activeFilters.isDeleted ? activeFilters.isDeleted === 'true' : undefined,
    isBuiltin: activeFilters.isBuiltin ? activeFilters.isBuiltin === 'true' : undefined,
    page,
    pageSize
  });
  const resultTableQuery = useResultTableList(currentEnvironment!, query);
  const columns = useMemo<Array<ColumnDef<ResultTableSummary>>>(
    () => [
      {
        header: 'table_id',
        size: 240,
        cell: ({ row }) => {
          const resultTable = row.original;
          return (
            <Link
              to="/result-tables/$tableId"
              params={{
                tableId: resultTable.table_id
              }}
              search={routeSearch}
              className="link inline-block"
            >
              <Truncated text={resultTable.table_id} maxW="240px" />
            </Link>
          );
        }
      },
      {
        header: '中文名',
        size: 180,
        cell: ({ row }) => {
          const v = row.original.table_name_zh;
          if (v == null || v === '') return <span className="muted-text whitespace-nowrap">-</span>;
          return <Truncated text={v} maxW="180px" />;
        }
      },
      { header: '业务', accessorKey: 'bk_biz_id', size: 70 },
      {
        header: 'label',
        size: 150,
        cell: ({ row }) => {
          const v = row.original.label;
          if (v == null || v === '') return <span className="muted-text whitespace-nowrap">-</span>;
          return <Truncated text={v} maxW="120px" />;
        }
      },
      {
        header: 'data_label',
        size: 170,
        cell: ({ row }) => {
          const v = row.original.data_label;
          if (v == null || v === '') return <span className="muted-text whitespace-nowrap">-</span>;
          return <Truncated text={v} maxW="170px" />;
        }
      },
      {
        header: '存储',
        size: 130,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            <Badge>{row.original.default_storage ?? '-'}</Badge>
          </span>
        )
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
        header: '删除',
        size: 70,
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            <Badge tone={row.original.is_deleted ? 'danger' : 'muted'}>
              {row.original.is_deleted ? '是' : '否'}
            </Badge>
          </span>
        )
      },
      {
        header: '字段数',
        size: 90,
        cell: ({ row }) => <span className="whitespace-nowrap">{row.original.field_count}</span>
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
      to: '/result-tables',
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
      to: '/result-tables',
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
          <h2>ResultTable</h2>
        </div>

      </div>
      <FilterToolbar
        fields={FILTER_FIELDS}
        values={drafts}
        onChange={(key, value) => setDrafts((prev) => ({ ...prev, [key]: value }))}
        onSearch={handleSearch}
        onReset={handleReset}
        loading={resultTableQuery.isLoading}
      />
      {resultTableQuery.isError ? (
        <PageState title="加载失败" description={String(resultTableQuery.error)} />
      ) : resultTableQuery.isLoading ? (
        <PageState title="正在加载 ResultTable..." />
      ) : (
        <>
          <DataTable data={resultTableQuery.data?.items ?? []} columns={columns} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={resultTableQuery.data?.total ?? 0}
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

function getInitialFilters(search: object): Record<string, FilterValue> {
  const filterKeys = [
    'tableId',
    'tableNameZh',
    'bkDataId',
    'dataLabel',
    'bkBizId',
    'label',
    'schemaType',
    'defaultStorage',
    'isEnable',
    'isDeleted',
    'isBuiltin'
  ];
  const filters: Record<string, FilterValue> = {};
  for (const key of filterKeys) {
    const value = getSearchString(search, key);
    if (value) {
      filters[key] = value;
    }
  }
  return filters;
}

function getSearchString(search: object, key: string): string | undefined {
  if (!(key in search)) return undefined;
  const value = (search as Record<string, unknown>)[key];
  return typeof value === 'string' ? value : undefined;
}

