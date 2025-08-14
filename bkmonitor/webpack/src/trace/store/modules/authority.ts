/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import {
  checkAllowedByActionIds,
  getAuthorityApplyInfo,
  getAuthorityDetail,
  getAuthorityMeta,
} from 'monitor-api/modules/iam';
import { transformDataKey } from 'monitor-common/utils/utils';
import { defineStore } from 'pinia';

export interface IAuthorityState {
  authApplyUrl: string;
  authDetail: any;
  authorityMeta: any[];
  dialogLoading: boolean;
  showAuthortyDialog: boolean;
}

export interface IInstanceAuthResource {
  id: number | string;
  type: string;
}

export async function getAuthorityMap(authorityMap: { [key: string]: string }) {
  const authority = {};
  const data = await checkAllowedByActionIds({
    action_ids: Array.from(new Set((Object.values(authorityMap) as any).flat(2))),
    bk_biz_id: window.cc_biz_id,
  }).catch(() => []);
  Object.entries(authorityMap).forEach(entry => {
    const [key, value] = entry;
    if (Array.isArray(value)) {
      const filterData = data?.filter(item => value.includes(item.action_id));
      const hasAuth = filterData?.every(item => item.is_allowed);
      if (filterData.length) {
        authority[key] = hasAuth;
      }
    } else {
      const curEntry = data.find(item => item.action_id === value);
      if (curEntry) {
        authority[key] = curEntry.is_allowed;
      }
    }
  });
  return authority;
}

export const useAuthorityStore = defineStore('authority', {
  state: (): IAuthorityState => ({
    authorityMeta: [],
    showAuthortyDialog: false,
    dialogLoading: false,
    authApplyUrl: '',
    authDetail: {},
  }),
  getters: {
    showDialog: state => state.showAuthortyDialog,
    loading: state => state.dialogLoading,
    applyUrl: state => state.authApplyUrl,
    authorityDetail: state => state.authDetail,
  },
  actions: {
    setAuthorityMeta(data: any) {
      this.authorityMeta = data;
    },
    setShowAuthortyDialog(data: boolean) {
      this.showAuthortyDialog = data;
    },
    setDialogLoading(data: boolean) {
      this.dialogLoading = data;
    },
    setApplyUrl(data: string) {
      this.authApplyUrl = data;
    },
    setAuthorityDetail(data: any) {
      this.authDetail = data;
    },
    // 获取系统所有权限对应表
    async getAuthorityMeta() {
      const data = await getAuthorityMeta().catch(() => []);
      this.setAuthorityMeta(transformDataKey(data));
    },
    // 通过actionId获取对应权限及依赖的权限的详情，及申请权限的跳转Url
    async getAuthorityDetail(actionId: string | string[]) {
      this.setDialogLoading(true);
      this.setShowAuthortyDialog(true);
      const res = await this.handleGetAuthDetail(actionId);
      const data = transformDataKey(res);
      this.setApplyUrl(data.applyUrl);
      this.setAuthorityDetail(data.authorityList);
      this.setDialogLoading(false);
    },
    async handleGetAuthDetail(actionId: string | string[]) {
      const res = await getAuthorityDetail({
        action_ids: Array.isArray(actionId) ? actionId : [actionId],
      }).catch(() => ({ applyUrl: '', authorityList: {} }));
      return res;
    },
    // 通过actionId、resouce获取对应实例的权限详情，及申请权限的跳转Url
    async getIntanceAuthDetail(actionId: string | string[], resources: IInstanceAuthResource[], bizId?: number) {
      this.setDialogLoading(true);
      this.setShowAuthortyDialog(true);
      const res = await this.handleIntanceAuthDetail(actionId, resources, bizId);
      const data = transformDataKey(res);
      this.setApplyUrl(data.applyUrl);
      this.setAuthorityDetail(data.authorityList);
      this.setDialogLoading(false);
    },
    async handleIntanceAuthDetail(actionId: string | string[], resources: IInstanceAuthResource[], bizId?: number) {
      const res = await getAuthorityApplyInfo({
        action_ids: Array.isArray(actionId) ? actionId : [actionId],
        resources,
        bk_biz_id: bizId || window.cc_biz_id,
      }).catch(() => ({ applyUrl: '', authorityList: {} }));
      return res;
    },
    showAuthorityDetail(res: any) {
      this.setDialogLoading(true);
      this.setShowAuthortyDialog(true);
      const data = transformDataKey(res);
      this.setApplyUrl(data.data.applyUrl);
      this.setAuthorityDetail(data.permission);
      this.setDialogLoading(false);
    },
    // 通过actionIds获取对应权限是否放行
    async checkAllowedByActionIds(params: any) {
      const data = await checkAllowedByActionIds({
        ...params,
        bk_biz_id: window.cc_biz_id,
      }).catch(() => []);
      return transformDataKey(data);
    },
  },
});
