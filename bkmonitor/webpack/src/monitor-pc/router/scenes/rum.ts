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
import * as rumAuth from '../../pages/rum/authority-map';

import type { RouteConfig } from 'vue-router';

const Rum = () => import(/* webpackChunkName: 'Rum' */ '../../pages/rum/rum');
export default [
  {
    path: '/trace/rum',
    name: 'rum',
    components: {
      noCache: Rum,
    },
    meta: {
      title: 'RUM',
      navId: 'rum',
      navClass: 'rum-nav',
      noChangeLoading: true,
      noNavBar: true,
      needClearQuery: true,
      route: {
        parent: 'scenes',
      },
      authority: {
        map: rumAuth,
        page: rumAuth.VIEW_AUTH,
      },
    },
  },
  {
    path: '/trace/rum/app/:appName/config',
    name: 'rumAppConfig',
    components: {
      noCache: Rum,
    },
    meta: {
      title: 'RUM应用配置',
      needBack: true,
      navId: 'rum',
      authority: {
        map: rumAuth,
        page: rumAuth.VIEW_AUTH,
      },
      route: {
        parent: 'rum',
      },
      noNavBar: true,
    },
  },
] as RouteConfig[];
