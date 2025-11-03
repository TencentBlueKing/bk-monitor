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

// 嵌套路由视图组件声明（用于实现多层嵌套路由结构时，多级 children 路由的占位）
const DashboardTempView = () => import(/* webpackChunkName: 'dashboard' */ '@/views/dashboard/index');

// 仪表盘模块各组件异步声明（用于路由懒加载）
const home = () => import(/* webpackChunkName: 'dashboard' */ '@/views/dashboard/home');

// 仪表盘模块各组件异步声明（用于路由懒加载）
const dashboard = () => import(/* webpackChunkName: 'dashboard' */ '@/views/dashboard/old-index.vue');

// 仪表盘模块路由配置生成函数
const getDashboardRoutes = () => [
  {
    path: '/dashboard',
    name: 'dashboard',
    component: DashboardTempView,
    redirect: '/dashboard/home',
    children: [
      // 默认仪表盘
      {
        path: 'home',
        name: 'home',
        component: home,
        meta: {
          title: '仪表盘',
          navId: 'dashboard-home',
        },
      },
      // 默认仪表盘
      {
        path: 'default-dashboard',
        name: 'default-dashboard',
        component: dashboard,
        meta: {
          title: '仪表盘',
          navId: 'dashboard',
        },
      },
      // 新建仪表盘
      {
        path: 'create-dashboard',
        name: 'create-dashboard',
        meta: {
          title: '仪表盘',
          needBack: true,
          backName: 'default-dashboard',
          navId: 'dashboard',
        },
        component: dashboard,
      },
      // 新建目录
      {
        path: 'create-folder',
        name: 'create-folder',
        meta: {
          title: '仪表盘',
          needBack: true,
          backName: 'default-dashboard',
          navId: 'dashboard',
        },
        component: dashboard,
      },
      // 导入仪表盘
      {
        path: 'import-dashboard',
        name: 'import-dashboard',
        meta: {
          title: '仪表盘',
          needBack: true,
          backName: 'default-dashboard',
          navId: 'dashboard',
        },
        component: dashboard,
      },
    ],
  },
];

export default getDashboardRoutes;
