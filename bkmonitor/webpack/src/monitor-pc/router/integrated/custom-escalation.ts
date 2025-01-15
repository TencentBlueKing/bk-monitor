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

import * as customAuth from '../../pages/custom-escalation/authority-map';

import type { RouteConfig } from 'vue-router';

const CustomEscalationSet = () =>
  import(/* webpackChunkName: 'CustomEscalationAdd' */ '@page/custom-escalation/custom-escalation-set.vue');
const CustomEscalationDetail = () =>
  import(/* webpackChunkName: 'CustomEscalationDetail' */ '@page/custom-escalation/custom-escalation-detail.vue');
const CustomEscalationView = () =>
  import(/* webpackChunkName: 'CustomEscalationView' */ '../../pages/custom-escalation/view-detail/metric-view');
const CustomEscalationEventView = () =>
  import(/* webpackChunkName: 'CustomEscalationEventView' */ '../../pages/custom-escalation/view-detail/event-view');
export default [
  {
    path: '/custom-escalation-set/event',
    name: 'custom-set-event',
    props: {
      noCache: true,
    },
    components: {
      noCache: CustomEscalationSet,
    },
    meta: {
      title: '新建',
      navId: 'custom-event',
      needBack: true,
      authority: {
        map: customAuth,
        page: customAuth.MANAGE_CUSTOM_EVENT,
      },
      route: {
        parent: 'custom-event',
      },
    },
  },
  {
    path: '/custom-escalation-set/timeseries',
    name: 'custom-set-timeseries',
    props: {
      noCache: true,
    },
    components: {
      noCache: CustomEscalationSet,
    },
    meta: {
      title: '新建',
      navId: 'custom-metric',
      needBack: true,
      authority: {
        map: customAuth,
        page: customAuth.MANAGE_CUSTOM_METRIC,
      },
      route: {
        parent: 'custom-metric',
      },
    },
  },
  {
    path: '/custom-escalation-detail/event/:id',
    name: 'custom-detail-event',
    props: {
      noCache: true,
    },
    components: {
      noCache: CustomEscalationDetail,
    },
    meta: {
      title: '详情',
      navId: 'custom-event',
      needBack: true,
      authority: {
        map: customAuth,
        page: customAuth.VIEW_CUSTOM_EVENT,
      },
      route: {
        parent: 'custom-event',
      },
      needCopyLink: true,
      noNavBar: true,
    },
  },
  {
    path: '/custom-escalation-detail/timeseries/:id',
    name: 'custom-detail-timeseries',
    props: {
      noCache: true,
    },
    components: {
      noCache: CustomEscalationDetail,
    },
    meta: {
      title: '详情',
      navId: 'custom-metric',
      needBack: true,
      authority: {
        map: customAuth,
        page: customAuth.VIEW_CUSTOM_METRIC,
      },
      route: {
        parent: 'custom-metric',
      },
      needCopyLink: true,
      noNavBar: true,
    },
  },
  {
    path: '/custom-escalation-view/:id',
    name: 'custom-escalation-view',
    props: {
      noCache: true,
    },
    components: {
      noCache: CustomEscalationView,
    },
    meta: {
      title: '可视化',
      navId: 'custom-metric',
      needBack: true,
      customTitle: true,
      noNavBar: true,
      authority: {
        map: customAuth,
        page: customAuth.VIEW_CUSTOM_METRIC,
      },
      route: {
        parent: 'custom-metric',
      },
    },
  },
  {
    path: '/custom-escalation-event-view/:id',
    name: 'custom-escalation-event-view',
    props: {
      noCache: true,
    },
    components: {
      noCache: CustomEscalationEventView,
    },
    meta: {
      title: '可视化',
      navId: 'custom-event',
      needBack: true,
      customContent: true,
      noNavBar: true,
      authority: {
        map: customAuth,
        page: customAuth.VIEW_CUSTOM_METRIC,
      },
      route: {
        parent: 'custom-event',
      },
    },
  },
] as RouteConfig[];
