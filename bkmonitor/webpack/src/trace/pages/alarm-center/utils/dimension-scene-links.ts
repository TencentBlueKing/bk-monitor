/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { K8sNewTabEnum, K8sTableColumnKeysEnum, SceneEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';

import { AlertTargetTypeMap } from '../typings/constants';

import type { IDimension } from '../typings/detail';

/** 告警目标类型（与后端 constants.alert 对齐） */
export const AlertTargetType = {
  HOST: 'HOST',
  SERVICE: 'SERVICE',
  TOPO: 'TOPO',
  K8S_POD: 'K8S-POD',
  K8S_NODE: 'K8S-NODE',
  K8S_SERVICE: 'K8S-SERVICE',
  K8S_WORKLOAD: 'K8S-WORKLOAD',
  APM_SERVICE: 'APM-SERVICE',
} as const;

export interface DimensionSceneLink {
  alias: string;
  url: string;
}

export interface DimensionSceneLinkContext {
  bizId: number;
  dimensions: IDimension[];
  target: string;
  targetType: string;
  timeRange?: [number, number];
}

type SceneLinkResolver = (item: IDimension, ctx: DimensionSceneLinkContext) => DimensionSceneLink | null;

const K8S_TARGET_TYPES = new Set<string>([
  AlertTargetType.K8S_POD,
  AlertTargetType.K8S_NODE,
  AlertTargetType.K8S_SERVICE,
  AlertTargetType.K8S_WORKLOAD,
]);

const normalizeDimKey = (key = '') => (key.startsWith('tags.') ? key.slice(5) : key);

const buildDimValueMap = (dimensions: IDimension[] = []) => {
  const map: Record<string, string> = {};
  for (const item of dimensions) {
    if (item.value == null || item.value === '') continue;
    const value = String(item.value);
    map[item.key] = value;
    const normalized = normalizeDimKey(item.key);
    if (!map[normalized]) {
      map[normalized] = value;
    }
  }
  return map;
};

const dimValue = (map: Record<string, string>, ...keys: string[]) => {
  for (const key of keys) {
    if (map[key]) return map[key];
  }
  return '';
};

/** 与 panel-k8s 跳转一致：开发态走 proxy，生产替换当前 hash */
export const buildMonitorHashUrl = (hash: string, bizId?: number) => {
  if (process.env.NODE_ENV === 'development') {
    return `${process.env.proxyUrl}?bizId=${bizId || window.cc_biz_id}${hash}`;
  }
  return location.href.replace(location.hash, hash);
};

export const parseApmTarget = (target = '') => {
  const separatorIndex = target.indexOf(':');
  if (separatorIndex < 1 || separatorIndex === target.length - 1) return null;
  return {
    appName: target.slice(0, separatorIndex),
    serviceName: target.slice(separatorIndex + 1),
  };
};

const withTimeQuery = (params: URLSearchParams, timeRange?: [number, number]) => {
  if (!timeRange?.[0] || !timeRange?.[1]) return;
  params.set('from', String(timeRange[0]));
  params.set('to', String(timeRange[1]));
};

export const buildApmApplicationUrl = (bizId: number, appName: string, timeRange?: [number, number]) => {
  const params = new URLSearchParams({ 'filter-app_name': appName });
  withTimeQuery(params, timeRange);
  return buildMonitorHashUrl(`#/apm/application?${params.toString()}`, bizId);
};

export const buildApmServiceUrl = (
  bizId: number,
  appName: string,
  serviceName: string,
  timeRange?: [number, number]
) => {
  const params = new URLSearchParams({
    'filter-app_name': appName,
    'filter-service_name': serviceName,
  });
  withTimeQuery(params, timeRange);
  return buildMonitorHashUrl(`#/apm/service?${params.toString()}`, bizId);
};

const resolveGroupByList = (groupBy?: K8sTableColumnKeysEnum) => {
  if (!groupBy) return [];
  if (groupBy === K8sTableColumnKeysEnum.WORKLOAD) {
    return [K8sTableColumnKeysEnum.WORKLOAD, K8sTableColumnKeysEnum.POD];
  }
  return [groupBy];
};

export const buildK8sMonitorUrl = (options: {
  bizId: number;
  cluster: string;
  filterBy: Record<string, string[]>;
  groupBy?: K8sTableColumnKeysEnum;
  scene: SceneEnum;
  timeRange?: [number, number];
}) => {
  const params = new URLSearchParams({
    cluster: options.cluster,
    scene: options.scene,
    groupBy: JSON.stringify(resolveGroupByList(options.groupBy)),
    activeTab: K8sNewTabEnum.CHART,
    filterBy: JSON.stringify(options.filterBy),
  });
  withTimeQuery(params, options.timeRange);
  return buildMonitorHashUrl(`#/k8s-new/?${params.toString()}`, options.bizId);
};

const resolveApmNames = (ctx: DimensionSceneLinkContext) => {
  const map = buildDimValueMap(ctx.dimensions);
  const parsed = ctx.targetType === AlertTargetType.APM_SERVICE ? parseApmTarget(ctx.target) : null;
  return {
    appName: dimValue(map, 'app_name') || parsed?.appName || '',
    serviceName: dimValue(map, 'service_name') || parsed?.serviceName || '',
  };
};

const resolveK8sResources = (ctx: DimensionSceneLinkContext) => {
  const map = buildDimValueMap(ctx.dimensions);
  const cluster = dimValue(map, 'bcs_cluster_id');
  const namespace = dimValue(map, 'namespace');
  const pod = dimValue(map, 'pod', 'pod_name') || (ctx.targetType === AlertTargetType.K8S_POD ? ctx.target : '');
  const node = dimValue(map, 'node', 'node_name') || (ctx.targetType === AlertTargetType.K8S_NODE ? ctx.target : '');
  const service = dimValue(map, 'service') || (ctx.targetType === AlertTargetType.K8S_SERVICE ? ctx.target : '');
  const workload =
    dimValue(map, 'workload') ||
    (map.workload_kind && map.workload_name ? `${map.workload_kind}:${map.workload_name}` : '') ||
    (ctx.targetType === AlertTargetType.K8S_WORKLOAD ? ctx.target : '');
  return { cluster, namespace, node, pod, service, workload };
};

const k8sLinkAlias = () => window.i18n.t('容器监控') as string;

type K8sJumpConfig = { filterBy: Record<string, string[]>; groupBy?: K8sTableColumnKeysEnum; scene: SceneEnum };
type K8sResourceKey = 'cluster' | 'namespace' | 'node' | 'pod' | 'service' | 'workload';

const buildK8sJumpConfig = (
  resource: ReturnType<typeof resolveK8sResources>,
  preferred?: K8sResourceKey
): K8sJumpConfig | null => {
  const configs: Record<K8sResourceKey, () => K8sJumpConfig | null> = {
    pod: () =>
      resource.pod
        ? {
            scene: SceneEnum.Performance,
            groupBy: K8sTableColumnKeysEnum.POD,
            filterBy: {
              ...(resource.namespace ? { namespace: [resource.namespace] } : {}),
              ...(resource.workload ? { workload: [resource.workload] } : {}),
              pod: [resource.pod],
            },
          }
        : null,
    node: () =>
      resource.node
        ? {
            scene: SceneEnum.Capacity,
            groupBy: K8sTableColumnKeysEnum.NODE,
            filterBy: { node: [resource.node] },
          }
        : null,
    service: () =>
      resource.service
        ? {
            scene: SceneEnum.Network,
            groupBy: K8sTableColumnKeysEnum.SERVICE,
            filterBy: {
              ...(resource.namespace ? { namespace: [resource.namespace] } : {}),
              service: [resource.service],
            },
          }
        : null,
    workload: () =>
      resource.workload
        ? {
            scene: SceneEnum.Performance,
            groupBy: K8sTableColumnKeysEnum.WORKLOAD,
            filterBy: {
              ...(resource.namespace ? { namespace: [resource.namespace] } : {}),
              workload: [resource.workload],
            },
          }
        : null,
    namespace: () =>
      resource.namespace
        ? {
            scene: SceneEnum.Performance,
            groupBy: K8sTableColumnKeysEnum.NAMESPACE,
            filterBy: { namespace: [resource.namespace] },
          }
        : null,
    cluster: () => ({ scene: SceneEnum.Performance, filterBy: {} }),
  };

  if (preferred) return configs[preferred]();
  return (
    configs.pod() ||
    configs.node() ||
    configs.service() ||
    configs.workload() ||
    configs.namespace() ||
    configs.cluster()
  );
};

const buildK8sUrlByResource = (
  ctx: DimensionSceneLinkContext,
  resource: ReturnType<typeof resolveK8sResources>,
  preferred?: K8sResourceKey
): DimensionSceneLink | null => {
  if (!resource.cluster) return null;
  const resolved = preferred ? buildK8sJumpConfig(resource, preferred) : buildK8sJumpConfig(resource);
  if (!resolved) return null;
  return {
    alias: k8sLinkAlias(),
    url: buildK8sMonitorUrl({
      bizId: ctx.bizId,
      cluster: resource.cluster,
      scene: resolved.scene,
      groupBy: resolved.groupBy,
      filterBy: resolved.filterBy,
      timeRange: ctx.timeRange,
    }),
  };
};

const resolveApmAppLink: SceneLinkResolver = (_item, ctx) => {
  const { appName } = resolveApmNames(ctx);
  if (!appName) return null;
  return {
    alias: window.i18n.t('APM应用') as string,
    url: buildApmApplicationUrl(ctx.bizId, appName, ctx.timeRange),
  };
};

const resolveApmServiceLink: SceneLinkResolver = (_item, ctx) => {
  const { appName, serviceName } = resolveApmNames(ctx);
  if (!appName || !serviceName) return null;
  return {
    alias: window.i18n.t('APM服务') as string,
    url: buildApmServiceUrl(ctx.bizId, appName, serviceName, ctx.timeRange),
  };
};

const resolveK8sLink =
  (preferred: K8sResourceKey): SceneLinkResolver =>
  (_item, ctx) =>
    buildK8sUrlByResource(ctx, resolveK8sResources(ctx), preferred);

const resolveK8sServiceLink: SceneLinkResolver = (item, ctx) => {
  if (ctx.targetType === AlertTargetType.APM_SERVICE) return null;
  if (!K8S_TARGET_TYPES.has(ctx.targetType) && !buildDimValueMap(ctx.dimensions).bcs_cluster_id) return null;
  return resolveK8sLink('service')(item, ctx);
};

/** 维度 key → 场景跳转。未注册的字段不加芯片。 */
const SCENE_LINK_RESOLVERS: Record<string, SceneLinkResolver> = {
  app_name: resolveApmAppLink,
  service_name: resolveApmServiceLink,
  bcs_cluster_id: (_item, ctx) => buildK8sUrlByResource(ctx, resolveK8sResources(ctx)),
  namespace: resolveK8sLink('namespace'),
  pod: resolveK8sLink('pod'),
  pod_name: resolveK8sLink('pod'),
  node: resolveK8sLink('node'),
  node_name: resolveK8sLink('node'),
  workload_name: resolveK8sLink('workload'),
  workload_kind: resolveK8sLink('workload'),
  service: resolveK8sServiceLink,
};

export const getDimensionDisplayValue = (item: IDimension) => {
  if (normalizeDimKey(item.key) === 'target_type') {
    const raw = String(item.value ?? '');
    return String(AlertTargetTypeMap[raw]?.alias || item.display_value || raw);
  }
  return String(item.display_value ?? item.value ?? '');
};

export const getTargetJumpUrl = (ctx: DimensionSceneLinkContext) => {
  if (!ctx.target) return '';
  if (ctx.targetType === AlertTargetType.APM_SERVICE) {
    const parsed = parseApmTarget(ctx.target) || resolveApmNames(ctx);
    if (!parsed?.appName || !parsed?.serviceName) return '';
    return buildApmServiceUrl(ctx.bizId, parsed.appName, parsed.serviceName, ctx.timeRange);
  }
  if (K8S_TARGET_TYPES.has(ctx.targetType)) {
    const preferred =
      ctx.targetType === AlertTargetType.K8S_POD
        ? 'pod'
        : ctx.targetType === AlertTargetType.K8S_NODE
          ? 'node'
          : ctx.targetType === AlertTargetType.K8S_SERVICE
            ? 'service'
            : 'workload';
    return buildK8sUrlByResource(ctx, resolveK8sResources(ctx), preferred)?.url || '';
  }
  return '';
};

export const getDimensionSceneLinks = (item: IDimension, ctx: DimensionSceneLinkContext): DimensionSceneLink[] => {
  const key = normalizeDimKey(item.key);
  if (key === 'target' || key === 'target_type') return [];
  const resolver = SCENE_LINK_RESOLVERS[key];
  if (!resolver) return [];
  const link = resolver(item, ctx);
  return link?.url ? [link] : [];
};

export const isTargetDimension = (key = '') => normalizeDimKey(key) === 'target';
