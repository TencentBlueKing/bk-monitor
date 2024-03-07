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
import * as AlarmGroupAuth from 'monitor-pc/pages/alarm-group/authority-map';

const AlarmGroup = () => import(/* webpackChunkName: "AlarmGroup" */ '../../../pages/alarm-group/alarm-group');
const AlarmGroupAdd = () =>
  import(/* webpackChunkName: "AlarmGroupAdd" */ '../../../pages/alarm-group/alarm-group-add/alarm-group-add');

export default [
  {
    path: '/alarm-group',
    name: 'alarm-group',
    props: true,
    components: {
      noCache: AlarmGroup
    },
    meta: {
      title: '告警组',
      navId: 'alarm-group',
      route: {
        parent: 'manager'
      },
      authority: {
        map: AlarmGroupAuth,
        page: AlarmGroupAuth.VIEW_AUTH
      },
      noNavBar: true
    }
  },
  {
    path: '/alarm-group-add',
    name: 'alarm-group-add',
    props: true,
    components: {
      noCache: AlarmGroupAdd
    },
    meta: {
      title: '新增告警组',
      navId: 'alarm-group',
      needBack: true,
      route: {
        parent: 'alarm-group'
      },
      authority: {
        map: AlarmGroupAuth,
        page: AlarmGroupAuth.MANAGE_AUTH
      }
    }
  },
  {
    path: '/alarm-group/edit/:id',
    name: 'alarm-group-edit',
    components: {
      noCache: AlarmGroupAdd
    },
    props: {
      noCache: true
    },
    meta: {
      title: '编辑告警组',
      navId: 'alarm-group',
      needBack: true,
      needCopyLink: true,
      route: {
        parent: 'alarm-group'
      },
      authority: {
        map: AlarmGroupAuth,
        page: AlarmGroupAuth.MANAGE_AUTH
      }
    }
  }
] as RouteConfig[];
