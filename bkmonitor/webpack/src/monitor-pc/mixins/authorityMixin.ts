/* eslint-disable @typescript-eslint/naming-convention */
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
import { Component, Provide, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getAuthById, setAuthById } from '../common/auth-store';
import authorityStore from '@store/modules/authority';

Component.registerHooks(['beforeRouteEnter']);

export default (authMap: { [propsName: string]: string }, inCreated = true) => {
  class authorityMixin extends tsc<undefined> {
    __bizIdUnWatch__: any;
    authLoading = false;
    dataLoading = false;
    isQueryAuthDone = false;
    @ProvideReactive('authority') authority: { [propsName: string]: boolean } = {};
    @Provide('authorityMap') authorityMap = authMap;
    constructor() {
      super();
      this.authority = Object.keys(authMap).reduce((pre: any, cur: string) => {
        pre[cur] = false;
        return pre;
      }, {});
    }
    get __BizId__() {
      return this.$store.getters.bizId;
    }
    get hasPageViewAuth() {
      if (this.$store.getters.is_superuser) return true;
      const actionId = this.$route.meta?.authority?.page;
      if (!actionId) return true;
      // if (this.authority.VIEW_AUTH) return false;
      return getAuthById(actionId, this.__BizId__) || this.authority.VIEW_AUTH;
    }
    // 显示申请权限的详情
    @Provide('handleShowAuthorityDetail')
    handleShowAuthorityDetail(actionId?: string) {
      authorityStore.getAuthorityDetail(actionId || this.$route.meta.authority?.map?.MANAGE_AUTH);
    }
    created() {
      if (inCreated) {
        this.getAuthCreated();
      }
    }

    async getAuthCreated() {
      const authorityMap: any = authMap || (this.$route.meta.authority?.map ? this.$route.meta.authority.map : false);
      const isSpecialEvent =
        ['event-center', 'event-center-detail'].includes(this.$route.name) && location.search.indexOf('specEvent') > -1;
      if (!authorityMap) {
        return;
      }
      await this.handleInitPageAuthority(
        Array.from(new Set((Object.values(authorityMap) as any).flat(2))),
        isSpecialEvent
      );
    }
    // 初始化通用页面权限
    async handleInitPageAuthority(actionList: string[], isSpecialEvent: boolean) {
      this.authLoading = true;
      this.isQueryAuthDone = false;
      try {
        // 临时分享模式下 前端不再做权限校验 一致交由api判断
        const isShareView = (window.__POWERED_BY_BK_WEWEB__ && window.token) || window.is_superuser;
        let data: {
          actionId: string;
          isAllowed: boolean;
        }[] = [];
        const realFetchActionIds = actionList.filter(actionId => !getAuthById(actionId));
        if (!isShareView && realFetchActionIds.length) {
          data = await authorityStore.checkAllowedByActionIds({
            action_ids: realFetchActionIds,
          });
        }
        for (const [key, value] of Object.entries(authMap)) {
          if (getAuthById(value)) {
            this.$set(this.authority, key, true);
            continue;
          }
          if (isShareView) {
            this.$set(this.authority, key, true);
            setAuthById(authMap[key], true);
          } else {
            const isViewAuth = key.indexOf('VIEW_AUTH') > -1;
            if (Array.isArray(value)) {
              const filterData = data?.filter(item => value.includes(item.actionId)) || [];
              if (filterData.length) {
                const hasAuth = !!filterData.length && filterData.every(item => item.isAllowed);
                filterData.length && this.$set(this.authority, key, isViewAuth ? isSpecialEvent || hasAuth : hasAuth);
                setAuthById(authMap[key], isViewAuth ? isSpecialEvent || hasAuth : hasAuth);
              }
            } else {
              const curEntry = data.find(item => item.actionId === value);
              if (curEntry) {
                const hasAuth = isViewAuth ? isSpecialEvent || curEntry.isAllowed : curEntry.isAllowed;
                this.$set(this.authority, key, hasAuth);
                setAuthById(authMap[key], hasAuth);
              }
            }
          }
        }
      } catch (e) {
        console.error(e);
      } finally {
        this.authLoading = false;
        this.isQueryAuthDone = true;
      }
    }
  }
  return Component(authorityMixin);
};
