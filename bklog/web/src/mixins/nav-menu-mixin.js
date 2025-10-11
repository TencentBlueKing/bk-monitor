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

import reportLogStore from '@/store/modules/report-log';
import { mapState } from 'vuex';

import * as authorityMap from '../common/authority-map';
import { BK_LOG_STORAGE } from '../store/store.type';

export default {
  data() {
    return {};
  },
  computed: {
    ...mapState({
      topMenu: state => state.topMenu,
      menuList: state => state.menuList,
      activeTopMenu: state => state.activeTopMenu,
      spaceUid: state => state.spaceUid,
      bkBizId: state => state.bkBizId,
      mySpaceList: state => state.mySpaceList,
      isExternal: state => state.isExternal,
      externalMenu: state => state.externalMenu,
    }),
  },
  watch: {
    '$route.query'(val) {
      const queryObj = structuredClone(val);
      if (queryObj.from) {
        this.$store.commit('updateIframeQuery', queryObj);
      }
    },
  },
  methods: {
    getDemoProjectUrl(id) {
      let siteUrl = window.SITE_URL;
      if (!siteUrl.startsWith('/')) siteUrl = `/${siteUrl}`;
      if (!siteUrl.endsWith('/')) siteUrl += '/';
      return `${window.location.origin + siteUrl}#/retrieve?spaceUid=${id}`;
    },
    checkSpaceChange(spaceUid = '') {
      if (!this.isFirstLoad && this.$route.meta.needBack) {
        this.$store.commit('updateState', { showRouterLeaveTip: true });

        this.$bkInfo({
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => {
            this.spaceChange(spaceUid);
          },
          cancelFn: () => {
            this.$store.commit('updateState', { showRouterLeaveTip: false });
          },
        });
        return;
      }
      this.spaceChange(spaceUid);
    },
    /**
     * 更新当前项目
     * @param  {String} spaceUid - 当前项目id
     */
    async spaceChange(spaceUid = '') {
      this.$store.commit('updateSpace', spaceUid);
      if (spaceUid) {
        const space = this.mySpaceList.find(item => item.space_uid === spaceUid);
        await this.checkSpaceAuth(space);
      }
      // window.localStorage.setItem('space_uid', spaceUid);
      this.$store.commit('updateStorage', { [BK_LOG_STORAGE.BK_SPACE_UID]: spaceUid });
      for (const item of this.mySpaceList) {
        if (item.space_uid === spaceUid) {
          // window.localStorage.setItem('bk_biz_id', item.bk_biz_id);
          this.$store.commit('updateStorage', { [BK_LOG_STORAGE.BK_BIZ_ID]: item.bk_biz_id });
          break;
        }
      }
      spaceUid && this.setRouter(spaceUid); // 项目id不为空时，获取菜单

      // 由于首次加载应用路由触发上报还未获取到 spaceUid ，需手动执行上报
      if (this.$store.state.isAppFirstLoad && spaceUid) {
        this.$store.state.isAppFirstLoad = false;
        const { name, meta } = this.$route;
        reportLogStore.reportRouteLog({
          route_id: name,
          nav_id: meta.navId,
          external_menu: this.externalMenu,
        });
      }
    },
    // 选择的业务是否有权限
    async checkSpaceAuth(space) {
      if (space?.permission?.[authorityMap.VIEW_BUSINESS]) {
        // 有权限 不显示无业务权限的页面
        this.$store.commit('globals/updateAuthContainerInfo', null);
        return;
      }
      try {
        this.$store.commit('updateSpace', space.space_uid);
        const res = await this.$store.dispatch('getApplyData', {
          action_ids: [authorityMap.VIEW_BUSINESS],
          resources: [
            {
              type: 'space',
              id: space.space_uid,
            },
          ],
        });
        this.$store.commit('globals/updateAuthContainerInfo', res.data);
      } catch (err) {
        console.warn(err);
      }
    },
    /** 外部版根据空间授权权限显示菜单 */
    updateExternalMenuBySpace(spaceUid) {
      const list = [];
      const curSpace = (this.mySpaceList || []).find(item => item.space_uid === spaceUid);
      (curSpace.external_permission || []).forEach(permission => {
        if (permission === 'log_search') {
          list.push('retrieve');
        } else if (permission === 'log_extract') {
          list.push('manage');
        }
      });
      this.$store.commit('updateState', { externalMenu: list });
    },
    async setRouter(spaceUid) {
      if (this.isExternal) {
        this.updateExternalMenuBySpace(spaceUid);
      }
      try {
        const menuList = await this.$store.dispatch('requestMenuList', spaceUid);

        const manageGroupNavList = menuList.find(item => item.id === 'manage')?.children || [];
        const manageNavList = [];
        manageGroupNavList.forEach(group => {
          manageNavList.push(...group.children);
        });
        const logCollectionNav = manageNavList.find(nav => nav.id === 'log-collection');

        if (logCollectionNav) {
          // 增加日志采集导航子菜单
          logCollectionNav.children = [
            {
              id: 'collection-item',
              name: this.$t('采集项'),
              project_manage: logCollectionNav.project_manage,
            },
            {
              id: 'log-index-set',
              name: this.$t('索引集'),
              project_manage: logCollectionNav.project_manage,
            },
          ];
        }

        this.$watch(
          '$route.name',
          () => {
            const matchedList = this.$route.matched;
            const activeTopMenu =
              menuList.find(item => {
                return matchedList.some(record => record.name === item.id);
              }) || {};
            this.$store.commit('updateState', { activeTopMenu: activeTopMenu });

            const topMenuList = activeTopMenu.children?.length ? activeTopMenu.children : [];
            const topMenuChildren = topMenuList.reduce((pre, cur) => {
              if (cur.children?.length) {
                pre.push(...cur.children);
              }
              return pre;
            }, []);
            const activeManageNav =
              topMenuChildren.find(item => {
                return matchedList.some(record => record.name === item.id);
              }) || {};
            this.$store.commit('updateState', { activeManageNav: activeManageNav });

            const activeManageSubNav = activeManageNav.children
              ? activeManageNav.children.find(item => {
                  return matchedList.some(record => record.name === item.id);
                })
              : {};
            this.$store.commit('updateState', { activeManageSubNav: activeManageSubNav });
          },
          {
            immediate: true,
          },
        );

        return menuList;
      } catch (e) {
        console.warn(e);
      } finally {
        if (this.isExternal && this.$route.name === 'retrieve' && !this.externalMenu.includes('retrieve')) {
          // 当前在检索页 如果该空间没有日志检索授权 则跳转管理页
          this.$router.push({ name: 'extract-home' });
        } else if (
          this.isExternal &&
          ['extract-home', 'extract-create', 'extract-clone'].includes(this.$route.name) &&
          !this.externalMenu.includes('manage')
        ) {
          // 当前在管理页 如果该空间没有日志提取授权 则跳转检索页
          this.$router.push({ name: 'retrieve' });
        } else if (this.$route.name !== 'retrieve' && !this.isFirstLoad) {
          // 所有页面的子路由在切换业务的时候都统一返回到父级页面
          const { name, meta, params, query } = this.$route;
          const RoutingHop = meta.needBack && !this.isFirstLoad ? meta.backName : name ? name : 'retrieve';
          const newQuery = {
            ...query,
            spaceUid,
          };
          if (query.bizId) {
            newQuery.spaceUid = spaceUid;
            delete newQuery.bizId;
          }
          if (params.indexId) delete params.indexId;
          this.$store.commit('updateState', { pageLoading: true });
          this.$router.push({
            name: RoutingHop,
            params: {
              ...params,
            },
            query: newQuery,
          });
        }
        setTimeout(() => {
          this.$store.commit('updateState', { pageLoading: false });
          this.isFirstLoad = false;
          this.$store.commit('updateState', { showRouterLeaveTip: false });
        }, 0);
      }
    },
  },
};
