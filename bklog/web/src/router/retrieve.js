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

// 检索模块各组件异步声明（用于路由懒加载）
const Retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-hub');
const ExternalAuth = () => import(/* webpackChunkName: 'externalAuth' */ '@/views/authorization/authorization-list');
const ShareLink = () => import(/* webpackChunkName: 'share-link' */ '@/views/share/index.tsx');
const DataIdUrl = () => import(/* webpackChunkName: 'data-id-url' */ '@/views/data-id-url/index.tsx');
const TemplateManage = () => import('@/views/retrieve-v3/search-result/template-manage/index.tsx');

// 检索模块路由配置生成函数
const getRetrieveRoutes = () => [
  // 检索主页面
  {
    path: '/retrieve/:indexId?',
    name: 'retrieve',
    component: Retrieve,
    meta: {
      title: '检索',
      navId: 'retrieve',
    },
  },
  // 模版管理
  {
    path: '/template-manage',
    name: 'templateManage',
    component: TemplateManage,
  },
  // 授权列表
  {
    path: '/external-auth/:activeNav?',
    name: 'externalAuth',
    component: ExternalAuth,
    meta: {
      title: '授权列表',
      navId: 'external-auth',
    },
  },
  // 分享链接
  {
    path: '/share/:linkId?',
    name: 'share',
    component: ShareLink,
    meta: {
      title: '分享链接',
      navId: 'share',
    },
  },

  // 根据 bk_data_id 获取采集项和索引集信息
  {
    path: '/data_id/:id?',
    name: 'data_id',
    component: DataIdUrl,
    meta: {
      title: '根据 bk_data_id 获取采集项和索引集信息',
      navId: 'data_id',
    },
  },
];

export default getRetrieveRoutes;
