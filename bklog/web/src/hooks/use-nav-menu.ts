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

import { ref, computed, watch } from 'vue';

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
  const { t, bkInfo, http, emit } = options;
  const store = useStore();
  const route = useRoute();
  const router = useRouter();

  // data
  const isFirstLoad = ref(true);

  // computed
  const topMenu = computed(() => store.state.topMenu);
  const menuList = computed(() => store.state.menuList);
  const activeTopMenu = computed(() => store.state.activeTopMenu);
  const spaceUid = computed(() => store.state.spaceUid);
  const bkBizId = computed(() => store.state.bkBizId);
  const mySpaceList = computed(() => store.state.mySpaceList);
  const isExternal = computed(() => store.state.isExternal);
  const externalMenu = computed(() => store.state.externalMenu);

  // watch query.from
  watch(
    () => route.query.from,
    fromValue => {
      if (fromValue) {
        store.commit('updateIframeQuery', { from: fromValue });
      }
    },
    { immediate: true, deep: true },
  );

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
    try {
      const menuListData = await store.dispatch('requestMenuList', newSpaceUid);

      const manageGroupNavList = menuListData.find((item: any) => item.id === 'manage')?.children || [];
      const manageNavList: any[] = [];
      for (const group of manageGroupNavList) {
        manageNavList.push(...group.children);
      }
      const logCollectionNav = manageNavList.find((nav: any) => nav.id === 'log-collection');

      if (logCollectionNav) {
        logCollectionNav.children = [
          {
            id: 'collection-item',
            name: t('采集项'),
            project_manage: logCollectionNav.project_manage,
          },
          {
            id: 'log-index-set',
            name: t('索引集'),
            project_manage: logCollectionNav.project_manage,
          },
        ];
      }

      // 监听路由 name
      watch(
        () => route.name,
        () => {
          const matchedList = (route as any).matched;
          const newActiveTopMenu =
            menuListData.find((item: any) => {
              return matchedList.some((record: any) => record.name === item.id);
            }) || {};
          store.commit('updateState', { activeTopMenu: newActiveTopMenu });
          const topMenuList = newActiveTopMenu.children?.length ? newActiveTopMenu.children : [];
          const topMenuChildren = topMenuList.reduce((pre: any[], cur: any) => {
            if (cur.children?.length) {
              pre.push(...cur.children);
            }
            return pre;
          }, []);
          const activeManageNav =
            topMenuChildren.find((item: any) => {
              return matchedList.some((record: any) => record.name === item.id);
            }) || {};
          store.commit('updateState', { activeManageNav: activeManageNav });

          const activeManageSubNav = activeManageNav.children
            ? activeManageNav.children.find((item: any) => {
                return matchedList.some((record: any) => record.name === item.id);
              })
            : {};
          store.commit('updateState', { activeManageSubNav: activeManageSubNav });
        },
        { immediate: true },
      );

      return menuListData;
    } catch (e) {
      console.warn(e);
    } finally {
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
        const RoutingHop = meta.needBack && !isFirstLoad.value ? meta.backName : name ? name : 'retrieve';
        const newQuery = {
          ...query,
          spaceUid,
        };
        if (query.bizId) {
          newQuery.spaceUid = spaceUid;
        }
        const { bizId: _bizId, ...otherNewQuery } = newQuery;
        const { indexId: _indexId, ...otherParams } = params;
        store.commit('updateState', { pageLoading: true });
        router.push({
          name: RoutingHop,
          params: {
            ...otherParams,
          },
          query: otherNewQuery,
        });
      }
      setTimeout(() => {
        store.commit('updateState', { pageLoading: false });
        isFirstLoad.value = false;
        store.commit('updateState', { showRouterLeaveTip: false });
      }, 0);
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

  const requestMySpaceList = async () => {
    try {
      const queryObj = structuredClone(route.query);
      if (queryObj.from) {
        store.commit('updateIframeQuery', queryObj);
      }

      const spaceList = store.state.mySpaceList;
      let isHaveViewBusiness = false;

      for (const item of spaceList) {
        item.bk_biz_id = `${item.bk_biz_id}`;
        item.space_uid = `${item.space_uid}`;
        item.space_full_code_name = `${item.space_name}(#${item.space_id})`;
        item.permission.view_business_v2 && (isHaveViewBusiness = true);
      }

      const { bizId, spaceUid: newSpaceUid } = queryObj;
      const demoId = String((window as any).DEMO_BIZ_ID);
      const demoProject = spaceList.find((item: any) => `${item.bk_biz_id}` === demoId);
      const demoProjectUrl = demoProject ? getDemoProjectUrl(demoProject.space_uid) : '';
      store.commit('updateState', { demoUid: demoProject ? demoProject.space_uid : '' });
      const isOnlyDemo = demoProject && spaceList.length === 1;
      if (!isHaveViewBusiness || isOnlyDemo) {
        const args: any = {
          newBusiness: { url: (window as any).BIZ_ACCESS_URL },
          getAccess: {},
        };
        if (isOnlyDemo) {
          if (bizId === demoProject.bk_biz_id || newSpaceUid === demoProject.space_uid) {
            return checkSpaceChange(demoProject.space_uid);
          }
          args.demoBusiness = {
            url: demoProjectUrl,
          };
        }
        if (newSpaceUid || bizId) {
          const query = newSpaceUid ? { space_uid: newSpaceUid } : { bk_biz_id: bizId };
          const [betaRes, authRes] = await Promise.all([
            http.request('/meta/getMaintainerApi', { query }),
            store.dispatch('getApplyData', {
              action_ids: [authorityMap.VIEW_BUSINESS],
              resources: [],
            }),
          ]);
          args.getAccess.businessName = betaRes.data.bk_biz_name;
          args.getAccess.url = authRes.data.apply_url;
        } else {
          const authRes = await store.dispatch('getApplyData', {
            action_ids: [authorityMap.VIEW_BUSINESS],
            resources: [],
          });
          args.getAccess.url = authRes.data.apply_url;
        }
        store.commit('updateState', { pageLoading: false });
        checkSpaceChange();
        emit?.('welcome', args);
      } else {
        const firstRealSpaceUid = spaceList.find((item: any) => item.bk_biz_id !== demoId).space_uid;
        if (newSpaceUid || bizId) {
          const matchProject = spaceList.find(
            (item: any) => item.space_uid === newSpaceUid || item.bk_biz_id === bizId,
          );
          checkSpaceChange(matchProject ? matchProject.space_uid : firstRealSpaceUid);
        } else {
          const storageSpaceUid = store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID];
          const hasSpace = storageSpaceUid ? spaceList.some((item: any) => item.space_uid === storageSpaceUid) : false;
          checkSpaceChange(hasSpace ? storageSpaceUid : firstRealSpaceUid);
        }
      }
    } catch (e) {
      console.warn(e);
      store.commit('updateState', { pageLoading: false });
    }
  };

  return {
    // state
    topMenu,
    menuList,
    activeTopMenu,
    spaceUid,
    bkBizId,
    mySpaceList,
    isExternal,
    externalMenu,
    // methods
    requestMySpaceList,
    getDemoProjectUrl,
    checkSpaceChange,
    spaceChange,
    checkSpaceAuth,
    updateExternalMenuBySpace,
    setRouter,
    isFirstLoad,
  };
}
