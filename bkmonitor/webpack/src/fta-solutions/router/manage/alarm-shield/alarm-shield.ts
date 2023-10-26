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
import { RouteConfig } from 'vue-router';

import * as alarmShieldAuth from '../../../../monitor-pc/pages/alarm-shield/authority-map';

const AlarmShield = () => import(/* webpackChunkName: "AlarmShield" */ '../../../pages/alarm-shield/alarm-shield');
const AlarmShieldDetail = () =>
  import(/* webpackChunkName: "AlarmShieldDetail" */ '../../../pages/alarm-shield/alarm-shield-detail');
const AlarmShieldSet = () =>
  import(/* webpackChunkName: "AlarmShieldSet" */ '../../../pages/alarm-shield/alarm-shield-set');

export default [
  {
    path: '/alarm-shield',
    name: 'alarm-shield',
    props: true,
    component: AlarmShield,
    meta: {
      title: '告警屏蔽',
      navId: 'alarm-shield',
      route: {
        parent: 'manage'
      },
      authority: {
        map: alarmShieldAuth,
        page: alarmShieldAuth.VIEW_AUTH
      },
      noNavBar: true
    }
  },
  {
    path: '/alarm-shield-detail/:id',
    name: 'alarm-shield-detail',
    components: {
      noCache: AlarmShieldDetail
    },
    props: {
      noCache: true
    },
    meta: {
      title: '屏蔽详情',
      navId: 'alarm-shield',
      needBack: true,
      needCopyLink: true,
      route: {
        parent: 'alarm-shield'
      },
      authority: {
        map: alarmShieldAuth,
        page: alarmShieldAuth.VIEW_AUTH
      }
    }
  },
  {
    path: '/alarm-shield-add',
    name: 'alarm-shield-add',
    components: {
      noCache: AlarmShieldSet
    },
    meta: {
      title: '新建屏蔽',
      navId: 'alarm-shield',
      needBack: true,
      route: {
        parent: 'alarm-shield'
      },
      authority: {
        map: alarmShieldAuth,
        page: alarmShieldAuth.MANAGE_AUTH
      }
    }
  },
  {
    path: '/alarm-shield-edit/:id/:type',
    name: 'alarm-shield-edit',
    components: {
      noCache: AlarmShieldSet
    },
    meta: {
      title: '编辑屏蔽',
      navId: 'alarm-shield',
      needBack: true,
      needCopyLink: true,
      route: {
        parent: 'alarm-shield'
      },
      authority: {
        map: alarmShieldAuth,
        page: alarmShieldAuth.MANAGE_AUTH
      }
    }
  }
] as RouteConfig[];
