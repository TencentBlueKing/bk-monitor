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

import * as ruleAuth from 'fta-solutions/pages/setting/set-meal/authority-map';

import type { RouteConfig } from 'vue-router';

const SetMeal = () => import(/* webpackChunkName: "SetMeal" */ 'fta-solutions/pages/setting/set-meal/set-meal');
const AddSetMeal = () =>
  import(/* webpackChunkName: "AddSetMeal" */ 'fta-solutions/pages/setting/set-meal/set-meal-add/set-meal-add');
export default [
  {
    path: '/set-meal',
    name: 'set-meal',
    props: true,
    component: SetMeal,
    meta: {
      title: '处理套餐',
      navId: 'set-meal',
      customContent: true,
      route: {
        parent: 'manager',
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.VIEW_AUTH,
      },
      noNavBar: true,
    },
  },
  {
    path: '/set-meal/:id',
    name: 'set-meal-detail',
    props: true,
    component: SetMeal,
    meta: {
      title: '处理套餐详情',
      needBack: true,
      customContent: true,
      navId: 'set-meal',
      route: {
        parent: 'manager',
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.VIEW_AUTH,
      },
      needCopyLink: true,
      noNavBar: false,
    },
  },
  {
    path: '/set-meal-add',
    name: 'set-meal-add',
    props: {
      noCache: true,
    },
    components: {
      noCache: AddSetMeal,
    },
    meta: {
      title: '新建套餐',
      navId: 'set-meal',
      customContent: true,
      needBack: true,
      route: {
        parent: 'set-meal',
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.MANAGE_ACTION_CONFIG,
      },
      customPage: true, // 自定义路由页面
    },
  },
  {
    path: '/clone-meal/:id',
    name: 'clone-meal',
    props: {
      noCache: true,
    },
    components: {
      noCache: AddSetMeal,
    },
    meta: {
      title: '新建套餐', // 克隆套餐
      navId: 'set-meal',
      needBack: true,
      route: {
        parent: 'set-meal',
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.MANAGE_ACTION_CONFIG,
      },
      customPage: true,
    },
  },
  {
    path: '/set-meal-edit/:id',
    name: 'set-meal-edit',
    props: {
      noCache: true,
    },
    components: {
      noCache: AddSetMeal,
    },
    meta: {
      title: '编辑套餐',
      navId: 'set-meal',
      needBack: true,
      route: {
        parent: 'set-meal',
      },
      authority: {
        map: ruleAuth,
        page: ruleAuth.MANAGE_ACTION_CONFIG,
      },
      customPage: true,
    },
  },
] as RouteConfig[];
