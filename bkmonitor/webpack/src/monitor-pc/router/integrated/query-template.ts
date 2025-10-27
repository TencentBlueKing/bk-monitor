/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import type { RouteConfig } from 'vue-router';

const MetricTemplate = () =>
  import(/* webpackChunkName: 'MetricTemplate' */ '../../pages/query-template/query-template');

const MetricTemplateCreate = () =>
  import(/* webpackChunkName: 'MetricTemplateCreate' */ '../../pages/query-template/create/template-create');

const MetricTemplateEdit = () =>
  import(/* webpackChunkName: 'MetricTemplateEdit' */ '../../pages/query-template/edit/template-edit');
import * as queryTemplateAuth from '../../pages/query-template/authority-map';

export default [
  {
    path: '/query-template',
    name: 'query-template',
    components: {
      noCache: MetricTemplate,
    },
    meta: {
      title: '查询模板',
      navId: 'query-template',
      route: {
        parent: 'integrated',
      },
      authority: {
        map: queryTemplateAuth,
        page: queryTemplateAuth.VIEW_AUTH,
      },
      noNavBar: false,
    },
  },
  {
    path: '/query-template/create',
    name: 'query-template-create',
    components: {
      noCache: MetricTemplateCreate,
    },
    meta: {
      title: '创建查询模板',
      navId: 'query-template',
      route: {
        parent: 'integrated',
      },
      authority: {
        map: queryTemplateAuth,
        page: queryTemplateAuth.MANAGE_AUTH,
      },
      noNavBar: true,
    },
  },
  {
    path: '/query-template/edit/:id',
    name: 'query-template-edit',
    components: {
      noCache: MetricTemplateEdit,
    },
    meta: {
      title: '编辑查询模板',
      navId: 'query-template',
      authority: {
        map: queryTemplateAuth,
        page: queryTemplateAuth.MANAGE_AUTH,
      },
      route: {
        parent: 'integrated',
      },
      noNavBar: true,
    },
  },
] as RouteConfig[];
