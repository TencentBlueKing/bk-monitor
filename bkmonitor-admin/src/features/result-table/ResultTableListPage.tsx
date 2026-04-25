import { Link } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { FilterToolbar, type FilterField } from '../../shared/components/FilterToolbar';
import { PageState } from '../../shared/components/PageState';
import { Pagination } from '../../shared/components/Pagination';
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

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});

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
        cell: ({ row }) => (
          <Link
            to="/result-tables/$tableId"
            params={{
              tableId: row.original.table_id
            }}
            search={routeSearch}
            className="link"
          >
            {row.original.table_id}
          </Link>
        )
      },
      { header: '中文名', accessorKey: 'table_name_zh' },
      { header: '租户', accessorKey: 'bk_tenant_id' },
      { header: '业务', accessorKey: 'bk_biz_id' },
      { header: 'label', accessorKey: 'label' },
      { header: 'data_label', accessorKey: 'data_label' },
      {
        header: '存储',
        cell: ({ row }) => <Badge>{row.original.default_storage ?? '-'}</Badge>
      },
      {
        header: '启用',
        cell: ({ row }) => (
          <Badge tone={row.original.is_enable ? 'success' : 'danger'}>
            {formatBoolean(row.original.is_enable)}
          </Badge>
        )
      },
      {
        header: '删除',
        cell: ({ row }) => (
          <Badge tone={row.original.is_deleted ? 'danger' : 'muted'}>
            {row.original.is_deleted ? '是' : '否'}
          </Badge>
        )
      },
      { header: '字段数', accessorKey: 'field_count' },
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
          <h2>ResultTable</h2>
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
