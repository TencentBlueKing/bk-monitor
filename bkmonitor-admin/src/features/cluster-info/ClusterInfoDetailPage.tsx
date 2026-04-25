import { Link, useParams } from '@tanstack/react-router';
import { useState } from 'react';

import { Badge } from '../../shared/components/Badge';
import { JsonBlock } from '../../shared/components/JsonBlock';
import { PageState } from '../../shared/components/PageState';
import { Button } from '../../shared/components/ui/button';
import { Card, CardContent } from '../../shared/components/ui/card';
import { formatBoolean, formatDateTime } from '../../shared/utils/format';
import { useEnvironmentConfig } from '../environments/hooks';
import { createEnvironmentSearch } from '../environments/search';
import { CLUSTER_TYPE_TONE } from './constants';
import { useClusterInfoDetail } from './queries';
import type { ClusterConfig } from './schemas';

export function ClusterInfoDetailPage() {
  const params = useParams({ strict: false });
  const { currentEnvironment, currentTenantId } = useEnvironmentConfig();
  const clusterId = Number(params.clusterId);

  const detailQuery = useClusterInfoDetail(currentEnvironment!, currentTenantId, clusterId);
  const routeSearch = createEnvironmentSearch(currentEnvironment?.id ?? 'local', currentTenantId);

  if (!currentEnvironment || Number.isNaN(clusterId)) {
    return <PageState title="存储集群参数无效" />;
  }

  if (detailQuery.isLoading) {
    return <PageState title="正在加载存储集群详情..." />;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return <PageState title="加载失败" description={String(detailQuery.error)} />;
  }

  const { cluster_info, cluster_configs, related_result_tables, related_datasources } =
    detailQuery.data;

  return (
    <section className="page-panel">
      <div className="page-heading">
        <div>
          <div className="eyebrow">存储集群详情</div>
          <h2>{cluster_info.cluster_name}</h2>
        </div>
        <Button asChild variant="secondary">
          <Link to="/clusters" search={routeSearch}>
            返回列表
          </Link>
        </Button>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info label="cluster_name" value={cluster_info.cluster_name} />
          <Info label="display_name" value={cluster_info.display_name ?? '–'} />
          <Info
            label="cluster_type"
            value={
              <Badge tone={CLUSTER_TYPE_TONE[cluster_info.cluster_type] ?? 'default'}>
                {cluster_info.cluster_type}
              </Badge>
            }
            raw
          />
          <Info label="version" value={cluster_info.version ?? '–'} />
          <Info label="description" value={cluster_info.description ?? '–'} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="detail-grid">
            <h3 className="col-span-full text-sm font-semibold">连接信息</h3>
            <Info label="domain_name" value={cluster_info.domain_name ?? '–'} />
            <Info label="port" value={String(cluster_info.port ?? '–')} />
            <Info label="schema" value="–" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="detail-grid">
            <h3 className="col-span-full text-sm font-semibold">安全配置</h3>
            <Info label="SSL" value="–" />
            <Info label="Auth" value="–" />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="detail-grid">
          <Info
            label="默认集群"
            value={
              <Badge tone={cluster_info.is_default_cluster ? 'success' : 'muted'}>
                {formatBoolean(cluster_info.is_default_cluster)}
              </Badge>
            }
            raw
          />
          <Info label="注册系统" value={cluster_info.registered_system ?? '–'} />
          <Info label="label" value={cluster_info.label ?? '–'} />
          <Info label="创建时间" value={formatDateTime(cluster_info.create_time)} />
          <Info label="更新时间" value={formatDateTime(cluster_info.last_modify_time)} />
        </CardContent>
      </Card>

      <section>
        <h3>ClusterConfig</h3>
        {cluster_configs.length === 0 ? (
          <PageState title="暂无 ClusterConfig" />
        ) : (
          <div className="space-y-4">
            {groupByNamespace(cluster_configs).map(([namespace, configs]) => (
              <NamespaceSection
                key={namespace}
                namespace={namespace}
                configs={configs}
                routeSearch={routeSearch}
              />
            ))}
          </div>
        )}
      </section>

      <Card>
        <CardContent className="detail-grid">
          <Info
            label="关联结果表"
            value={
              <Link to="/result-tables" search={routeSearch} className="link">
                {related_result_tables}
              </Link>
            }
            raw
          />
          <Info
            label="关联数据源"
            value={
              <Link to="/datasources" search={routeSearch} className="link">
                {related_datasources}
              </Link>
            }
            raw
          />
        </CardContent>
      </Card>
    </section>
  );
}

function Info({ label, value, raw }: { label: string; value: React.ReactNode; raw?: boolean }) {
  return (
    <div className="info-item">
      <span>{label}</span>
      {raw ? value : <strong>{value}</strong>}
    </div>
  );
}

function groupByNamespace(configs: ClusterConfig[]): Array<[string, ClusterConfig[]]> {
  const map = new Map<string, ClusterConfig[]>();
  for (const c of configs) {
    const list = map.get(c.namespace) ?? [];
    list.push(c);
    map.set(c.namespace, list);
  }
  return [...map.entries()];
}

function NamespaceSection({
  namespace,
  configs,
  routeSearch
}: {
  namespace: string;
  configs: ClusterConfig[];
  routeSearch: ReturnType<typeof createEnvironmentSearch>;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <CardContent className="p-0">
        <button
          type="button"
          className="flex w-full items-center justify-between px-5 py-3 text-left font-medium hover:bg-muted/30"
          onClick={() => setOpen((v) => !v)}
        >
          <span>{namespace}</span>
          <span className="text-muted-foreground">{open ? '▲' : '▼'}</span>
        </button>
        {open ? (
          <div className="space-y-4 px-5 pb-5">
            {configs.map((config) => (
              <div
                key={`${config.kind}-${config.name}`}
                className="space-y-3 border-t pt-4 first:border-t-0 first:pt-0"
              >
                <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <span>
                    kind: <strong className="text-foreground">{config.kind}</strong>
                  </span>
                  <span>
                    name: <strong className="text-foreground">{config.name}</strong>
                  </span>
                  <span>created: {formatDateTime(config.created_at)}</span>
                  <span>updated: {formatDateTime(config.updated_at)}</span>
                </div>

                <OriginConfigSection originConfig={config.origin_config} />

                {config.component_config === null ? (
                  <div className="rounded-md bg-muted/50 p-4 text-center text-muted-foreground">
                    获取失败
                  </div>
                ) : config.component_config ? (
                  <ComponentConfigSection
                    componentConfig={config.component_config}
                    routeSearch={routeSearch}
                  />
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function OriginConfigSection({ originConfig }: { originConfig: Record<string, unknown> }) {
  const [show, setShow] = useState(false);

  return (
    <div>
      <button
        type="button"
        className="text-sm text-primary hover:underline"
        onClick={() => setShow((v) => !v)}
      >
        {show ? '隐藏 origin_config' : '查看 origin_config'}
      </button>
      {show ? <JsonBlock value={originConfig} /> : null}
    </div>
  );
}

function ComponentConfigSection({
  componentConfig,
  routeSearch
}: {
  componentConfig: NonNullable<ClusterConfig['component_config']>;
  routeSearch: ReturnType<typeof createEnvironmentSearch>;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {componentConfig.status ? (
        <Card className="md:col-span-2">
          <CardContent className="flex items-center gap-3 py-3">
            <span className="text-sm font-medium">状态:</span>
            <Badge
              tone={
                componentConfig.status.phase === 'Ok' || componentConfig.status.phase === 'ok'
                  ? 'success'
                  : 'danger'
              }
            >
              {componentConfig.status.phase ?? 'Unknown'}
            </Badge>
            {componentConfig.status.message ? (
              <span className="text-sm text-muted-foreground">
                {componentConfig.status.message}
              </span>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {componentConfig.sources && componentConfig.sources.length > 0 ? (
        <Card>
          <CardContent className="py-3">
            <h4 className="mb-2 text-sm font-semibold">Sources</h4>
            <div className="space-y-1 text-sm">
              {componentConfig.sources.map((source, i) => (
                <div key={i}>
                  {typeof source.kind === 'string' && source.kind === 'DataId' && source.data_id ? (
                    <Link
                      to="/datasources/$bkDataId"
                      params={{ bkDataId: safeToString(source.data_id) }}
                      search={routeSearch}
                      className="link"
                    >
                      DataId #{safeToString(source.data_id)}
                    </Link>
                  ) : (
                    <span>
                      {typeof source.kind === 'string'
                        ? `${source.kind}: ${safeToString(source.name)}`
                        : JSON.stringify(source)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {componentConfig.sinks && componentConfig.sinks.length > 0 ? (
        <Card>
          <CardContent className="py-3">
            <h4 className="mb-2 text-sm font-semibold">Sinks</h4>
            <div className="space-y-1 text-sm">
              {componentConfig.sinks.map((sink, i) => (
                <div key={i}>
                  {typeof sink.kind === 'string'
                    ? `${sink.kind}: ${safeToString(sink.name)}`
                    : JSON.stringify(sink)}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {componentConfig.transforms && componentConfig.transforms.length > 0 ? (
        <Card>
          <CardContent className="py-3">
            <h4 className="mb-2 text-sm font-semibold">Transforms</h4>
            <div className="space-y-1 text-sm">
              {componentConfig.transforms.map((transform, i) => (
                <div key={i}>
                  {typeof transform.kind === 'string'
                    ? `${transform.kind}: ${safeToString(transform.name)}`
                    : JSON.stringify(transform)}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function safeToString(val: unknown): string {
  if (val === null || val === undefined) return '–';
  if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean')
    return String(val);
  return JSON.stringify(val);
}
