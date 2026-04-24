import { Link, useNavigate, useParams } from '@tanstack/react-router';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { Input } from '../../shared/components/ui/input';
import { Label } from '../../shared/components/ui/label';
import { DataTable } from '../../shared/table/DataTable';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { useResultTableDetail, useResultTableFields } from './queries';
import { resultTableFieldListQuerySchema } from './schemas';

export function ResultTableDetailPage() {
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const tableId = params.tableId ?? '';
  const [fieldName, setFieldName] = useState('');
  const [fieldPage, setFieldPage] = useState(1);

  const initialTenantRef = useRef(currentTenantId);
  useEffect(() => {
    if (currentTenantId !== initialTenantRef.current) {
      void navigate({
        to: '/result-tables',
        search: createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId)
      });
    }
  }, [currentTenantId, currentEnvironment?.id, navigate]);

  const detailQuery = useResultTableDetail(currentEnvironment!, currentTenantId, tableId);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const fieldQueryParams = resultTableFieldListQuerySchema.parse({
    bkTenantId: currentTenantId,
    tableId,
    fieldName: fieldName || undefined,
    page: fieldPage,
    pageSize: 20
  });
  const fieldQuery = useResultTableFields(currentEnvironment!, fieldQueryParams);

  if (!currentEnvironment || !tableId) {
    return <PageState title="ResultTable 参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载 ResultTable 详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const { result_table, options, datasources, custom_groups, es_storage, vm_record } =
    detailQuery.data;

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ResultTable Detail</div>
          <h2>{result_table.table_id}</h2>
        </div>
        <Button asChild variant="secondary">
          <Link to="/result-tables" search={routeSearch}>
            返回列表
          </Link>
        </Button>
      </div>
      <Card>
        <CardContent className="detail-grid">
          <Info label="中文名" value={result_table.table_name_zh} />
          <Info label="租户" value={result_table.bk_tenant_id} />
          <Info label="业务" value={String(result_table.bk_biz_id)} />
          <Info label="schema" value={result_table.schema_type} />
          <Info label="默认存储" value={result_table.default_storage ?? '-'} />
          <Info label="label" value={result_table.label} />
          <Info label="data_label" value={result_table.data_label ?? '-'} />
          <Info label="启用" value={formatBoolean(result_table.is_enable)} />
          <Info label="删除" value={formatBoolean(result_table.is_deleted)} />
          <Info label="更新时间" value={formatDateTime(result_table.last_modify_time)} />
        </CardContent>
      </Card>
      <div className="section-stack">
        <section>
          <h3>Options</h3>
          <DataTable
            data={options}
            columns={[
              { header: 'name', accessorKey: 'name' },
              { header: 'value_type', accessorKey: 'value_type' },
              { header: 'creator', accessorKey: 'creator' },
              { header: 'value', cell: ({ row }) => <JsonBlock value={row.original.value} /> }
            ]}
          />
        </section>
        <section>
          <h3>字段</h3>
          <form
            className="inline-filter"
            onSubmit={(event) => {
              event.preventDefault();
              setFieldPage(1);
            }}
          >
            <div className="grid gap-1.5">
              <Label>field_name</Label>
              <Input value={fieldName} onChange={(event) => setFieldName(event.target.value)} />
            </div>
            <Button type="submit">
              <Search aria-hidden="true" size={16} />
              过滤
            </Button>
          </form>
          {fieldQuery.isLoading ? (
            <PageState title="正在加载字段..." />
          ) : fieldQuery.isError ? (
            <PageState title="字段加载失败" description={String(fieldQuery.error)} />
          ) : (
            <>
              <DataTable
                data={fieldQuery.data?.items ?? []}
                columns={[
                  { header: 'field_name', accessorKey: 'field_name' },
                  { header: 'field_type', accessorKey: 'field_type' },
                  { header: 'tag', accessorKey: 'tag' },
                  { header: 'description', accessorKey: 'description' },
                  { header: 'unit', accessorKey: 'unit' },
                  {
                    header: '用户配置',
                    cell: ({ row }) => formatBoolean(row.original.is_config_by_user)
                  },
                  {
                    header: '禁用',
                    cell: ({ row }) => (
                      <Badge tone={row.original.is_disabled ? 'danger' : 'success'}>
                        {formatBoolean(row.original.is_disabled)}
                      </Badge>
                    )
                  },
                  { header: 'options', accessorKey: 'option_count' }
                ]}
              />
              <Card>
                <CardContent className="pager">
                  <Button
                    variant="secondary"
                    disabled={fieldPage <= 1}
                    onClick={() => setFieldPage((value) => value - 1)}
                  >
                    <ChevronLeft aria-hidden="true" size={16} />
                    上一页
                  </Button>
                  <span>
                    第 {fieldPage} 页 / 共 {fieldQuery.data?.total ?? 0} 个字段
                  </span>
                  <Button
                    variant="secondary"
                    disabled={(fieldQuery.data?.items.length ?? 0) < fieldQueryParams.pageSize}
                    onClick={() => setFieldPage((value) => value + 1)}
                  >
                    下一页
                    <ChevronRight aria-hidden="true" size={16} />
                  </Button>
                </CardContent>
              </Card>
            </>
          )}
        </section>
        <section>
          <h3>数据源</h3>
          <DataTable
            data={datasources}
            columns={[
              {
                header: 'bk_data_id',
                cell: ({ row }) => (
                  <Link
                    to="/datasources/$bkDataId"
                    params={{
                      bkDataId: String(row.original.bk_data_id)
                    }}
                    search={routeSearch}
                    className="link"
                  >
                    {row.original.bk_data_id}
                  </Link>
                )
              },
              { header: 'data_name', accessorKey: 'data_name' },
              { header: 'created_from', accessorKey: 'created_from' },
              { header: 'source_label', accessorKey: 'source_label' },
              { header: 'type_label', accessorKey: 'type_label' },
              { header: '启用', cell: ({ row }) => formatBoolean(row.original.is_enable) }
            ]}
          />
        </section>
        <section>
          <h3>自定义分组</h3>
          <JsonBlock value={custom_groups} />
        </section>
        <section className="two-column">
          <div>
            <h3>ESStorage</h3>
            <JsonBlock value={es_storage ?? { message: '无 ESStorage' }} />
          </div>
          <div>
            <h3>AccessVMRecord</h3>
            <JsonBlock value={vm_record ?? { message: '无 AccessVMRecord' }} />
          </div>
        </section>
      </div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
