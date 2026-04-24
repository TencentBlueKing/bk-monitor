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
import { datasourceListQuerySchema, type DataSourceSummary } from './schemas';
import { useDatasourceList } from './queries';

export function DataSourceListPage() {
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const [bkDataId, setBkDataId] = useState('');
  const [dataName, setDataName] = useState('');
  const [tableId, setTableId] = useState('');
  const [page, setPage] = useState(1);
  const [activeFilters, setActiveFilters] = useState({ bkDataId: '', dataName: '', tableId: '' });
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  const query = datasourceListQuerySchema.parse({
    bkTenantId: currentTenantId,
    bkDataId: activeFilters.bkDataId || undefined,
    dataName: activeFilters.dataName || undefined,
    tableId: activeFilters.tableId || undefined,
    page,
    pageSize: 20
  });
  const datasourceQuery = useDatasourceList(currentEnvironment!, query);
  const columns = useMemo<Array<ColumnDef<DataSourceSummary>>>(
    () => [
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
      { header: '名称', accessorKey: 'data_name' },
      { header: '租户', accessorKey: 'bk_tenant_id' },
      {
        header: '类型',
        cell: ({ row }) => (
          <div className="badge-row">
            <Badge>{row.original.type_label}</Badge>
            <Badge tone="muted">{row.original.source_label}</Badge>
          </div>
        )
      },
      { header: '来源', accessorKey: 'created_from' },
      {
        header: 'Kafka 集群',
        cell: ({ row }) => {
          const cluster = row.original.kafka_cluster;
          const clusterId = cluster?.cluster_id ?? row.original.mq_cluster_id;
          const clusterName = cluster ? getKafkaClusterName(cluster) : null;

          if (!clusterId) {
            return <span className="muted-text">-</span>;
          }

          return <KafkaClusterValue name={clusterName || `#${clusterId}`} clusterId={clusterId} />;
        }
      },
      {
        header: '启用',
        cell: ({ row }) => (
          <Badge tone={row.original.is_enable ? 'success' : 'danger'}>
            {formatBoolean(row.original.is_enable)}
          </Badge>
        )
      },
      { header: '空间', accessorKey: 'space_uid' },
      { header: 'RT 数', accessorKey: 'result_table_count' },
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
          <h2>DataSource</h2>
        </div>
      </div>
      <form
        className="filter-grid"
        onSubmit={(event) => {
          event.preventDefault();
          setActiveFilters({ bkDataId, dataName, tableId });
          setPage(1);
        }}
      >
        <div className="grid gap-1.5">
          <Label>bk_data_id</Label>
          <Input
            inputMode="numeric"
            value={bkDataId}
            onChange={(event) => setBkDataId(event.target.value.replace(/\D/g, ''))}
          />
        </div>
        <div className="grid gap-1.5">
          <Label>data_name</Label>
          <Input value={dataName} onChange={(event) => setDataName(event.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label>table_id</Label>
          <Input value={tableId} onChange={(event) => setTableId(event.target.value)} />
        </div>
        <Button type="submit">
          <Search aria-hidden="true" size={16} />
          搜索
        </Button>
      </form>
      {datasourceQuery.isError ? (
        <PageState title="加载失败" description={String(datasourceQuery.error)} />
      ) : datasourceQuery.isLoading ? (
        <PageState title="正在加载 DataSource..." />
      ) : (
        <>
          <DataTable data={datasourceQuery.data?.items ?? []} columns={columns} />
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
                第 {page} 页 / 共 {datasourceQuery.data?.total ?? 0} 条
              </span>
              <Button
                variant="secondary"
                disabled={(datasourceQuery.data?.items.length ?? 0) < query.pageSize}
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

function getKafkaClusterName(cluster: NonNullable<DataSourceSummary['kafka_cluster']>) {
  return cluster.display_name || cluster.cluster_name || `#${cluster.cluster_id}`;
}

function KafkaClusterValue({ name, clusterId }: { name: string; clusterId: number }) {
  return (
    <button
      type="button"
      className="tooltip-value"
      aria-label={`Kafka 集群 ${name}，cluster_id ${clusterId}`}
    >
      <span className="tooltip-value-label">{name}</span>
      <span className="tooltip-value-panel">cluster_id: {clusterId}</span>
    </button>
  );
}
