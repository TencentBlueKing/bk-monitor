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

import { computed, onScopeDispose, watch } from 'vue';

import { getHostInfo } from 'monitor-api/modules/scene_view';
import { tryURLDecodeParse } from 'monitor-common/utils';
import { isBkHostId, LEGACY_IPV4_QUERY, splitLegacyIpv4HostId } from 'monitor-common/utils/host-monitor-url';
import { useRoute, useRouter } from 'vue-router';

import { DEFAULT_AGGREGATION_STATE } from '../constants/aggregation';
import { HOST_FILTER_FIELDS, NUMBER_METHODS } from '../constants/host-list';
import { isHostNode } from '../utils/topo-tree';
import { EFieldType } from '@/components/retrieval-filter/typing';
import { useHostStore } from '@/store/modules/host';

import type { CompareTarget } from '../types/aggregation';
import type { EHostQuickCategory } from '../types/host-list';
import type { IHostTopoViewRow } from './use-host-topo-tree-worker';
export const useHostUrlParams = () => {
  const hostStore = useHostStore();

  const router = useRouter();
  const route = useRoute();
  let legacyResolveVersion = 0;
  let legacyResolvePending = false;
  onScopeDispose(() => {
    legacyResolveVersion += 1;
  });

  const urlParams = computed(() => {
    return {
      scene: hostStore.scene,
      where: encodeURIComponent(JSON.stringify(hostStore.where)),
      filterExpanded: String(hostStore.filterExpanded),
      activeCategory: hostStore.activeCategory,
      keyword: hostStore.keyword,
      from: hostStore.timeRange[0],
      to: hostStore.timeRange[1],
      timezone: hostStore.timezone,
      refreshInterval: hostStore.refreshInterval.toString(),
      /** 当前选中的拓扑节点 ID */
      nodeId: hostStore.nodeId,
      /** 当前激活的内容 Tab */
      activeTab: hostStore.activeTab,
      /** 指标汇聚 Toolbar 状态（JSON 编码） */
      metricAggregationState: encodeURIComponent(JSON.stringify(hostStore.metricAggregationState)),
      /** 当前选中的主机进程名称（用于恢复进程详情选中状态） */
      hostProcessName: hostStore.hostProcessName,
      /** 主机进程详情侧栏指标视图 Toolbar 状态（JSON 编码） */
      processMetricAggregationState: encodeURIComponent(JSON.stringify(hostStore.processMetricAggregationState)),
      /** 进程列表搜索关键词（同步到 URL） */
      hostProcessKeyword: hostStore.hostProcessKeyword,
    };
  });

  function readLegacyIpv4Host() {
    const fromQuery = splitLegacyIpv4HostId(String(route.query[LEGACY_IPV4_QUERY] || ''));
    if (fromQuery) return fromQuery;
    const rawId = String(route.params.id || '');
    if (!rawId || isBkHostId(rawId)) return null;
    return splitLegacyIpv4HostId(rawId);
  }

  /** 页面打开后再把 ip-云区域换成 bk_host_id，失败时退回列表并用 IP 当关键字。 */
  async function resolveLegacyIpv4Host(ip: string, cloudId: string) {
    const version = ++legacyResolveVersion;
    legacyResolvePending = true;
    let bkHostId = '';
    try {
      const data = (await getHostInfo({ ip, bk_cloud_id: cloudId })) as null | { bk_host_id?: number | string };
      const id = data?.bk_host_id == null ? '' : String(data.bk_host_id);
      if (isBkHostId(id)) bkHostId = id;
    } catch {
      bkHostId = '';
    }
    if (version !== legacyResolveVersion) return;
    if (bkHostId) {
      hostStore.nodeId = bkHostId;
      const query: Record<string, string> = {};
      Object.entries({ ...route.query, ...urlParams.value }).forEach(([key, value]) => {
        const text = queryText(value);
        if (!text || key === LEGACY_IPV4_QUERY) return;
        query[key] = text;
      });
      await router.replace({
        path: `/trace/host/${bkHostId}`,
        query,
      });
      legacyResolvePending = false;
      return;
    }
    legacyResolvePending = false;
    if (!hostStore.keyword) hostStore.keyword = ip;
    setUrlParams();
  }

  function setUrlParams(otherParams: Record<string, unknown> = {}) {
    if (legacyResolvePending) return;
    const queryParams = {
      ...route.query,
      ...urlParams.value,
      ...otherParams,
    };
    if (!legacyResolvePending) delete queryParams[LEGACY_IPV4_QUERY];
    const targetRoute = router.resolve({
      query: queryParams,
    });
    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.fullPath !== route.fullPath) {
      router.replace({
        query: queryParams,
      });
    }
  }

  /**
   * 从 URL query 参数恢复主机列表过滤状态到 store
   *
   * 支持两种 URL 格式：
   * 1. 新版格式：where 参数（JSON 编码的 IWhereItem[]）
   * 2. 旧版格式：search 参数（旧版搜索条件），自动转换为 where 格式以保持向后兼容
   *
   * 同时支持 panelKey → activeCategory 的映射兼容（旧版面板 key 到新版快捷分类）
   */
  function getUrlParams() {
    const {
      filterExpanded,
      activeCategory,
      panelKey,
      queryString,
      keyword,
      from,
      to,
      timezone,
      refreshInterval,
      nodeId,
      activeTab,
      dashboardId,
      hostProcessName,
      hostProcessKeyword,
    } = route.query;
    const legacyIpv4 = readLegacyIpv4Host();
    if (legacyIpv4) {
      hostStore.nodeId = '';
      void resolveLegacyIpv4Host(legacyIpv4.ip, legacyIpv4.cloudId);
    } else {
      hostStore.nodeId = (nodeId || route.params.id || '') as string;
    }
    hostStore.activeTab = queryText(activeTab) || legacyDashboardTab(dashboardId);
    getWhereParams();
    hostStore.keyword = (keyword || queryString || '') as string;
    hostStore.filterExpanded = filterExpanded === 'true' || !!hostStore.where.length;
    getMetricAggregationState();
    // 兼容旧版本面板key
    const panelKeyMap = {
      unresolveData: 'alarm',
      cpuData: 'cpu',
      menmoryData: 'mem',
      diskData: 'disk',
    };
    hostStore.activeCategory = (activeCategory || panelKeyMap?.[panelKey as string] || '') as '' | EHostQuickCategory;
    hostStore.hostProcessName = queryText(hostProcessName);
    /** 恢复进程列表搜索关键词 */
    hostStore.hostProcessKeyword = (hostProcessKeyword || '') as string;
    hostStore.timeRange = from && to ? [from as string, to as string] : ['now-1h', 'now'];
    hostStore.timezone = (timezone as string) || window.timezone;
    hostStore.refreshInterval = parseInt(refreshInterval as string, 10) || -1;
  }

  function getWhereParams() {
    const { where, search } = route.query;
    if (where) {
      hostStore.where = tryURLDecodeParse(where as string, []);
    } else {
      // 兼容旧版本
      const keyWordFields = HOST_FILTER_FIELDS.filter(f => f.type === EFieldType.keyword).map(f => f.name);
      const textFields = HOST_FILTER_FIELDS.filter(f => f.type === EFieldType.text).map(f => f.name);
      const numberInputFields = HOST_FILTER_FIELDS.filter(f => f.type === EFieldType.numberInput).map(f => f.name);
      const searchWhere = tryURLDecodeParse(search as string, []);
      const newWhere = [];
      for (const w of searchWhere) {
        if ([...textFields, ...keyWordFields].includes(w.id)) {
          newWhere.push({
            key: w.id,
            condition: 'and',
            value: typeof w.value === 'string' ? [w.value] : w.value,
            method: textFields.includes(w.id) ? 'include' : 'eq',
          });
        } else if (numberInputFields.includes(w.id)) {
          for (const v of w.value) {
            newWhere.push({
              key: w.id,
              condition: 'and',
              value: typeof v.value === 'string' ? [v.value] : v.value,
              method: NUMBER_METHODS.find(m => m.alias === v.condition)?.value || 'eq',
            });
          }
        } else if (w.id === 'cluster_module') {
          newWhere.push({
            key: w.id,
            condition: 'and',
            value: w.value.map(v => JSON.stringify(v)),
            method: 'eq',
          });
        } else {
          newWhere.push({
            key: w.id,
            condition: 'and',
            value: typeof w.value === 'string' ? [w.value] : w.value,
            method: 'eq',
          });
        }
      }
      hostStore.where = newWhere;
    }
  }

  /**
   * 从 URL query 参数恢复指标汇聚状态到 store
   *
   * 支持从 URL 恢复以下汇聚配置：
   * - metricAggregationState: 完整的汇聚状态 JSON
   * - method / interval: 汇聚方法和间隔
   * - compares / timeOffset: 对比目标（按目标对比或时间偏移对比）
   */
  function getMetricAggregationState() {
    const { metricAggregationState, processMetricAggregationState, compares, timeOffset, method, interval } =
      route.query;
    const paramsFn = () => {
      return {
        ...(() => {
          const obj: any = {};
          if (method) {
            obj.method = method;
          }
          if (interval) {
            obj.interval = interval;
          }
          return obj;
        })(),
        ...(() => {
          const queryCompares: any = tryURLDecodeParse(compares as string, {});
          const queryTimeOffset = tryURLDecodeParse(timeOffset as string, []);
          const targets: CompareTarget[] = queryCompares?.targets;
          if (targets?.length) {
            return {
              compareType: 'target',
              compareTargets: targets,
            };
          }
          if (queryTimeOffset?.length) {
            return {
              compareType: 'time',
              timeShift: queryTimeOffset,
            };
          }
          return {};
        })(),
      };
    };
    Object.assign(hostStore.metricAggregationState, {
      ...tryURLDecodeParse(metricAggregationState as string, {}),
      ...paramsFn(),
    });
    Object.assign(hostStore.processMetricAggregationState, {
      ...tryURLDecodeParse(processMetricAggregationState as string, {}),
      ...paramsFn(),
    });
  }

  /**
   * 处理拓扑节点选中事件
   *
   * 当用户在拓扑树中选中节点时：
   * 1. 更新 store 中的当前节点 ID
   * 2. 重置指标汇聚状态为默认值（保留已配置的列）
   * 3. 如果选中的是主机节点，清空过滤条件、快捷分类和搜索关键词
   */
  function handleSelectNode(node: IHostTopoViewRow) {
    hostStore.nodeId = node.id;
    Object.assign(hostStore.metricAggregationState, {
      ...JSON.parse(JSON.stringify(DEFAULT_AGGREGATION_STATE)),
      columns: hostStore.metricAggregationState.columns,
    });
    hostStore.hostProcessName = '';
    /** 切换节点时清空进程搜索关键词 */
    hostStore.hostProcessKeyword = '';
    if (isHostNode(node)) {
      hostStore.where = [];
      hostStore.activeCategory = '';
      hostStore.keyword = '';
    }
  }

  // 列表页和 legacyIpv4 详情是同一条 /host 路由，组件会复用，需要在查询参数出现时再解析。
  watch(
    () => {
      const fromQuery = queryText(route.query[LEGACY_IPV4_QUERY]);
      if (fromQuery) return fromQuery;
      const rawId = queryText(route.params.id);
      if (!rawId || isBkHostId(rawId)) return '';
      return rawId;
    },
    value => {
      const legacy = splitLegacyIpv4HostId(value);
      if (!legacy) return;
      void resolveLegacyIpv4Host(legacy.ip, legacy.cloudId);
    }
  );

  // 主机页路由组件会复用。再次进入详情时，用地址上的页签和进程名覆盖列表页留下的 store。
  watch(
    () =>
      [
        queryText(route.params.id),
        queryText(route.query.activeTab),
        queryText(route.query.dashboardId),
        queryText(route.query.hostProcessName),
      ].join('\n'),
    () => {
      const nextTab = queryText(route.query.activeTab) || legacyDashboardTab(route.query.dashboardId);
      if (nextTab) hostStore.activeTab = nextTab;
      hostStore.hostProcessName = queryText(route.query.hostProcessName);
    }
  );

  return {
    urlParams,
    setUrlParams,
    getUrlParams,
    handleSelectNode,
  };
};

const queryText = (value: unknown) => {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw == null ? '' : String(raw);
};

/** 旧版 dashboardId=host|process 对应新版详情页签。 */
const legacyDashboardTab = (dashboardId: unknown) => {
  const value = queryText(dashboardId);
  if (value === 'host') return 'system';
  if (value === 'process') return 'process';
  return '';
};
