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
import Vue from 'vue';

import Router, { type RouteConfig } from 'vue-router';
Vue.use(Router);
const AlarmInfo = () => import(/* webpackChunkName: "alarm-info" */ '../pages/alarm-info/alarm-info.vue');
const AlarmDetail = () => import(/* webpackChunkName: "alarm-detail" */ '../pages/alarm-detail/alarm-detail.vue');
const EventCenter = () => import(/* webpackChunkName: "event-center" */ '../pages/event-center/event-center.vue');
const TendencyChart = () =>
  import(
    /* webpackChunkName: "tendency-chart" */
    '../pages/tendency-chart/tendency-chart.vue'
  );
const QuickAlarmShield = () =>
  import(
    /* webpackChunkName: "quick-alarm-shield" */
    '../pages/quick-alarm-shield/quick-alarm-shield.vue'
  );

export const routerConfig: RouteConfig[] = [
  {
    path: '/alarm-info',
    name: 'alarm-info',
    props: true,
    component: AlarmInfo,
    meta: {
      title: '告警信息',
    },
  },
  {
    path: '/detail/:id?',
    name: 'alarm-detail',
    props: {
      noCache: true,
    },
    components: {
      noCache: AlarmDetail,
    },
    beforeEnter(to, from, next) {
      to.meta.title = to.params.title || window.i18n.tc('告警详情');
      next();
    },
    meta: {
      title: '告警详情',
    },
  },
  {
    path: '/event-center',
    name: 'event-center',
    component: EventCenter,
    beforeEnter(to, from, next) {
      to.meta.title = to.params.title || '事件中心';
      next();
    },
    meta: {
      title: '事件中心',
    },
  },
  {
    path: '/tendency-chart/:id?',
    name: 'tendency-chart',
    props: true,
    component: TendencyChart,
    beforeEnter(to, from, next) {
      to.meta.title = to.params.title || '趋势图';
      next();
    },
    meta: {
      title: '趋势图',
    },
  },
  {
    path: '/quick-alarm-shield/:eventId?',
    name: 'quick-alarm-shield',
    props: true,
    component: QuickAlarmShield,
    beforeEnter(to, from, next) {
      if (to.params.eventId) {
        to.meta.title = to.params.title || '快捷屏蔽';
        next();
      } else {
        next('/');
      }
    },
    meta: {
      title: '快捷屏蔽',
    },
  },
  {
    path: '*',
    redirect: {
      name: 'alarm-info',
    },
  },
];

const createRouter = () =>
  new Router({
    scrollBehavior: (to, from, savedPosition) => {
      if (savedPosition) {
        return savedPosition;
      }
      return { x: 0, y: 0 };
    },
    mode: 'hash',
    routes: routerConfig,
  });

const router = createRouter();
router.beforeEach((to, from, next) => {
  next();
});
export default router;
