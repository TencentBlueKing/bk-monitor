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
import { Button } from '../../shared/components/ui/button';
import {
  getOptionalStoredReturnTarget,
  rememberReturnTarget
} from '../../shared/navigation/returnTarget';
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
  const currentHref = useLocation({ select: (location) => String(location.href) });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const [drafts, setDrafts] = useState<Record<string, FilterValue>>({});
  const [activeFilters, setActiveFilters] = useState<Record<string, FilterValue>>({});
  const returnTarget = getOptionalStoredReturnTarget(currentHref);

  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const returnSearch = {
    env: currentEnvironment?.id ?? 'local',
    tenant: currentTenantId
  } satisfies Record<string, unknown>;

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
        cell: ({ row }) => {
          const resultTable = row.original;
          const detailHref = createScopedHref(
            `/result-tables/${resultTable.table_id}`,
            returnSearch
          );

          return (
            <Link
              to="/result-tables/$tableId"
              params={{
                tableId: resultTable.table_id
              }}
              search={routeSearch}
              onClick={() =>
                rememberReturnTarget(detailHref, {
                  href: currentHref,
                  label: 'ResultTable 列表'
                })
              }
              className="link"
            >
              {resultTable.table_id}
            </Link>
          );
        }
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
          <h2>ResultTable</h2>
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
