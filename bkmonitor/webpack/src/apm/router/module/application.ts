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
import type { RouteConfig } from 'vue-router';

const Application = () => import(/* webpackChunkName: "application" */ '../../pages/application/application');
const ApplicationDetail = () =>
  import(/* webpackChunkName: "application-detial" */ '../../pages/application/application-detail');
const AppAdd = () => import(/* webpackChunkName: "AppAdd" */ '../../pages/home/add-app/add-app');
const NoDataGuide = () => import(/* webpackChunkName: "NoDataGuide" */ '../../pages/application/app-add/no-data-guide');
const AppConfig = () =>
  import(/* webpackChunkName: "applicationConfiguration" */ '../../pages/application/app-configuration/configuration');
export default [
  {
    path: '/application',
    name: 'application',
    props: {
      noCache: true,
    },
    components: {
      noCache: Application,
    },
    meta: {
      title: 'APM',
      navId: 'application',
      customTitle: true,
      noNavBar: true,
      route: {
        parent: 'application',
      },
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // }
    },
  },
  {
    path: '/application/detail',
    name: 'application-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: ApplicationDetail,
    },
    meta: {
      title: '应用详情',
      navId: 'application',
      customTitle: true,
      noNavBar: true,
      route: {
        parent: 'application',
      },
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // }
    },
  },
  {
    path: '/application/add',
    name: 'application-add',
    props: {
      noCache: true,
    },
    components: {
      noCache: AppAdd,
    },
    meta: {
      title: '新建应用',
      navId: 'application',
      needBack: true,
      noNavBar: true,
    },
  },
  {
    path: '/application/config/:appName',
    name: 'application-config',
    props: {
      noCache: true,
    },
    components: {
      noCache: AppConfig,
    },
    meta: {
      title: '应用配置',
      navId: 'application',
      noNavBar: true,
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // }
    },
  },
  {
    path: '/application/empty',
    name: 'application-empty',
    props: true,
    components: {
      noCache: NoDataGuide,
    },
    meta: {
      title: '无数据指引',
      navId: 'application',
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // },
      needBack: true,
      noNavBar: true,
    },
  },
] as RouteConfig[];
