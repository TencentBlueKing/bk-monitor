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

import * as reportAuth from '../../pages/new-report/authority-map';

import type { RouteConfig } from 'vue-router';

const Report = () => import(/* webpackChunkName: 'NewReport' */ '../../pages/new-report/new-report');
const MyReport = () => import(/* webpackChunkName: 'MyReport' */ '../../pages/my-subscription/my-subscription-iframe');
const MyAppliedReport = () => import(/* webpackChunkName: 'MyAppliedReport' */ '../../pages/my-apply/my-apply-iframe');
export default [
  {
    path: '/trace/report',
    name: 'report',
    components: {
      noCache: Report,
    },
    meta: {
      title: '邮件订阅',
      navId: 'report',
      noNavBar: true,
      authority: {
        map: reportAuth,
        page: [reportAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'manager',
      },
    },
  },
  {
    path: '/trace/report/create',
    name: 'create-report',
    components: {
      noCache: Report,
    },
    meta: {
      title: '新建订阅',
      needBack: true,
      navId: 'report',
      authority: {
        map: reportAuth,
        page: [reportAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'report',
      },
      noNavBar: true,
    },
  },
  // 20240229 该 我的订阅 页面作为 iframe 嵌入到 日志平台 展示
  {
    path: '/trace/report/my-report',
    name: 'my-report',
    components: {
      noCache: MyReport,
    },
    meta: {
      title: '我的订阅',
      needBack: true,
      navId: 'report',
      route: {
        parent: 'report',
      },
      noNavBar: true,
    },
  },
  // 20240229 该 我的申请 页面作为 iframe 嵌入到 日志平台 展示
  {
    path: '/trace/report/my-applied-report',
    name: 'my-applied-report',
    components: {
      noCache: MyAppliedReport,
    },
    meta: {
      title: '我的申请',
      needBack: true,
      navId: 'report',
      route: {
        parent: 'report',
      },
      noNavBar: true,
    },
  },
] as RouteConfig[];
