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

import { tryURLDecodeParse } from 'monitor-common/utils';

import { K8sNewTabEnum, SceneEnum } from '../../pages/monitor-k8s/typings/k8s-new';
import { EMode } from '../retrieval-filter/utils';

import type { K8sMonitorInitialParams, K8sMonitorState, K8sMonitorUrlParseResult } from './typings';

/** 容器监控（新版）的路由路径，后端生成的跳转链接以此为判据 */
export const K8S_MONITOR_ROUTE_PATH = '/k8s-new';

/**
 * @description 将容器监控视图状态序列化为 URL query
 */
export function buildK8sMonitorQuery(state: K8sMonitorState): Record<string, string> {
  const commonQuery = {
    sceneId: 'kubernetes',
    from: state.timeRange[0],
    to: state.timeRange[1],
    refreshInterval: String(state.refreshInterval),
    scene: state.scene,
    cluster: state.cluster,
  };

  if (state.scene === SceneEnum.Event) {
    return {
      ...commonQuery,
      /** 因存在内部跳转功能，所以使用事件检索URL格式 */
      targets: JSON.stringify([
        {
          data: {
            query_configs: [{ where: state.where, query_string: state.queryString }],
          },
        },
      ]),
      filterMode: state.filterMode,
    };
  }

  return {
    ...commonQuery,
    filterBy: JSON.stringify(state.filterBy),
    groupBy: JSON.stringify(state.groupBy),
    activeTab: state.activeTab,
  };
}

/**
 * @description 解析容器监控的 URL query 为结构化参数
 * 这里是 URL 契约的唯一解析点，路由页、侧滑、用户配置缓存三方共用
 */
export function parseK8sMonitorQuery(query: Record<string, any> = {}): K8sMonitorInitialParams {
  const {
    from = 'now-1h',
    to = 'now',
    refreshInterval = '-1',
    filterBy,
    groupBy,
    cluster = '',
    scene = SceneEnum.Performance,
    activeTab = K8sNewTabEnum.LIST,
    targets,
    filterMode,
  } = query;

  const params: K8sMonitorInitialParams = {
    timeRange: [from as string, to as string],
    refreshInterval: Number(refreshInterval),
    cluster: cluster as string,
    scene: scene as SceneEnum,
  };

  if (scene === SceneEnum.Event) {
    // 事件场景沿用事件检索的 targets 结构，仅取其中的 where / query_string
    const [firstTarget] = tryURLDecodeParse<any[]>(targets as string, []);
    const queryConfig = firstTarget?.data?.query_configs?.[0];
    params.filterMode = (filterMode as EMode) || EMode.ui;
    params.where = queryConfig?.where || [];
    params.queryString = queryConfig?.query_string || '';
  } else {
    params.activeTab = activeTab as K8sNewTabEnum;
    params.groupBy = tryURLDecodeParse<string[]>(groupBy as string, []);
    params.filterBy = tryURLDecodeParse<Record<string, string[]>>(filterBy as string, {});
  }

  return params;
}

/**
 * @description 解析后端下发的跳转链接，判断是否指向容器监控
 * @param url 形如 {host}?bizId=2#/k8s-new?cluster=xxx&filterBy=xxx 的绝对或相对链接
 *
 * 判据只看 hash 路径，不比对业务 id：业务 id 在主应用与 APM 子应用里的取值口径不一致，
 * 拿它做闸门会让子应用里的容器链接静默退回新开页。
 */
export function parseK8sMonitorUrl(url: string): K8sMonitorUrlParseResult {
  const fallback: K8sMonitorUrlParseResult = { isK8sMonitor: false, bizId: '', params: {} };
  if (!url) return fallback;

  let parsed: URL;
  try {
    parsed = new URL(url, location.origin);
  } catch {
    return fallback;
  }

  const hash = parsed.hash.replace(/^#/, '');
  const [rawPath, hashSearch = ''] = hash.split('?');
  // 容忍尾斜杠，仓库里存在 #/k8s-new/?... 形式的链接
  if (rawPath.replace(/\/+$/, '') !== K8S_MONITOR_ROUTE_PATH) return fallback;

  return {
    isK8sMonitor: true,
    bizId: parsed.searchParams.get('bizId') || '',
    params: parseK8sMonitorQuery(Object.fromEntries(new URLSearchParams(hashSearch))),
  };
}
