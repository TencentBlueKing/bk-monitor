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

// import * as rotation from '../../pages/rotation/authority-map';
import * as AlarmGroupAuth from '../../pages/alarm-group/authority-map';

import type { RouteConfig } from 'vue-router';

const Rotation = () => import(/* webpackChunkName: 'Rotation' */ '../../pages/rotation/rotation');
export default [
  {
    path: '/trace/rotation',
    name: 'rotation',
    components: {
      noCache: Rotation,
    },
    meta: {
      title: '轮值',
      navId: 'rotation',
      noNavBar: true,
      route: {
        parent: 'manager',
      },
      authority: {
        map: AlarmGroupAuth,
        page: [AlarmGroupAuth.VIEW_AUTH],
      },
    },
  },
  {
    path: '/trace/rotation/add',
    name: 'rotation-add',
    components: {
      noCache: Rotation,
    },
    meta: {
      title: '新增轮值',
      needBack: true,
      navId: 'rotation',
      // authority: {
      //   map: alarmShieldAuth,
      //   page: [alarmShieldAuth.MANAGE_AUTH]
      // },
      route: {
        parent: 'rotation',
      },
      noNavBar: true,
    },
  },
  {
    path: '/trace/rotation/edit/:id',
    name: 'rotation-edit',
    components: {
      noCache: Rotation,
    },
    meta: {
      title: '编辑轮值',
      needBack: true,
      needCopyLink: false,
      navId: 'rotation',
      // authority: {
      //   map: alarmShieldAuth,
      //   page: [alarmShieldAuth.MANAGE_AUTH]
      // },
      route: {
        parent: 'rotation',
      },
      noNavBar: true,
    },
  },
] as RouteConfig[];
