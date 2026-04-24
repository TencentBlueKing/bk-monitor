import { Link } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import { Label } from '../../shared/components/ui/label';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { resultTableListQuerySchema, type ResultTableSummary } from './schemas';
import { useResultTableList } from './queries';

export function ResultTableListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [tableId, setTableId] = useState('');
  const [bkDataId, setBkDataId] = useState('');
  const [dataLabel, setDataLabel] = useState('');
  const [page, setPage] = useState(1);
  const [activeFilters, setActiveFilters] = useState({ tableId: '', bkDataId: '', dataLabel: '' });
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const query = resultTableListQuerySchema.parse({
    bkTenantId: currentTenantId,
    tableId: activeFilters.tableId || undefined,
    bkDataId: activeFilters.bkDataId || undefined,
    dataLabel: activeFilters.dataLabel || undefined,
    page,
    pageSize: 20
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
      <form
        className="filter-grid"
        onSubmit={(event) => {
          event.preventDefault();
          setActiveFilters({ tableId, bkDataId, dataLabel });
          setPage(1);
        }}
      >
        <div className="grid gap-1.5">
          <Label>table_id</Label>
          <Input value={tableId} onChange={(event) => setTableId(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label>bk_data_id</Label>
          <Input
            inputMode="numeric"
            value={bkDataId}
            onChange={(event) => setBkDataId(event.target.value.replace(/\D/g, ''))}
          />
        </div>
        <div className="grid gap-1.5">
          <Label>data_label</Label>
          <Input value={dataLabel} onChange={(event) => setDataLabel(event.target.value)} />
        </div>
        <Button type="submit">
          <Search aria-hidden="true" size={16} />
          搜索
        </Button>
      </form>
      {resultTableQuery.isError ? (
        <PageState title="加载失败" description={String(resultTableQuery.error)} />
      ) : resultTableQuery.isLoading ? (
        <PageState title="正在加载 ResultTable..." />
      ) : (
        <>
          <DataTable data={resultTableQuery.data?.items ?? []} columns={columns} />
          <Card>
            <CardContent className="pager">
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                上一页
              </Button>
              <span>
                第 {page} 页 / 共 {resultTableQuery.data?.total ?? 0} 条
              </span>
              <Button
                variant="secondary"
                disabled={(resultTableQuery.data?.items.length ?? 0) < query.pageSize}
                onClick={() => setPage((value) => value + 1)}
              >
                下一页
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}
