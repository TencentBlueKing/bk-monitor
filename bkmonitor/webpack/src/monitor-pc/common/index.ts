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
import { RouteConfig, RouteConfigMultipleViews, RouteConfigSingleView } from 'vue-router/types/router';

import { beforeEnter } from '../router/utils';

export const applyGuidePage = (
  routes: RouteConfigMultipleViews[] | RouteConfigSingleView[],
  excludes: string[] = []
): RouteConfig[] =>
  routes.map(route => {
    if (excludes.includes(route.name)) return route;
    const { navId, noSpaceCheck = false } = route.meta;
    if (noSpaceCheck) return route;
    return {
      ...route,
      beforeEnter: (to: RouteConfig, from: RouteConfig, next: Function) => beforeEnter(navId, next),
      meta: {
        ...route.meta,
        noChangeLoading: true,
      },
    };
  });

export const applyNoAuthPage = (routes: RouteConfigMultipleViews[] | RouteConfigSingleView[], noAuthPage: any) =>
  routes.map((route: RouteConfig) => {
    if (route.path.length < 2) return route;
    return {
      ...route,
      meta: {
        ...(route.meta || {}),
        noAuthComponent: noAuthPage,
      },
    };
  });
