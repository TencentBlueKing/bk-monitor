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
import {
  type HostMonitorQuery,
  type LegacyHostRoute,
  hostMonitorHash,
  LEGACY_IPV4_QUERY,
  parseAppHash,
  planLegacyHostRedirect,
} from 'monitor-common/utils/host-monitor-url';

import type { NavigationGuard } from 'vue-router';

/** 旧版列表/详情路由转换成新版 /trace/host，不发起主机查询。 */
export const resolveLegacyHostTarget = (to: LegacyHostRoute) => planLegacyHostRedirect(to);

export const resolveLegacyHostHash = (input: { id?: string; processName?: string; query?: HostMonitorQuery }) => {
  const id = input.id ? String(input.id) : '';
  return hostMonitorHash(
    resolveLegacyHostTarget({
      path: id ? '/performance/detail/placeholder' : '/performance',
      params: { id, process: input.processName || '' },
      query: input.query,
    })
  );
};

/** 把仍指向旧版、或带 legacyIpv4 的 hash 换成可立即打开的新版 hash。 */
export const finalizeHostMonitorHash = (hash: string) => {
  const normalized = hash.startsWith('#') ? hash : `#${hash}`;
  const { path, query } = parseAppHash(normalized);
  if (path.startsWith('/performance/detail')) {
    const match = /^\/performance\/detail(?:-new)?\/([^/?#]+)(?:\/([^/?#]+))?/.exec(path);
    return resolveLegacyHostHash({
      id: match?.[1] ? decodeURIComponent(match[1]) : '',
      processName: match?.[2] ? decodeURIComponent(match[2]) : '',
      query,
    });
  }
  if (path === '/performance') return resolveLegacyHostHash({ query });
  if (query[LEGACY_IPV4_QUERY]) return resolveLegacyHostHash({ id: query[LEGACY_IPV4_QUERY], query });
  return normalized;
};

export const finalizeHostMonitorUrl = (url: string) => {
  const hashIndex = url.indexOf('#');
  if (hashIndex === -1) return url;
  return `${url.slice(0, hashIndex)}${finalizeHostMonitorHash(url.slice(hashIndex))}`;
};

export const redirectLegacyHostRoute: NavigationGuard = (to, _from, next) => {
  const target = resolveLegacyHostTarget({
    path: to.path,
    params: { id: to.params.id, process: to.params.process },
    query: to.query as HostMonitorQuery,
  });
  next({ path: target.path, query: target.query, replace: true });
};
