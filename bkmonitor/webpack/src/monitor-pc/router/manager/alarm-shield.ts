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

import * as alarmShieldAuth from '../../pages/alarm-shield/authority-map';

import type { RouteConfig } from 'vue-router';

const AlarmShield = () => import(/* webpackChunkName: 'AlarmShield' */ '../../pages/alarm-shield/alarm-shield');
// const AlarmShieldConfigSet = () =>
//   import(/* webpackChunkName: 'AlarmShieldConfigSet' */ '../../pages/alarm-shield/alarm-shield-set');
// const AlarmShieldDetail = () =>
//   import(/* webpackChunkName: 'AlarmShieldDetail' */ '../../pages/alarm-shield/alarm-shield-detail');
export default [
  {
    path: '/trace/alarm-shield',
    name: 'alarm-shield',
    components: {
      noCache: AlarmShield,
    },
    meta: {
      title: '告警屏蔽',
      navId: 'alarm-shield',
      noNavBar: true,
      route: {
        parent: 'manager',
      },
      authority: {
        map: alarmShieldAuth,
        page: alarmShieldAuth.VIEW_AUTH,
      },
    },
  },
  {
    path: '/trace/alarm-shield/add',
    name: 'alarm-shield-add',
    components: {
      noCache: AlarmShield,
    },
    meta: {
      title: '新建屏蔽',
      needBack: true,
      navId: 'alarm-shield',
      authority: {
        map: alarmShieldAuth,
        page: [alarmShieldAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'alarm-shield',
      },
      noNavBar: true,
    },
  },
  {
    path: '/trace/alarm-shield/clone/:id',
    name: 'alarm-shield-clone',
    components: {
      noCache: AlarmShield,
    },
    meta: {
      title: '克隆屏蔽',
      needBack: true,
      needCopyLink: false,
      navId: 'alarm-shield',
      authority: {
        map: alarmShieldAuth,
        page: [alarmShieldAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'alarm-shield',
      },
      noNavBar: true,
    },
  },
  {
    path: '/trace/alarm-shield/edit/:id',
    name: 'alarm-shield-edit',
    components: {
      noCache: AlarmShield,
    },
    meta: {
      title: '编辑屏蔽',
      needBack: true,
      needCopyLink: false,
      navId: 'alarm-shield',
      authority: {
        map: alarmShieldAuth,
        page: [alarmShieldAuth.MANAGE_AUTH],
      },
      route: {
        parent: 'alarm-shield',
      },
      noNavBar: true,
    },
  },
  // {
  //   path: '/alarm-shield-detail/:id',
  //   name: 'alarm-shield-detail',
  //   props: true,
  //   components: {
  //     noCache: AlarmShield
  //   },
  //   beforeEnter(to, from, next) {
  //     if (!to.params.id) {
  //       next({ path: '/alarm-shield' });
  //     } else {
  //       to.meta.title = to.params.id || '告警详情';
  //       next();
  //     }
  //     next();
  //   },
  //   meta: {
  //     title: '告警详情',
  //     navId: 'alarm-shield',
  //     authority: {
  //       map: alarmShieldAuth,
  //       page: [alarmShieldAuth.VIEW_AUTH]
  //     },
  //     noNavBar: true
  //   }
  // },
] as RouteConfig[];
