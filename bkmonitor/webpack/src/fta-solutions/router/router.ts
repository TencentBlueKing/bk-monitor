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
import Vue from 'vue';

import { random } from 'monitor-common/utils/utils';
import { getAuthById, setAuthById } from 'monitor-pc/common/auth-store';
import ExceptionPage from 'monitor-pc/pages/exception-page/exception-page.vue';
import Router, { type RouteConfig } from 'vue-router';

import authorityStore from '../store/modules/authority';
import Store from '../store/store';
import eventRoutes from './event/event';
import homeRoutes from './home/home';
import intergratedRoutes from './intergrated/intergrated';
import manageRoutes from './manage/manage';

Vue.use(Router);
export const routerConfig: RouteConfig[] = [
  ...eventRoutes,
  ...homeRoutes,
  ...intergratedRoutes,
  ...manageRoutes,
  {
    path: '/exception/:type?/:queryUid?',
    name: 'error-exception',
    component: ExceptionPage,
    props: true,
    beforeEnter(to, from, next) {
      to.meta.title = to.params.type === '403' ? '无权限' : to.params.title || to.params.type || '404';
      next();
    },
    meta: {
      title: '404',
      navId: 'exception',
      noNavBar: true,
    },
  },
  {
    path: '*',
    redirect: {
      name: 'home',
    },
  },
];

const createRouter = () =>
  new Router({
    scrollBehavior: (to, from, savedPosition) => {
      if (savedPosition) {
        return savedPosition;
      }
      return { x: 0, y: 0 };
    },
    mode: 'hash',
    routes: routerConfig.map(item => ({
      ...item,
      path:
        item.path !== '*'
          ? `${window.__BK_WEWEB_DATA__?.baseroute || '/'}${item.path}`.replace(/\/\//gim, '/')
          : item.path,
    })),
  });

const router = createRouter();

const isAuthority = async (page: string | string[]) => {
  if (!page) return true;
  const data: { isAllowed: boolean }[] = await authorityStore
    .checkAllowedByActionIds({
      action_ids: Array.isArray(page) ? page : [page],
    })
    .catch(() => false);
  return !!data.length && data.some(item => item.isAllowed);
};
router.beforeEach(async (to, from, next) => {
  Store.commit('app/SET_NAV_ID', to.meta.navId || to.name);
  const { fromUrl, actionId } = to.query;
  if (to.name === 'error-exception' && actionId) {
    let hasAuthority = false;
    if (!from.name) {
      hasAuthority = await isAuthority(actionId as string | string[]);
    }
    if (hasAuthority) {
      next(`/${fromUrl}`);
    } else {
      next();
    }
    return;
  }

  let hasAuthority = true;
  const { authority } = to.meta;
  if (authority?.page && to.name !== 'error-exception' && to.name !== from.name) {
    if (!getAuthById(authority.page)) {
      hasAuthority = await isAuthority(authority?.page).catch(() => false);
      setAuthById(Array.isArray(authority.page) ? authority.page[0] : authority.page, hasAuthority);
    }
    if (hasAuthority) {
      next();
    } else {
      next({
        path: `${window.__BK_WEWEB_DATA__?.baseroute || '/'}exception/403/${random(10)}`,
        query: {
          actionId: authority.page || '',
          fromUrl: to.fullPath.replace(/^\//, ''),
        },
        params: {
          title: '无权限',
        },
      });
    }
  } else {
    next();
  }
});
export default router;
