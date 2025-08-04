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
import useStore from '@/hooks/use-store';
import useRoute from '@/hooks/use-route';
import useRouter from '@/hooks/use-router';
import reportLogStore from '@/store/modules/report-log';
import * as authorityMap from '@/common/authority-map';
import { BK_LOG_STORAGE } from '@/store/store.type';

export function useNavMenu(options: {
  t: (msg: string) => string;
  bkInfo: any;
  http: any;
  emit?: (event: string, ...args: any[]) => void;
} ) {
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
    (fromValue) => {
      if (fromValue) {
        store.commit('updateAsIframe', fromValue);
        store.commit('updateIframeQuery', { from: fromValue });
      }
    },
    { immediate: true, deep: true }
  );

  // methods
  const getDemoProjectUrl = (id: string) => {
    let siteUrl = (window as any).SITE_URL;
    if (!siteUrl.startsWith('/')) siteUrl = `/${siteUrl}`;
    if (!siteUrl.endsWith('/')) siteUrl += '/';
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

  const updateExternalMenuBySpace = (spaceUid: string) => {
    const list: string[] = [];
    const curSpace = (mySpaceList.value || []).find((item: any) => item.space_uid === spaceUid);
    (curSpace?.external_permission || []).forEach((permission: string) => {
      if (permission === 'log_search') {
        list.push('retrieve');
      } else if (permission === 'log_extract') {
        list.push('manage');
      }
    });
    store.commit('updateExternalMenu', list);
  };

  const setRouter = async (spaceUid: string) => {
    if (isExternal.value) {
      updateExternalMenuBySpace(spaceUid);
    }
    try {
      const menuListData = await store.dispatch('requestMenuList', spaceUid);

      const manageGroupNavList = menuListData.find((item: any) => item.id === 'manage')?.children || [];
      const manageNavList: any[] = [];
      manageGroupNavList.forEach((group: any) => {
        manageNavList.push(...group.children);
      });
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
          const activeTopMenu =
            menuListData.find((item: any) => {
              return matchedList.some((record: any) => record.name === item.id);
            }) || {};
          store.commit('updateActiveTopMenu', activeTopMenu);

          const topMenuList = activeTopMenu.children?.length ? activeTopMenu.children : [];
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
          store.commit('updateActiveManageNav', activeManageNav);

          const activeManageSubNav = activeManageNav.children
            ? activeManageNav.children.find((item: any) => {
                return matchedList.some((record: any) => record.name === item.id);
              })
            : {};
          store.commit('updateActiveManageSubNav', activeManageSubNav);
        },
        { immediate: true }
      );

      return menuListData;
    } catch (e) {
      console.warn(e);
    } finally {
      if (
        isExternal.value &&
        route.name === 'retrieve' &&
        !externalMenu.value.includes('retrieve')
      ) {
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
          delete newQuery.bizId;
        }
        if (params.indexId) delete params.indexId;
        store.commit('setPageLoading', true);
        router.push({
          name: RoutingHop,
          params: {
            ...params,
          },
          query: newQuery,
        });
      }
      setTimeout(() => {
        store.commit('setPageLoading', false);
        isFirstLoad.value = false;
        store.commit('updateRouterLeaveTip', false);
      }, 0);
    }
  };

  const spaceChange = async (spaceUid = '') => {
    store.commit('updateSpace', spaceUid);
    if (spaceUid) {
      const space = mySpaceList.value.find((item: any) => item.space_uid === spaceUid);
      await checkSpaceAuth(space);
    }
    store.commit('updateStorage', { [BK_LOG_STORAGE.BK_SPACE_UID]: spaceUid });
    for (const item of mySpaceList.value) {
      if (item.space_uid === spaceUid) {
        store.commit('updateStorage', { [BK_LOG_STORAGE.BK_BIZ_ID]: item.bk_biz_id });
        break;
      }
    }
    if (spaceUid) await setRouter(spaceUid);

    // 首次加载应用路由触发上报还未获取到 spaceUid ，需手动执行上报
    if (store.state.isAppFirstLoad && spaceUid) {
      store.state.isAppFirstLoad = false;
      const { name, meta } = route as any;
      reportLogStore.reportRouteLog({
        route_id: name,
        nav_id: meta.navId,
        external_menu: externalMenu.value,
      });
    }
  };

  const checkSpaceChange = (spaceUid = '') => {
    if (!isFirstLoad.value && (route.meta as any)?.needBack) {
      store.commit('updateRouterLeaveTip', true);

      bkInfo({
        title: t('是否放弃本次操作？'),
        confirmFn: () => {
          spaceChange(spaceUid);
        },
        cancelFn: () => {
          store.commit('updateRouterLeaveTip', false);
        },
      });
      return;
    }
    spaceChange(spaceUid);
  };

  const requestMySpaceList = async () => {
    try {
      const queryObj = JSON.parse(JSON.stringify(route.query));
      if (queryObj.from) {
        store.commit('updateAsIframe', queryObj.from);
        store.commit('updateIframeQuery', queryObj);
      }

      const spaceList = store.state.mySpaceList;
      let isHaveViewBusiness = false;

      spaceList.forEach((item: any) => {
        item.bk_biz_id = `${item.bk_biz_id}`;
        item.space_uid = `${item.space_uid}`;
        item.space_full_code_name = `${item.space_name}(#${item.space_id})`;
        item.permission.view_business_v2 && (isHaveViewBusiness = true);
      });

      const { bizId, spaceUid } = queryObj;
      const demoId = String((window as any).DEMO_BIZ_ID);
      const demoProject = spaceList.find((item: any) => item.bk_biz_id === demoId);
      const demoProjectUrl = demoProject ? getDemoProjectUrl(demoProject.space_uid) : '';
      store.commit('setDemoUid', demoProject ? demoProject.space_uid : '');
      const isOnlyDemo = demoProject && spaceList.length === 1;
      if (!isHaveViewBusiness || isOnlyDemo) {
        const args: any = {
          newBusiness: { url: (window as any).BIZ_ACCESS_URL },
          getAccess: {},
        };
        if (isOnlyDemo) {
          if (bizId === demoProject.bk_biz_id || spaceUid === demoProject.space_uid) {
            return checkSpaceChange(demoProject.space_uid);
          }
          args.demoBusiness = {
            url: demoProjectUrl,
          };
        }
        if (spaceUid || bizId) {
          const query = spaceUid ? { space_uid: spaceUid } : { bk_biz_id: bizId };
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
        store.commit('setPageLoading', false);
        checkSpaceChange();
        emit && emit('welcome', args);
      } else {
        const firstRealSpaceUid = spaceList.find((item: any) => item.bk_biz_id !== demoId).space_uid;
        if (spaceUid || bizId) {
          const matchProject = spaceList.find(
            (item: any) => item.space_uid === spaceUid || item.bk_biz_id === bizId
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
      store.commit('setPageLoading', false);
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