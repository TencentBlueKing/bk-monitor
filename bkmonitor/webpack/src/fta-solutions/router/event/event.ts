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
import * as eventCenterAuth from 'monitor-pc/pages/event-center/authority-map';

import type { RouteConfig } from 'vue-router';

const Event = () => import(/* webpackChunkName: "Event" */ '../../pages/event/event');
const EventDetail = () => import(/* webpackChunkName: "EventDetail" */ '../../pages/event/event-detail/event-detail');
const ActionDetail = () =>
  import(/* webpackChunkName: "ActionDetail" */ '../../pages/event/event-detail/action-detail');
const isSpecEvent = location.search.indexOf('specEvent') > -1;

export default [
  {
    path: '/event-center',
    name: 'event-center',
    props: {
      noCache: true,
    },
    components: {
      noCache: Event,
    },
    meta: {
      title: '事件',
      navId: 'event-center',
      isFta: true,
      noNavBar: true,
      ...(!isSpecEvent
        ? {
            authorityList: ['view_event_v2'],
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
            },
          }
        : {}),
    },
  },
  {
    path: '/event-center/detail/:id',
    name: 'event-center-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: EventDetail,
    },
    meta: {
      title: '告警详情',
      navId: 'event-center',
      route: {
        parent: 'event-center',
      },
      noNavBar: true,
      ...(!isSpecEvent
        ? {
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
            },
          }
        : {}),
    },
  },
  {
    path: '/event-center/action-detail/:id',
    name: 'event-center-action-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: ActionDetail,
    },
    meta: {
      title: '处理记录详情',
      navId: 'event-center',
      noNavBar: true,
      route: {
        parent: 'event-center',
      },
      ...(!isSpecEvent
        ? {
            authority: {
              page: eventCenterAuth.VIEW_AUTH,
            },
          }
        : {}),
    },
  },
] as RouteConfig[];
