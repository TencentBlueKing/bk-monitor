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

import * as eventCenterAuth from '../../pages/event-center/authority-map';

import type { RouteConfig } from 'vue-router';
// import PageLoading from '../../pages/loading/page-loading';
const EventCenter = () => import(/* webpackChunkName: "Event" */ 'fta-solutions/pages/event/event');
const EventCenterDetail = () =>
  import(/* webpackChunkName: "EventDetail" */ 'fta-solutions/pages/event/event-detail/event-detail');
const ActionDetail = () =>
  import(/* webpackChunkName: "EventDetail" */ 'fta-solutions/pages/event/event-detail/action-detail');
const IncidentDetail = () => import(/* webpackChunkName: "IncidentDetail" */ '../../pages/incident/incident-detail');
// const createAsyncComponent = () => ({
//   component: import(/* webpackChunkName: "Event" */ 'fta-solutions/pages/event/event'),
//   // 异步组件加载时使用的组件
//   loading: PageLoading,
//   // 加载失败时使用的组件
//   error: PageLoading,
//   // 展示加载时组件的延时时间。默认值是 200 (毫秒)
//   delay: 10,
//   // 如果提供了超时时间且组件加载也超时了，
//   // 则使用加载失败时使用的组件。默认值是：`Infinity`
//   timeout: Infinity
// });

const isSpecEvent = location.search.indexOf('specEvent') > -1;
export default [
  {
    path: '/event-center',
    name: 'event-center',
    components: {
      noCache: EventCenter,
    },
    props: {
      noCache: true,
    },
    meta: Object.assign(
      {
        route: {
          parent: 'event',
        },
      },
      {
        title: '事件中心',
        navId: 'event-center',
        navClass: 'event-center-nav',
        noNavBar: true,
        authority: {
          map: eventCenterAuth,
        },
      },
      !isSpecEvent
        ? {
            authorityList: ['view_event_v2'],
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
              map: eventCenterAuth,
            },
          }
        : {}
    ),
  },
  {
    path: '/event-action',
    name: 'event-action',
    components: {
      noCache: EventCenter,
    },
    props: {
      noCache: true,
    },
    meta: Object.assign(
      {
        route: {
          parent: 'event',
        },
      },
      {
        title: '事件中心',
        navId: 'event-center',
        navClass: 'event-center-nav',
        noNavBar: true,
        authority: {
          map: eventCenterAuth,
        },
      },
      !isSpecEvent
        ? {
            authorityList: ['view_event'],
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
              map: eventCenterAuth,
            },
          }
        : {}
    ),
  },
  {
    path: '/event-center/detail/:id',
    name: 'event-center-detail',
    props: true,
    beforeEnter(to, from, next) {
      to.params.id ? next() : next(false);
    },
    component: EventCenterDetail,
    meta: Object.assign(
      {
        route: {
          parent: 'event',
        },
      },
      {
        title: '告警详情',
        navId: 'event-center',
        needBack: true,
        noNavBar: true,
        navClass: 'event-center-nav',
        authority: {
          map: eventCenterAuth,
        },
      },
      !isSpecEvent
        ? {
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
            },
          }
        : {}
    ),
  },
  {
    path: '/event-center/action-detail/:id',
    name: 'event-center-action-detail',
    props: true,
    beforeEnter(to, from, next) {
      to.params.id ? next() : next(false);
    },
    component: ActionDetail,
    meta: Object.assign(
      {
        route: {
          parent: 'event',
        },
      },
      {
        title: '处理记录详情',
        navId: 'event-center',
        needBack: true,
        noNavBar: true,
        navClass: 'event-center-nav',
        authority: {
          map: eventCenterAuth,
        },
      },
      !isSpecEvent
        ? {
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
            },
          }
        : {}
    ),
  },
  {
    path: '/trace/incident/detail/:id?',
    name: 'incident-detail',
    props: {
      noCache: true,
    },
    beforeEnter(to, from, next) {
      to.params.id ? next() : next(false);
    },
    components: {
      noCache: IncidentDetail,
    },
    meta: {
      title: '故障详情',
      navId: 'event-center',
      needBack: true,
      noNavBar: true,
      navClass: 'event-center-nav',
      authority: {
        map: eventCenterAuth,
      },
      route: {
        parent: 'event',
      },
    },
  },
] as RouteConfig[];
