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

import { computed, ref } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import reportLogStore from '@/store/modules/report-log';
import { BK_LOG_STORAGE } from '@/store/store.type';

export function useNavMenu(options: {
  t: (msg: string) => string;
  bkInfo: any;
  http: any;
  emit?: (event: string, ...args: any[]) => void;
}) {
  const { t, bkInfo } = options;
  const store = useStore();
  const route = useRoute();
  const router = useRouter();
  const isFirstLoad = ref(true);

  // computed
  const topMenu = computed(() => store.state.topMenu);
  const menuList = computed(() => store.state.menuList);
  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID]);
  const mySpaceList = computed(() => store.state.mySpaceList);
  const isExternal = computed(() => store.state.isExternal);
  const externalMenu = computed(() => store.state.externalMenu);

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
      store.commit('globals/updateAuthContainerInfo', null);
      return;
    }
    try {
      store.commit('updateSpace', space.space_uid);
      const res = await store.dispatch('getApplyData', {
        action_ids: [authorityMap.VIEW_BUSINESS],
        resources: [
          {
            type: 'space',
            id: space.space_uid,
          },
        ],
      });
      store.commit('globals/updateAuthContainerInfo', res.data);
    } catch (err) {
      console.warn(err);
    }
  };

  const updateExternalMenuBySpace = (newSpaceUid: string) => {
    const list: string[] = [];
    const curSpace = (mySpaceList.value || []).find((item: any) => item.space_uid === newSpaceUid);
    for (const permission of curSpace?.external_permission || []) {
      if (permission === 'log_search') {
        list.push('retrieve');
      } else if (permission === 'log_extract') {
        list.push('manage');
      }
    }
    store.commit('updateState', { externalMenu: list });
  };

  const setRouter = async (newSpaceUid: string) => {
    if (isExternal.value) {
      updateExternalMenuBySpace(newSpaceUid);
    }
    if (isExternal.value && route.name === 'retrieve' && !externalMenu.value.includes('retrieve')) {
      router.push({ name: 'extract-home' });
    } else if (
      isExternal.value &&
      ['extract-home', 'extract-create', 'extract-clone'].includes(route.name as string) &&
      !externalMenu.value.includes('manage')
    ) {
      router.push({ name: 'retrieve' });
    } else if (route.name !== 'retrieve' && !isFirstLoad.value) {
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
    store.commit('updateSpace', newSpaceUid);
    if (newSpaceUid) {
      const space = mySpaceList.value.find((item: any) => item.space_uid === newSpaceUid);
      await checkSpaceAuth(space);
    }
    store.commit('updateStorage', { [BK_LOG_STORAGE.BK_SPACE_UID]: newSpaceUid });
    for (const item of mySpaceList.value) {
      if (item.space_uid === newSpaceUid) {
        store.commit('updateStorage', { [BK_LOG_STORAGE.BK_BIZ_ID]: item.bk_biz_id });
        break;
      }
    }
    if (newSpaceUid) {
      await setRouter(newSpaceUid);
    }

    // 首次加载应用路由触发上报还未获取到 spaceUid ，需手动执行上报
    if (store.state.isAppFirstLoad && newSpaceUid) {
      store.state.isAppFirstLoad = false;
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
      store.commit('updateState', { showRouterLeaveTip: true });

      bkInfo({
        title: t('是否放弃本次操作？'),
        confirmFn: () => {
          spaceChange(newSpaceUid);
        },
        cancelFn: () => {
          store.commit('updateState', { showRouterLeaveTip: false });
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
