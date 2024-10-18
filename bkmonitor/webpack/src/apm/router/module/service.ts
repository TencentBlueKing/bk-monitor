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
// import * as HomeAuth from '../../pages/home/authority-map';
const Service = () => import(/* webpackChunkName: "service" */ '../../pages/service/service');
const ServiceDetail = () => import(/* webpackChunkName: "service-detail" */ '../../pages/service/service-detail');
const ServiceAdd = () => import(/* webpackChunkName: "service-add" */ '../../pages/service/service-add');
const ServiceConfig = () =>
  import(/* webpackChunkName: "ServiceConfig" */ '../../pages/service/service-config/configuration');
export default [
  {
    path: '/service',
    name: 'service',
    props: {
      noCache: true,
    },
    components: {
      noCache: Service,
    },
    meta: {
      title: '服务',
      navId: 'service',
      customTitle: true,
      noNavBar: true,
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // }
    },
  },
  {
    path: '/service/detail',
    name: 'service-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: ServiceDetail,
    },
    meta: {
      title: '服务详情',
      navId: 'service',
      customTitle: true,
      noNavBar: true,
      route: {
        parent: 'service',
      },
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // }
    },
  },
  {
    path: '/service-config',
    name: 'service-config',
    props: true,
    components: {
      noCache: ServiceConfig,
    },
    meta: {
      title: '服务配置',
      navId: 'service',
      noNavBar: true,
      // authority: {
      //   map: HomeAuth,
      //   page: [HomeAuth.VIEW_AUTH]
      // }
    },
  },
  {
    path: '/service-add/:appName',
    name: 'service-add',
    props: {
      noCache: true,
    },
    components: {
      noCache: ServiceAdd,
    },
    meta: {
      title: '接入服务',
      navId: 'service',
      customTitle: false,
      noNavBar: true,
      route: {
        parent: 'service',
      },
    },
  },
] as RouteConfig[];
