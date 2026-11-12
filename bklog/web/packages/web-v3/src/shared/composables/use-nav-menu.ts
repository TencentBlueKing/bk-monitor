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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { useGlobalsStore } from '@/app/state/domains/globals-store';
import { includesValue } from '@/shared/utils/typed-record';

import { computed, ref } from 'vue';

import * as authorityMap from '@/shared/lib/authority-map';
import useRoute from '@/shared/composables/use-route';
import useRouter from '@/shared/composables/use-router';

import { getExternalDefaultRoute, routeNameToExternalMenu } from '@/app/router/helper';
import reportLogStore from '@/app/state/modules/report-log';
import { BK_LOG_STORAGE } from '@/app/state/store.type.ts';

export function useNavMenu(options: {
  t: (_msg: string) => string;
  bkInfo: any;
  http: any;
  emit?: (_event: 'welcome', ..._args: unknown[]) => void;
}) {
  const { t, bkInfo } = options;
  const store = useApplicationStore();
  const route = useRoute();
  const router = useRouter();
  const isFirstLoad = ref(true);

  // computed
  const topMenu = computed(() => store.topMenu);
  const menuList = computed(() => store.menuList);
  const spaceUid = computed(() => store.spaceUid);
  const bkBizId = computed(() => store.storage[BK_LOG_STORAGE.BK_BIZ_ID]);
  const mySpaceList = computed(() => store.mySpaceList);
  const isExternal = computed(() => store.isExternal);
  const externalMenu = computed(() => store.externalMenu);

  // methods
  const getDemoProjectUrl = (id: string) => {
    let siteUrl = (window as any).SITE_URL;
    if (!siteUrl.startsWith('/')) {
      siteUrl = `/${siteUrl}`;
    }
    if (!siteUrl.endsWith('/')) {
      siteUrl += '/';
    }
    return `${window.location.origin + siteUrl}#/retrieve?spaceUid=${id}`;
  };

  const checkSpaceAuth = async (space: any) => {
    if (space?.permission?.[authorityMap.VIEW_BUSINESS]) {
      useGlobalsStore().updateAuthContainerInfo(null);
      return;
    }
    try {
      store.updateSpace(space.space_uid);
      const res = await store.getApplyData({
        action_ids: [authorityMap.VIEW_BUSINESS],
        resources: [
          {
            type: 'space',
            id: space.space_uid,
          },
        ],
      });
      useGlobalsStore().updateAuthContainerInfo(res.data);
    } catch (err) {
      console.warn(err);
    }
  };

  const updateExternalMenuBySpace = (newSpaceUid: string) => {
    const list: string[] = [];
    const curSpace = (mySpaceList.value || []).find((item: any) => item.space_uid === newSpaceUid);
    const externalPermissions: string[] = curSpace?.external_permission || [];
    for (const permission of externalPermissions) {
      if (permission === 'log_search') {
        list.push('retrieve');
      } else if (permission === 'log_extract') {
        list.push('manage');
      } else if (permission === 'client_log') {
        list.push('client-log-search');
      }
    }
    // 聚类配置等功能级授权项不对应菜单，需要保留原始授权项供页面内判断
    store.updateState({ externalMenu: list, externalPermissions });
  };

  const setRouter = async (newSpaceUid: string) => {
    if (isExternal.value) {
      updateExternalMenuBySpace(newSpaceUid);
    }
    // 空间解析失败的恢复跳转由空间选择器统一处理，避免覆盖原始 IndexId。
    if (store.spaceResolveFailed) {
      return;
    }
    // 外部版：当前路由在新业务不可用时，重定向到第一个可用路由
    if (isExternal.value) {
      const currentMenu = routeNameToExternalMenu(route.name as string);
      if (currentMenu !== null && !includesValue(externalMenu.value, currentMenu)) {
        const targetRoute = getExternalDefaultRoute(externalMenu.value);
        router.push({ name: targetRoute === 'manage' ? 'extract-home' : targetRoute });
        return;
      }
    }
    if (route.name !== 'retrieve' && !isFirstLoad.value) {
      const { name, meta, params, query } = route as any;
      const routingHop = meta.needBack && !isFirstLoad.value ? meta.backName : name ? name : 'retrieve';
      const newQuery = {
        ...query,
        spaceUid,
      };
      if (query.bizId) {
        newQuery.spaceUid = spaceUid;
      }
      const { bizId: removedBizId, ...otherNewQuery } = newQuery;
      const { indexId: removedIndexId, ...otherParams } = params;
      router.push({
        name: routingHop,
        params: {
          ...otherParams,
        },
        query: otherNewQuery,
      });
    }
  };

  const spaceChange = async (newSpaceUid = '') => {
    store.updateSpace(newSpaceUid);
    if (newSpaceUid) {
      const space = mySpaceList.value.find((item: any) => item.space_uid === newSpaceUid);
      await checkSpaceAuth(space);
    }
    store.updateStorage({ [BK_LOG_STORAGE.BK_SPACE_UID]: newSpaceUid });
    for (const item of mySpaceList.value) {
      if (item.space_uid === newSpaceUid) {
        store.updateStorage({ [BK_LOG_STORAGE.BK_BIZ_ID]: item.bk_biz_id });
        break;
      }
    }
    if (newSpaceUid) {
      await setRouter(newSpaceUid);
    }

    // 首次加载应用路由触发上报还未获取到 spaceUid ，需手动执行上报
    if (store.isAppFirstLoad && newSpaceUid) {
      const { name, meta } = route as any;
      reportLogStore.reportRouteLog({
        route_id: name,
        nav_id: meta.navId,
        external_menu: externalMenu.value,
      });
    }
  };

  const checkSpaceChange = (newSpaceUid = '') => {
    if (!isFirstLoad.value && (route.meta as any)?.needBack) {
      store.updateState({ showRouterLeaveTip: true });

      bkInfo({
        title: t('是否放弃本次操作？'),
        confirmFn: () => {
          spaceChange(newSpaceUid);
        },
        cancelFn: () => {
          store.updateState({ showRouterLeaveTip: false });
        },
      });
      return;
    }
    spaceChange(newSpaceUid);
  };

  return {
    // state
    topMenu,
    menuList,
    spaceUid,
    bkBizId,
    mySpaceList,
    isExternal,
    externalMenu,
    getDemoProjectUrl,
    checkSpaceChange,
    spaceChange,
    checkSpaceAuth,
    updateExternalMenuBySpace,
    isFirstLoad,
  };
}
