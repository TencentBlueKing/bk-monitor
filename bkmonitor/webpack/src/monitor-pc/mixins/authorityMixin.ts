/* eslint-disable no-param-reassign */
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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import authorityStore from '@store/modules/authority';

Component.registerHooks(['beforeRouteEnter']);
// eslint-disable-next-line new-cap
export default (authMap: { [propsName: string]: string }) =>
  Component(
    class authorityMixin extends tsc<{}> {
      // authority: Record<string, boolean>;
      __bizIdUnWatch__: any;
      constructor() {
        super();
        this.authority = Object.keys(authMap).reduce((pre: any, cur: string) => ((pre[cur] = false), pre), {});
      }
      get __BizId__() {
        return this.$store.getters.bizId;
      }
      // beforeRouteEnter(to: any, from: any, next: any) {
      //   next((vm: any) => {
      //     if (vm?.showGuidePage) return;
      //     const authorityMap: any = authMap || (to.meta.authority?.map ? to.meta.authority.map : false);
      //     const isSpecialEvent =
      //       ['event-center', 'event-center-detail'].includes(to.name) && location.search.indexOf('specEvent') > -1;
      //     authorityMap &&
      //       vm.handleInitPageAuthority(
      //         Array.from(new Set((Object.values(authorityMap) as any).flat(2))),
      //         isSpecialEvent
      //       );
      //   });
      // }
      created() {
        // if (this?.showGuidePage) return;
        const authorityMap: any = authMap || (this.$route.meta.authority?.map ? this.$route.meta.authority.map : false);
        const isSpecialEvent =
          ['event-center', 'event-center-detail'].includes(this.$route.name) &&
          location.search.indexOf('specEvent') > -1;
        authorityMap &&
          this.handleInitPageAuthority(
            Array.from(new Set((Object.values(authorityMap) as any).flat(2))),
            isSpecialEvent
          );
      }
      // created() {
      //   if ((this as any).showGuide) return;
      //   if (
      //     !location.hash.includes('#/share/') &&
      //     !(window.__POWERED_BY_BK_WEWEB__ && window.token) &&
      //     attachMethod === 'created'
      //   ) {
      //     authMap && this.handleInitPageAuthority(Array.from(new Set((Object.values(authMap) as any).flat(2))), false);
      //   }
      // }
      // mounted() {
      //   console.info(this.$route.name, '+++++++++++++++++');
      //   this.__bizIdUnWatch__ = this.$watch('__BizId__', (v, old) => {
      //     if (this?.showGuidePage) return;
      //     const authorityMap: any = authMap || this.$route.meta.authority?.map;
      //     const isSpecialEvent =
      //       ['event-center', 'event-center-detail'].includes(this.$route.name) &&
      //       location.search.indexOf('specEvent') > -1;
      //     debugger;
      //     authorityMap &&
      //       this.handleInitPageAuthority(
      //         Array.from(new Set((Object.values(authorityMap) as any).flat(2))),
      //         isSpecialEvent
      //       );
      //   });
      // }
      // 初始化通用页面权限
      public async handleInitPageAuthority(actionList: string[], isSpecialEvent: boolean) {
        // 临时分享模式下 前端不再做权限校验 一致交由api判断
        const isShareView = window.__POWERED_BY_BK_WEWEB__ && window.token;
        let data: {
          actionId: string;
          isAllowed: boolean;
        }[] = [];
        if (!isShareView) {
          data = await authorityStore.checkAllowedByActionIds({
            action_ids: actionList
          });
        }
        Object.entries(authMap).forEach(entry => {
          const [key, value] = entry;
          if (isShareView) {
            this.$set(this.authority, key, true);
          } else {
            const isViewAuth = key.indexOf('VIEW_AUTH') > -1;
            if (Array.isArray(value)) {
              const filterData = data?.filter(item => value.includes(item.actionId));
              const hasAuth = filterData?.every(item => item.isAllowed);
              filterData.length && this.$set(this.authority, key, isViewAuth ? isSpecialEvent || hasAuth : hasAuth);
            } else {
              const curEntry = data.find(item => item.actionId === value);
              curEntry &&
                this.$set(this.authority, key, isViewAuth ? isSpecialEvent || curEntry.isAllowed : curEntry.isAllowed);
            }
          }
        });
      }
      // 显示申请权限的详情
      public handleShowAuthorityDetail(actionId: string) {
        authorityStore.getAuthorityDetail(actionId || this.$route.meta.authority?.map?.MANAGE_AUTH);
      }
    }
  );
