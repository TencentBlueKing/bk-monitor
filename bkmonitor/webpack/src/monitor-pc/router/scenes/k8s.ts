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
import { VIEW_AUTH } from '../../pages/monitor-k8s/authority-map';

import type { RouteConfig } from 'vue-router';

const MonitorK8sNew = () => import(/* webpackChunkName: 'monitorK8s' */ '../../pages/monitor-k8s/monitor-k8s-new');
const MonitorK8s = () => import(/* webpackChunkName: 'monitorK8s' */ '../../pages/monitor-k8s/monitor-k8s');
// const monitorK8sDetail = () =>
//   import(/* webpackChunkName: 'monitorK8sDetail' */ '../../pages/monitor-k8s/monitor-k8s-detail');
export default applyGuidePage([
  {
    path: '/k8s',
    name: 'k8s',
    props: {
      noCache: true,
    },
    components: {
      noCache: MonitorK8s,
    },
    meta: {
      title: '容器监控',
      navId: 'k8s',
      customTitle: true,
      noNavBar: true,
      needClearQuery: true,
      route: {
        parent: 'scenes',
      },
      authority: {
        page: VIEW_AUTH,
      },
    },
  },
  {
    path: '/k8s-new',
    name: 'k8s-new',
    props: {
      noCache: true,
    },
    components: {
      noCache: MonitorK8sNew,
    },
    meta: {
      title: '容器监控',
      navId: 'k8s-new',
      customTitle: true,
      noNavBar: true,
      needClearQuery: true,
      route: {
        parent: 'scenes',
      },
      authority: {
        page: VIEW_AUTH,
      },
    },
  },
  // {
  //   path: '/k8s/detail',
  //   name: 'k8s-detail',
  //   props: {
  //     noCache: true,
  //   },
  //   components: {
  //     noCache: monitorK8sDetail,
  //   },
  //   meta: {
  //     title: '容器监控详情',
  //     navId: 'k8s',
  //     customTitle: true,
  //     noNavBar: true,
  //     route: {
  //       parent: 'k8s',
  //     },
  //     authority: {
  //       page: VIEW_AUTH,
  //     },
  //   },
  // },
] as RouteConfig[]);
