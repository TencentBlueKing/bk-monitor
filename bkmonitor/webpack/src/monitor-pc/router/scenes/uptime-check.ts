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
import * as uptimeAuth from '../../pages/uptime-check/authority-map';

import type { RouteConfig } from 'vue-router';

const UptimeCheckDetail = () =>
  import(
    /* webpackChunkName: 'UptimeCheckDetail' */ '../../pages/uptime-check/uptime-check-task/uptime-check-detail/uptime-check-details'
  );
const UptimeCheckForm = () =>
  import(
    /* webpackChunkName: 'UptimeCheckForm' */ '../../pages/uptime-check/uptime-check-task/uptime-check-form/task-form.vue'
  );
const UptimeCheckNodeEdit = () =>
  import(
    /* webpackChunkName: 'UptimeCheckNodeEdit' */ '../../pages/uptime-check/uptime-check-nodes/uptime-check-node-edit.vue'
  );
const UptimeCheck = () => import(/* webpackChunkName: 'UptimeCheck' */ '../../pages/uptime-check/uptime-check');
export default applyGuidePage([
  {
    path: '/uptime-check/task-detail/:taskId',
    name: 'uptime-check-task-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: UptimeCheckDetail,
    },
    meta: {
      needBack: true,
      noNavBar: true,
      title: '任务详情',
      navId: 'uptime-check',
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.VIEW_AUTH],
      },
      route: {
        parent: 'uptime-check',
      },
    },
  },
  {
    path: '/uptime-check/group-detail/:groupId/:taskId',
    name: 'uptime-check-group-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: UptimeCheckDetail,
    },
    meta: {
      needBack: true,
      noNavBar: true,
      title: '任务详情',
      navId: 'uptime-check',
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.VIEW_AUTH],
      },
      route: {
        parent: 'uptime-check',
      },
    },
  },
  {
    path: '/uptime-check/task-add',
    name: 'uptime-check-task-add',
    // 组件指向 name 为 noCache 的 router-view 。
    components: {
      noCache: UptimeCheckForm,
    },
    meta: {
      needBack: true,
      customContent: true,
      // title: '新建拨测任务',
      navId: 'uptime-check',
      noSpaceCheck: true,
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'uptime-check',
      },
    },
  },
  {
    path: '/uptime-check/task-edit/:id',
    name: 'uptime-check-task-edit',
    // 将 url 中的 params 传入到 noCache 组件里（特指 UptimeCheckForm）
    props: {
      noCache: true,
    },
    // 组件指向 name 为 noCache 的 router-view 。
    components: {
      noCache: UptimeCheckForm,
    },
    meta: {
      needBack: true,
      needCopyLink: false,
      customContent: true,
      // title: '编辑拨测任务',
      navId: 'uptime-check',
      noSpaceCheck: true,
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.VIEW_AUTH],
      },
      route: {
        parent: 'uptime-check',
      },
    },
  },
  {
    path: '/uptime-check/node-add',
    name: 'uptime-check-node-add',
    components: {
      noCache: UptimeCheckNodeEdit,
    },
    meta: {
      needBack: true,
      title: '新建拨测节点',
      navId: 'uptime-check',
      noSpaceCheck: true,
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'uptime-check',
      },
    },
  },
  {
    path: '/uptime-check/node-edit/:id',
    name: 'uptime-check-node-edit',
    props: {
      noCache: true,
    },
    components: {
      noCache: UptimeCheckNodeEdit,
    },
    meta: {
      noSpaceCheck: true,
      needBack: true,
      needCopyLink: false,
      title: '编辑拨测节点',
      navId: 'uptime-check',
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'uptime-check',
      },
    },
  },
  {
    path: '/uptime-check',
    name: 'uptime-check',
    component: UptimeCheck,
    props: true,
    meta: {
      title: '综合拨测',
      navId: 'uptime-check',
      navClass: 'uptime-check-nav',
      authority: {
        map: uptimeAuth,
        page: [uptimeAuth.VIEW_AUTH],
      },
      noNavBar: true,
      route: {
        parent: 'scenes',
      },
    },
  },
] as RouteConfig[]);
