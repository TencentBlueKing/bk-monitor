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

import { Component } from 'vue-property-decorator';
import { Component as tsx } from 'vue-tsx-support';

import authorityStore from '../store/modules/authority';

Component.registerHooks(['beforeRouteEnter']);

export default (authMap: { [propsName: string]: string }) =>
  Component(
    class authorityMixin extends tsx<object> {
      public authority: { [propsName: string]: boolean } = {};
      public constructor() {
        super();

        this.authority = Object.keys(authMap).reduce((pre: any, cur: string) => ((pre[cur] = false), pre), {});
      }
      public beforeRouteEnter(to: any, from: any, next: any) {
        next((vm: any) => {
          const authorityMap: any = authMap || (to.meta.authority?.map ? to.meta.authority.map : false);
          const isSpecialEvent = false;
          const resource = vm.authorityResource;

          authorityMap &&
            vm.handleInitPageAuthority(
              Array.from(new Set(Object.values(authorityMap).flat(2))),
              resource,
              isSpecialEvent
            );
        });
      }
      // 初始化通用页面权限
      public async handleInitPageAuthority(
        actionList: string[],
        resource: { [key: string]: string },
        isSpecialEvent: boolean
      ) {
        const data: { actionId: string; isAllowed: boolean }[] = await authorityStore.checkAllowedByApmApplication({
          action_ids: actionList,
          ...resource,
        });
        Object.entries(authMap).forEach(entry => {
          const [key, value] = entry;
          const isViewAuth = key.indexOf('VIEW_AUTH') > -1;
          if (Array.isArray(value)) {
            const filterData = data.filter(item => value.includes(item.actionId));
            const hasAuth = filterData.every(item => item.isAllowed);
            filterData.length && this.$set(this.authority, key, isViewAuth ? isSpecialEvent || hasAuth : hasAuth);
          } else {
            const curEntry = data.find(item => item.actionId === value);

            curEntry &&
              this.$set(this.authority, key, isViewAuth ? isSpecialEvent || curEntry.isAllowed : curEntry.isAllowed);
          }
        });
      }
      // 显示申请权限的详情
      public handleShowAuthorityDetail(actionId: string) {
        authorityStore.getAuthorityDetail(actionId || this.$route.meta.authority?.map?.MANAGE_AUTH);
      }
    }
  );
