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

import { applyGuidePage } from '../../common';
import { redirectLegacyHostRoute } from '../../common/legacy-host-url';
import * as performanceAuth from '../../pages/performance/authority-map';
import { beforeEnter } from '../utils';

import type { RouteConfig } from 'vue-router';

const Host = () => import(/* webpackChunkName: 'Host' */ '../../pages/host/host');

export default applyGuidePage(
  [
    {
      path: '/performance',
      name: 'performance',
      beforeEnter: redirectLegacyHostRoute,
      meta: {
        title: '主机监控',
        navId: 'host',
        noChangeLoading: true,
        authority: {
          page: performanceAuth.VIEW_AUTH,
        },
        route: {
          parent: 'scenes',
        },
      },
    },
    {
      path: '/trace/host/:id?',
      name: 'host',
      components: {
        noCache: Host,
      },
      // navId 保持 host；引导数据复用 performance，进入前单独拉取 introduce
      beforeEnter: (_to, _from, next) => beforeEnter('performance', next),
      meta: {
        title: '主机监控',
        navId: 'host',
        navClass: 'host-retrieval-nav',
        noChangeLoading: true,
        noNavBar: true,
        route: {
          parent: 'scenes',
        },
        authority: {
          map: performanceAuth,
          page: performanceAuth.VIEW_AUTH,
        },
      },
    },
    {
      path: '/performance/detail/:id/:process?',
      name: 'performance-detail',
      beforeEnter: redirectLegacyHostRoute,
      meta: {
        title: '主机监控',
        navId: 'host',
        noChangeLoading: true,
        authority: {
          map: performanceAuth,
          page: performanceAuth.VIEW_AUTH,
        },
        route: {
          parent: 'scenes',
        },
      },
    },
    {
      path: '/performance/detail-new/:id/:process?',
      name: 'performance-detail-new',
      beforeEnter: redirectLegacyHostRoute,
      meta: {
        title: '主机监控',
        navId: 'host',
        noChangeLoading: true,
        authority: {
          map: performanceAuth,
          page: performanceAuth.VIEW_AUTH,
        },
        route: {
          parent: 'scenes',
        },
      },
    },
  ] as RouteConfig[],
  ['host', 'performance', 'performance-detail', 'performance-detail-new']
);
