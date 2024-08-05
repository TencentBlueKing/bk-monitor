/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import * as performanceAuth from '../../pages/performance/authority-map';

import type { RouteConfig } from 'vue-router';

const Performance = () => import(/* webpackChunkName: 'Performance' */ '../../pages/performance/performance-wrapper');
const PerformanceDetail = () =>
  import(/* webpackChunkName: 'PerformanceDetail' */ '../../pages/performance/performance-detail/performance-detail');
export default applyGuidePage([
  {
    path: '/performance',
    name: 'performance',
    props: {
      noCache: true,
    },
    components: {
      noCache: Performance,
    },
    meta: {
      title: '主机监控',
      navId: 'performance',
      authority: {
        page: performanceAuth.VIEW_AUTH,
      },
      route: {
        parent: 'scenes',
      },
      noNavBar: true,
    },
  },
  {
    path: '/performance/detail/:id/:process?',
    name: 'performance-detail',
    components: {
      noCache: PerformanceDetail,
    },
    props: {
      noCache: true,
    },
    meta: {
      needBack: true,
      navId: 'performance',
      authority: {
        map: performanceAuth,
        page: performanceAuth.VIEW_AUTH,
      },
      customContent: true,
      noNavBar: true,
      route: {
        parent: 'performance',
      },
    },
  },
  {
    path: '/performance/detail-new/:id/:process?',
    name: 'performance-detail-new',
    components: {
      noCache: PerformanceDetail,
    },
    props: {
      noCache: true,
    },
    meta: {
      needBack: true,
      navId: 'performance',
      authority: {
        map: performanceAuth,
        page: performanceAuth.VIEW_AUTH,
      },
      customContent: true,
      noNavBar: true,
      route: {
        parent: 'performance',
      },
    },
  },
] as RouteConfig[]);
