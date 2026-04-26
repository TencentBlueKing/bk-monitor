import { useLocation, useSearch } from '@tanstack/react-router';
import { Loader2 } from 'lucide-react';
import type { ColumnDef } from '@tanstack/react-table';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { buildHref, getStoredReturnTarget } from '../../shared/navigation/returnTarget';
import { DataTable } from '../../shared/table/DataTable';
import { formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import {
  getClusterConfigComponentConfig,
  getComponentConfig,
  getDataLinkComponentConfig
} from './api';
import type {
  ClusterConfigDetailResponse,
  ComponentDetailResponse,
  DataLinkDetailResponse
} from './schemas';
import { useClusterConfigDetail, useComponentDetail, useDataLinkDetail } from './queries';

function getDetailSearchParams(search: Record<string, unknown>) {
  return {
    kind: typeof search.kind === 'string' ? search.kind : '',
    namespace: typeof search.namespace === 'string' ? search.namespace : '',
    name: typeof search.name === 'string' ? search.name : '',
    dataLinkName: typeof search.dataLinkName === 'string' ? search.dataLinkName : '',
    clusterKind: typeof search.clusterKind === 'string' ? search.clusterKind : ''
  };
}

export function DataLinkDetailPage() {
  const search = useSearch({ strict: false });
  const params = useMemo(() => getDetailSearchParams(search), [search]);
  const { kind, namespace, name, dataLinkName, clusterKind } = params;

  const currentHref = useLocation({ select: (location) => String(location.href) });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);
  const isDataLink = kind === 'DataLink';
  const isClusterConfig = kind === 'ClusterConfig';
  const listKind = isClusterConfig ? 'ClusterConfig' : isDataLink ? 'DataLink' : kind;
  const fallbackReturnHref = buildHref('/data-links', { ...routeSearch, kind: listKind });
  const returnTarget = getStoredReturnTarget(currentHref, fallbackReturnHref, 'DataLink 列表');

  const componentDetailParams = useMemo(
    () => ({
      bkTenantId: currentTenantId,
      kind: kind as ComponentDetailResponse['kind'],
      namespace,
      name
    }),
    [currentTenantId, kind, namespace, name]
  );

  const clusterConfigDetailParams = useMemo(
    () => ({
      bkTenantId: currentTenantId,
      kind: clusterKind,
      namespace,
      name
    }),
    [currentTenantId, clusterKind, namespace, name]
  );

  const datalinkDetailParams = useMemo(
    () => ({
      bkTenantId: currentTenantId,
      dataLinkName
    }),
    [currentTenantId, dataLinkName]
  );

  const componentDetailQuery = useComponentDetail(currentEnvironment!, componentDetailParams);

  const clusterConfigDetailQuery = useClusterConfigDetail(
    currentEnvironment!,
    clusterConfigDetailParams
  );

  const datalinkDetailQuery = useDataLinkDetail(currentEnvironment!, datalinkDetailParams);

  if (!currentEnvironment) {
    return <PageState title="缺少环境上下文" />;
  }

  if (!kind) {
    return <PageState title="缺少 kind 参数" />;
  }

  if (isDataLink) {
    if (datalinkDetailQuery.isLoading) {
      return <PageState title="正在加载 DataLink 详情..." />;
    }
    if (datalinkDetailQuery.isError || !datalinkDetailQuery.data) {
      return <PageState title="加载失败" description={String(datalinkDetailQuery.error)} />;
    }
    return (
      <DataLinkDetailView
        detail={datalinkDetailQuery.data}
        currentEnvironment={currentEnvironment}
        currentTenantId={currentTenantId}
        returnTarget={returnTarget}
      />
    );
  }

  if (isClusterConfig) {
    if (clusterConfigDetailQuery.isLoading) {
      return <PageState title="正在加载 ClusterConfig 详情..." />;
    }
    if (clusterConfigDetailQuery.isError || !clusterConfigDetailQuery.data) {
      return <PageState title="加载失败" description={String(clusterConfigDetailQuery.error)} />;
    }
    return (
      <ClusterConfigDetailView
        detail={clusterConfigDetailQuery.data}
        currentEnvironment={currentEnvironment}
        currentTenantId={currentTenantId}
        returnTarget={returnTarget}
      />
    );
  }

  if (componentDetailQuery.isLoading) {
    return <PageState title="正在加载组件详情..." />;
  }
  if (componentDetailQuery.isError || !componentDetailQuery.data) {
    return <PageState title="加载失败" description={String(componentDetailQuery.error)} />;
  }
  return (
    <ComponentDetailView
      detail={componentDetailQuery.data}
      currentEnvironment={currentEnvironment}
      currentTenantId={currentTenantId}
      returnTarget={returnTarget}
    />
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

// --- Component Detail View ---

function ComponentDetailView({
  detail,
  currentEnvironment,
  currentTenantId,
  returnTarget
}: {
  detail: ComponentDetailResponse;
  currentEnvironment: NonNullable<ReturnType<typeof useEnvironmentConfig>['currentEnvironment']>;
  currentTenantId: string;
  returnTarget: { href: string; label: string };
}) {
  const [configState, setConfigState] = useState<{
    loading: boolean;
    data: unknown;
    error: string | null;
  }>({ loading: true, data: null, error: null });

  const fetchConfig = useCallback(async () => {
    setConfigState({ loading: true, data: null, error: null });
    try {
      const result = await getComponentConfig(currentEnvironment, {
        bkTenantId: currentTenantId,
        kind: detail.kind,
        namespace: detail.namespace,
        name: detail.name
      });
      setConfigState({ loading: false, data: result.component_config, error: null });
    } catch (err) {
      setConfigState({ loading: false, data: null, error: String(err) });
    }
  }, [currentEnvironment, currentTenantId, detail]);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">{detail.kind} 详情</div>
          <h2>{detail.name}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info label="kind" value={detail.kind} />
          <Info label="name" value={detail.name} />
          <Info label="namespace" value={detail.namespace} />
          <Info label="status" value={detail.status} />
          <Info label="dataLinkName" value={detail.data_link_name ?? '-'} />
          <Info label="bkBizId" value={String(detail.bk_biz_id)} />
          <Info label="bkTenantId" value={detail.bk_tenant_id} />
          {detail.bk_data_id !== undefined ? (
            <Info label="bk_data_id" value={String(detail.bk_data_id)} />
          ) : null}
          {detail.table_id ? <Info label="tableId" value={detail.table_id} /> : null}
          {detail.data_type ? <Info label="dataType" value={detail.data_type} /> : null}
          {detail.vm_cluster_name ? (
            <Info label="vmClusterName" value={detail.vm_cluster_name} />
          ) : null}
          {detail.es_cluster_name ? (
            <Info label="esClusterName" value={detail.es_cluster_name} />
          ) : null}
          {detail.doris_cluster_name ? (
            <Info label="dorisClusterName" value={detail.doris_cluster_name} />
          ) : null}
          {detail.bkbase_result_table_name ? (
            <Info label="bkbaseResultTableName" value={detail.bkbase_result_table_name} />
          ) : null}
          <Info label="createdAt" value={formatDateTime(detail.created_at)} />
          <Info label="updatedAt" value={formatDateTime(detail.updated_at)} />
        </CardContent>
      </Card>

      <div className="section-stack">
        <section>
          <h3>component_config</h3>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={configState.loading}
              onClick={() => void fetchConfig()}
            >
              {configState.loading ? (
                <Loader2 aria-hidden="true" size={16} className="animate-spin" />
              ) : null}
              刷新配置
            </Button>
          </div>
          <Card className="mt-3">
            <CardContent className="py-3">
              {configState.loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 aria-hidden="true" size={14} className="animate-spin" />
                  加载中...
                </div>
              ) : configState.error ? (
                <div className="text-sm text-destructive">{configState.error}</div>
              ) : (
                <JsonBlock value={configState.data} />
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </section>
  );
}

// --- ClusterConfig Detail View ---

function ClusterConfigDetailView({
  detail,
  currentEnvironment,
  currentTenantId,
  returnTarget
}: {
  detail: ClusterConfigDetailResponse;
  currentEnvironment: NonNullable<ReturnType<typeof useEnvironmentConfig>['currentEnvironment']>;
  currentTenantId: string;
  returnTarget: { href: string; label: string };
}) {
  const [configState, setConfigState] = useState<{
    loading: boolean;
    data: unknown;
    error: string | null;
  }>({ loading: true, data: null, error: null });

  const fetchConfig = useCallback(async () => {
    setConfigState({ loading: true, data: null, error: null });
    try {
      const result = await getClusterConfigComponentConfig(currentEnvironment, {
        bkTenantId: currentTenantId,
        kind: detail.kind,
        namespace: detail.namespace,
        name: detail.name
      });
      setConfigState({ loading: false, data: result.component_config, error: null });
    } catch (err) {
      setConfigState({ loading: false, data: null, error: String(err) });
    }
  }, [currentEnvironment, currentTenantId, detail]);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ClusterConfig 详情</div>
          <h2>{detail.name}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <div className="info-item">
            <span>kind</span>
            <strong>
              <Badge>{detail.kind}</Badge>
            </strong>
          </div>
          <Info label="name" value={detail.name} />
          <Info label="namespace" value={detail.namespace} />
          <Info label="bkTenantId" value={detail.bk_tenant_id} />
          <Info label="createdAt" value={formatDateTime(detail.created_at)} />
          <Info label="updatedAt" value={formatDateTime(detail.updated_at)} />
        </CardContent>
      </Card>

      <div className="section-stack">
        <section>
          <h3>origin_config</h3>
          <Card>
            <CardContent className="py-3">
              <JsonBlock value={detail.origin_config} />
            </CardContent>
          </Card>
        </section>

        <section>
          <h3>component_config</h3>
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={configState.loading}
              onClick={() => void fetchConfig()}
            >
              {configState.loading ? (
                <Loader2 aria-hidden="true" size={16} className="animate-spin" />
              ) : null}
              刷新配置
            </Button>
          </div>
          <Card className="mt-3">
            <CardContent className="py-3">
              {configState.loading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 aria-hidden="true" size={14} className="animate-spin" />
                  加载中...
                </div>
              ) : configState.error ? (
                <div className="text-sm text-destructive">{configState.error}</div>
              ) : (
                <JsonBlock value={configState.data} />
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </section>
  );
}

// --- DataLink Detail View ---

interface ChildComponentRow {
  kind: string;
  name: string;
  namespace: string;
  componentConfig?: unknown;
}

function DataLinkChildComponentsTable({
  kind,
  rows,
  currentEnvironment,
  currentTenantId
}: {
  kind: string;
  rows: ChildComponentRow[];
  currentEnvironment: NonNullable<ReturnType<typeof useEnvironmentConfig>['currentEnvironment']>;
  currentTenantId: string;
}) {
  const [fetchedConfigs, setFetchedConfigs] = useState<
    Record<string, { loading: boolean; data: unknown; error: string | null }>
  >({});
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  const fetchSingle = useCallback(
    async (row: ChildComponentRow) => {
      const key = `${row.namespace}::${row.kind}::${row.name}`;
      setFetchedConfigs((prev) => ({
        ...prev,
        [key]: { loading: true, data: null, error: null }
      }));

      try {
        const result = await getDataLinkComponentConfig(currentEnvironment, {
          bkTenantId: currentTenantId,
          kind: row.kind,
          namespace: row.namespace,
          name: row.name
        });
        setFetchedConfigs((prev) => ({
          ...prev,
          [key]: { loading: false, data: result.component_config, error: null }
        }));
      } catch (err) {
        setFetchedConfigs((prev) => ({
          ...prev,
          [key]: { loading: false, data: null, error: String(err) }
        }));
      }
    },
    [currentEnvironment, currentTenantId]
  );

  useEffect(() => {
    for (const row of rows) {
      void fetchSingle(row);
    }
  }, [rows, fetchSingle]);

  const toggleExpand = useCallback((key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const columns = useMemo<Array<ColumnDef<ChildComponentRow>>>(
    () => [
      { header: 'name', size: 200, cell: ({ row }) => row.original.name },
      { header: 'namespace', size: 120, cell: ({ row }) => row.original.namespace },
      {
        header: '操作',
        size: 180,
        cell: ({ row }) => {
          const item = row.original;
          const key = `${item.namespace}::${item.kind}::${item.name}`;
          const fetched = fetchedConfigs[key];
          const isExpanded = expandedKeys.has(key);

          return (
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={fetched?.loading}
                onClick={() => void fetchSingle(item)}
              >
                {fetched?.loading ? (
                  <Loader2 aria-hidden="true" size={14} className="animate-spin" />
                ) : null}
                刷新配置
              </Button>
              {fetched && !fetched.loading ? (
                <button
                  type="button"
                  className="text-xs text-primary hover:underline"
                  onClick={() => toggleExpand(key)}
                >
                  {isExpanded ? '收起' : '展开'}
                </button>
              ) : null}
            </div>
          );
        }
      }
    ],
    [fetchedConfigs, expandedKeys, fetchSingle, toggleExpand]
  );

  const renderExpandedRow = useCallback(
    (row: ChildComponentRow) => {
      const key = `${row.namespace}::${row.kind}::${row.name}`;
      const config = fetchedConfigs[key];
      if (!config) return null;

      if (config.loading) {
        return (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 aria-hidden="true" size={14} className="animate-spin" />
            加载中...
          </div>
        );
      }

      if (config.error) {
        return <div className="text-sm text-destructive">{config.error}</div>;
      }

      return <JsonBlock value={config.data} />;
    },
    [fetchedConfigs]
  );

  return (
    <section>
      <h3>
        <Badge>{kind}</Badge>
        <span className="ml-2 text-muted-foreground">({rows.length})</span>
      </h3>
      <DataTable data={rows} columns={columns} renderExpandedRow={renderExpandedRow} />
    </section>
  );
}

function DataLinkDetailView({
  detail,
  currentEnvironment,
  currentTenantId,
  returnTarget
}: {
  detail: DataLinkDetailResponse;
  currentEnvironment: NonNullable<ReturnType<typeof useEnvironmentConfig>['currentEnvironment']>;
  currentTenantId: string;
  returnTarget: { href: string; label: string };
}) {
  const groupedComponents = useMemo(() => {
    const result: Record<string, ChildComponentRow[]> = {};
    for (const [kind, components] of Object.entries(detail.components)) {
      result[kind] = components.map((c) => ({
        kind: c.kind,
        name: c.name,
        namespace: c.namespace,
        componentConfig: c.component_config
      }));
    }
    return result;
  }, [detail.components]);

  const sortedKinds = useMemo(
    () =>
      Object.keys(groupedComponents).sort((a, b) => {
        const priority = ['DataId', 'ResultTable', 'VmStorageBinding'];
        const aIdx = priority.indexOf(a);
        const bIdx = priority.indexOf(b);
        if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
        if (aIdx !== -1) return -1;
        if (bIdx !== -1) return 1;
        return a.localeCompare(b);
      }),
    [groupedComponents]
  );

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">DataLink 详情</div>
          <h2>{detail.data_link_name}</h2>
        </div>
        <Button asChild variant="secondary">
          <a href={returnTarget.href}>返回 {returnTarget.label}</a>
        </Button>
      </div>

      <section>
        <h3>基本信息</h3>
        <Card>
          <CardContent className="detail-grid">
            <Info label="dataLinkName" value={detail.data_link_name} />
            <Info label="namespace" value={detail.namespace} />
            <Info label="dataLinkStrategy" value={detail.data_link_strategy} />
            <Info label="bkDataId" value={String(detail.bk_data_id)} />
            <Info label="bkTenantId" value={detail.bk_tenant_id} />
            <Info label="tableIds" value={detail.table_ids.join(', ')} />
            <Info label="createdAt" value={formatDateTime(detail.created_at)} />
            <Info label="updatedAt" value={formatDateTime(detail.updated_at)} />
          </CardContent>
        </Card>
      </section>

      <div className="section-stack">
        <section>
          <h3>关联组件</h3>
          {sortedKinds.map((kind) => {
            const rows = groupedComponents[kind];
            if (!rows) return null;
            return (
              <DataLinkChildComponentsTable
                key={kind}
                kind={kind}
                rows={rows}
                currentEnvironment={currentEnvironment}
                currentTenantId={currentTenantId}
              />
            );
          })}
          {sortedKinds.length === 0 ? <PageState title="无关联组件" /> : null}
        </section>
      </div>
    </section>
  );
}
