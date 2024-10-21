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
// import * as alarmShieldAuth from '../../pages/alarm-shield/authority-map'
import type { RouteConfig } from 'vue-router';

const EmailSubscriptions = () =>
  import(/* webpackChunkName: 'EmailSubscriptions' */ '../../pages/email-subscriptions/email-subscriptions.vue');
const EmailSubscriptionsSet = () =>
  import(/* webpackChunkName: 'EmailSubscriptionsSet' */ '../../pages/email-subscriptions/email-subscriptions-set.vue');
const EmailSubscriptionsHistory = () =>
  import(
    /* webpackChunkName: 'EmailSubscriptionsHistory' */ '../../pages/email-subscriptions/email-subscriptions-history'
  );
export default [
  {
    path: '/email-subscriptions',
    name: 'email-subscriptions',
    components: {
      noCache: EmailSubscriptions,
    },
    meta: {
      title: window.i18n.tc('route-邮件订阅'),
      navId: 'email-subscriptions',
      navName: '邮件订阅',
      needTitle: true, // 显示侧栏选中的导航标题
      route: {
        parent: 'dashboard',
      },
    },
  },
  {
    path: '/email-subscriptions/history',
    name: 'email-subscriptions-history',
    components: {
      noCache: EmailSubscriptionsHistory,
    },
    meta: {
      title: window.i18n.tc('route-发送历史'),
      navId: 'email-subscriptions-history',
      navName: '邮件订阅',
      needTitle: true,
      route: {
        parent: 'dashboard',
      },
    },
  },
  {
    path: '/email-subscriptions/add',
    name: 'email-subscriptions-add',
    components: {
      noCache: EmailSubscriptionsSet,
    },
    meta: {
      title: '新建订阅',
      navId: 'email-subscriptions',
      navName: '邮件订阅',
      needBack: true,
      route: {
        parent: 'email-subscriptions',
      },
    },
  },
  {
    path: '/email-subscriptions/edit/:id',
    name: 'email-subscriptions-edit',
    components: {
      noCache: EmailSubscriptionsSet,
    },
    props: {
      noCache: true,
    },
    meta: {
      title: '编辑订阅',
      navId: 'email-subscriptions',
      navName: '邮件订阅',
      needBack: true,
      route: {
        parent: 'email-subscriptions',
      },
    },
  },
] as RouteConfig[];
