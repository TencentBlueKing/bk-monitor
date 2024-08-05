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
import * as functionAuth from '../../pages/function-switch/authority-map';
import externalAuthRoutes from './external-auth';
import noBusinessRoutess from './no-business';
import shareRoutes from './share';

import type { RouteConfig } from 'vue-router';

const ExceptionPage = () =>
  import(/* webpackChunkName: 'ExceptionPage' */ '../../pages/exception-page/exception-page.vue');
const FunctionSwitch = () =>
  import(/* webpackChunkName: 'FunctionSwitch' */ '../../pages/function-switch/function-switch.vue');
const ViewDetail = () => import(/* webpackChunkName: 'ViewDetail' */ '../../pages/view-detail/view-detail.vue');
const MigrateDashboard = () =>
  import(/* webpackChunkName: 'MigrateDashboard' */ '../../pages/migrate-dashboard/migrate-dashboard.vue');
export default [
  ...noBusinessRoutess,
  ...(window.__POWERED_BY_BK_WEWEB__ ? [] : shareRoutes),
  ...externalAuthRoutes,
  {
    path: '/migrate-dashboard',
    name: 'migrate-dashboard',
    components: {
      noCache: MigrateDashboard,
    },
    meta: {
      title: '迁移工具',
      navId: 'migrate-dashboard',
    },
  },
  {
    path: '/function-switch',
    name: 'function-switch',
    components: {
      noCache: FunctionSwitch,
    },
    meta: {
      title: '功能开关',
      navId: 'function-switch',
      authority: {
        map: functionAuth,
        page: functionAuth.VIEW_AUTH,
      },
    },
  },
  {
    path: '/exception/:type?/:queryUid?',
    name: 'error-exception',
    component: ExceptionPage,
    props: true,
    beforeEnter(to, from, next) {
      to.meta.title = to.params.type === '403' ? '无权限' : to.params.title || to.params.type || '404';
      next();
    },
    meta: {
      title: '404',
      navId: 'exception',
      noNavBar: true,
    },
  },
  {
    path: '/view-detail',
    name: 'view-detail',
    components: {
      noCache: ViewDetail,
    },
    meta: {
      title: '视图详情',
      navId: 'view-detail',
    },
  },
] as RouteConfig[];
