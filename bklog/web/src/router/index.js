
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

/**
 * @file router 配置
 * @author  <>
 */

import Vue from 'vue';
import VueRouter from 'vue-router';
import http from '@/api';
import store from '@/store';
import reportLogStore from '@/store/modules/report-log';

import manageRoutes from './manage';
import retrieveRoutes from './retrieve';
import dashboardRoutes from './dashboard';
import monitorRoutes from './dashboard';

Vue.use(VueRouter);

// 解决编程式路由往同一地址跳转时会报错的情况
const originalPush = VueRouter.prototype.push;
const originalReplace = VueRouter.prototype.replace;

// push
VueRouter.prototype.push = function push(location, onResolve, onReject) {
  if (onResolve || onReject) return originalPush.call(this, location, onResolve, onReject);
  return originalPush.call(this, location).catch(err => err);
};

// replace
VueRouter.prototype.replace = function push(location, onResolve, onReject) {
  if (onResolve || onReject) return originalReplace.call(this, location, onResolve, onReject);
  return originalReplace.call(this, location).catch(err => err);
};

const getDefRouteName = () => {
  if (window.IS_EXTERNAL === true || window.IS_EXTERNAL === 'true') {
    if (externalMenu?.includes('retrieve')) {
      return 'retrieve';
    }
    return 'manage';
  }
  return 'retrieve';
};

// 路由配置生成函数
const getRoutes = (spaceId, bkBizId, externalMenu) => {
  return [
    // 当用户访问根路径/时，根据当前环境和参数，自动跳转到检索页or管理页
    {
      path: '',
      redirect: () => ({
        name: getDefRouteName(),
        query: {
          spaceUid: spaceId,
          bizId: bkBizId,
        },
      }),
      meta: {
        title: '检索',
        navId: 'retrieve',
      },
    },
    // 检索模块路由
    ...retrieveRoutes(),
    // 监控模块路由
    ...monitorRoutes(),
    // 仪表盘模块路由
    ...dashboardRoutes(),
    // 管理模块路由
    ...manageRoutes(),
  ];
};

/**
 * @param id 路由id
 * @returns 路由配置
 */
export function getRouteConfigById(id, space_uid, bk_biz_id, externalMenu) {
  const flatConfig = getRoutes(space_uid, bk_biz_id, externalMenu).flatMap(config => {
    if (config.children?.length) {
      return config.children.flatMap(set => {
        if (set.children?.length) {
          return set.children;
        }
        return set;
      });
    }
    return config;
  });

  return flatConfig.find(item => item.meta?.navId === id);
}

export default (spaceId, bkBizId, externalMenu) => {
  const routes = getRoutes(spaceId, bkBizId, externalMenu);
  const router = new VueRouter({
    routes,
  });

  const cancelRequest = async () => {
    const allRequest = http.queue.get();
    const requestQueue = allRequest.filter(request => request.cancelWhenRouteChange);
    await http.cancel(requestQueue.map(request => request.requestId));
  };

  router.beforeEach(async (to, from, next) => {
    await cancelRequest();
    if (to.name === 'retrieve') {
      window.parent.postMessage(
        {
          _MONITOR_URL_PARAMS_: to.params,
          _MONITOR_URL_QUERY_: to.query,
          _LOG_TO_MONITOR_: true,
          _MONITOR_URL_: window.MONITOR_URL,
        },
        '*',
        // window.MONITOR_URL,
      );
    }
    if (
      window.IS_EXTERNAL &&
      JSON.parse(window.IS_EXTERNAL) &&
      !['retrieve', 'extract-home', 'extract-create', 'extract-clone'].includes(to.name)
    ) {
      // 非外部版路由重定向
      const routeName = store.state.externalMenu.includes('retrieve') ? 'retrieve' : 'manage';
      next({ name: routeName });
    } else {
      next();
    }
  });

  let stringifyExternalMenu = '[]';
  try {
    stringifyExternalMenu = JSON.stringify(externalMenu);
  } catch (e) {
    console.warn('externalMenu JSON.stringify error', e);
  }

  router.afterEach(to => {
    if (to.name === 'exception') return;
    reportLogStore.reportRouteLog({
      route_id: to.name,
      nav_id: to.meta.navId,
      nav_name: to.meta?.title ?? undefined,
      external_menu: stringifyExternalMenu,
    });
  });

  return router;
};