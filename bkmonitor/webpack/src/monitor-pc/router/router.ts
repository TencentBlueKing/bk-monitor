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
/* eslint-disable max-len */
// eslint-disable-next-line simple-import-sort/imports
import Vue from 'vue';
import VueRouter, { Route, RouteConfig } from 'vue-router';

import { getUrlParam, random } from '../../monitor-common/utils/utils';
import introduce from '../common/introduce';
import { NO_BUSSINESS_PAGE_HASH } from '../constant/constant';
import authorityStore from '../store/modules/authority';
import reportLogStore from '../store/modules/report-log';
import store from '../store/store';
// #if APP !== 'external'
import dataRetrievalRoutes from './data-retrieval';
import eventRoutes from './event';
import homeRoutes from './home';
import intergrateRoutes from './integrated';
import managerRoutes from './manager';
import otherRoutes from './others';
import scensesRoutes from './scenes';
import platformSetting from './platform-setting';
import emailSubscriptionsRoutes from './dashboard/email-subscriptions';
// #endif
import dashboardRoutes from './dashboard';
// import spaceData from './space';
import { isInCommonRoute, setLocalStoreRoute } from './router-config';

const EmailSubscriptionsName = 'email-subscriptions';
Vue.use(VueRouter);

// #if APP !== 'external'
const routes = [
  ...homeRoutes,
  ...dataRetrievalRoutes,
  ...intergrateRoutes,
  ...eventRoutes,
  ...managerRoutes,
  ...otherRoutes,
  ...scensesRoutes,
  ...platformSetting,
  ...dashboardRoutes,
  ...emailSubscriptionsRoutes,
  {
    path: '*',
    redirect: '/exception'
  }
] as RouteConfig[];
// #else
// #code const routes = [...dashboardRoutes,{  path: '*',  redirect: '/grafana'}] as RouteConfig[];
// #endif
const router = new VueRouter({
  mode: 'hash',
  routes
});
export const isAuthority = async (page: string | string[]) => {
  const data: { isAllowed: boolean }[] = await authorityStore.checkAllowedByActionIds({
    action_ids: Array.isArray(page) ? page : [page]
  });
  return !!data.length && data.some(item => item.isAllowed);
};

const hasEmailSubscriptions = (route: Route) => (route.path || route.name || '').indexOf(EmailSubscriptionsName) > -1;

const specialReportRouteList = [
  'email-subscriptions',
  'email-subscriptions-history',
  'platform-setting',
  'external-auth',
  'metrics-manager',
  'new-dashboard',
  'import-dashboard',
  'folder-dashboard',
  'grafana-datasource'
];
router.beforeEach(async (to, from, next) => {
  // 空闲初始化introduce数据
  store.getters.bizList?.length && introduce.initIntroduce(to);
  if (
    !window.__BK_WEWEB_DATA__?.token &&
    !['no-business', 'event-center', 'event-center-detail', 'event-center-action-detail', 'share'].includes(to.name) &&
    !store.getters.bizList?.length
  ) {
    return next({ name: 'no-business' });
  }
  if ((document.body as any).___zrEVENTSAVED) {
    /* 图表tip异常问题解决办法 */
    (document.body as any).___zrEVENTSAVED = null;
  }
  // 设置本地缓存常用访问列表
  if (isInCommonRoute(to.name)) {
    setLocalStoreRoute(to.name);
  }
  store.commit('app/SET_NAV_ID', to.meta.navId);
  // 无业务页面跳转处理
  if (hasEmailSubscriptions(from)) {
    const bizId = getUrlParam('bizId')?.replace(/\//gim, '');
    if (hasEmailSubscriptions(to) || (bizId !== null && +bizId > -1)) {
      next();
    } else {
      const { origin, pathname } = location;
      const bizid = localStorage.getItem('__biz_id__') || -1;
      location.href = `${origin}${pathname}?bizId=${bizid}#${to.fullPath}`;
      return;
    }
  }

  const { fromUrl, actionId } = to.query;
  if (['no-business', 'error-exception'].includes(to.name) && actionId) {
    let hasAuthority = false;
    if (!from.name) {
      hasAuthority = await isAuthority(actionId as string | string[]);
    }
    if (hasAuthority) {
      let path = fromUrl || '';
      if (to.name === 'no-business') {
        path = localStorage.getItem(NO_BUSSINESS_PAGE_HASH) || '';
      }
      next(`/${path}`);
    } else {
      next();
    }
    return;
  }
  let hasAuthority = true;
  const { authority } = to.meta;
  // 子应用 临时分享 模式的引用不需要页面级鉴权
  if (
    !(window.token && window.__POWERED_BY_BK_WEWEB__) &&
    authority?.page &&
    ![
      from.name,
      'error-exception',
      'event-center',
      'event-center-detail',
      'event-center-action-detail',
      'share'
    ].includes(to.name)
  ) {
    store.commit('app/SET_ROUTE_CHANGE_LOADNG', true);
    hasAuthority = await isAuthority(authority?.page)
      .catch(() => false)
      .finally(() => {
        if (to.meta.noChangeLoading) return;
        setTimeout(() => store.commit('app/SET_ROUTE_CHANGE_LOADNG', false), 20);
      });
    if (hasAuthority) {
      next();
    } else {
      window.requestIdleCallback(() => store.commit('app/SET_ROUTE_CHANGE_LOADNG', false));
      next({
        path: `/exception/403/${random(10)}`,
        query: {
          actionId: authority.page || '',
          fromUrl: to.fullPath.replace(/^\//, ''),
          parentRoute: to.meta.route.parent
        },
        params: {
          title: '无权限'
        }
      });
    }
  } else {
    next();
  }
});
router.afterEach(to => {
  store.commit('app/SET_NAV_TITLE', to.params.title || to.meta.title);
  if (['error-exception', 'no-business'].includes(to.name)) return;
  reportLogStore.reportRouteLog({
    route_id: to.name,
    nav_id: to.meta.navId,
    nav_name: specialReportRouteList.includes(to.meta.navId) ? to.meta?.navName || to.meta?.title : undefined
  });
});

export default router;
