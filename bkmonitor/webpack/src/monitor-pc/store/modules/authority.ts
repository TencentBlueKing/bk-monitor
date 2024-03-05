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
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';
import { checkAllowedByActionIds, getAuthorityDetail, getAuthorityMeta } from 'monitor-api/modules/iam';
import { transformDataKey } from 'monitor-common/utils/utils';

import store from '../store';

// eslint-disable-next-line new-cap
@Module({ name: 'authority', dynamic: true, namespaced: true, store })
class Authority extends VuexModule {
  public authorityMeta: any = [];
  public showAuthortyDialog = false;
  public dialogLoading = false;
  public authApplyUrl = '';
  public authDetail: any = {};
  public get showDialog() {
    return this.showAuthortyDialog;
  }
  public get loading() {
    return this.dialogLoading;
  }
  public get applyUrl() {
    return this.authApplyUrl;
  }
  public get authorityDetail() {
    return this.authDetail;
  }
  @Mutation
  public setAuthorityMeta(data: any) {
    this.authorityMeta = data;
  }
  @Mutation
  public setShowAuthortyDialog(data: boolean) {
    this.showAuthortyDialog = data;
  }
  @Mutation
  public setDialogLoading(data: boolean) {
    this.dialogLoading = data;
  }
  @Mutation
  public setApplyUrl(data: string) {
    this.authApplyUrl = data;
  }
  @Mutation
  public setAuthorityDetail(data: any) {
    this.authDetail = data;
  }
  @Action // 获取系统所有权限对应表
  public async getAuthorityMeta() {
    const data = await getAuthorityMeta().catch(() => []);
    this.setAuthorityMeta(transformDataKey(data));
  }
  @Action // 通过actionId获取对应权限及依赖的权限的详情，及申请权限的跳转Url
  public async getAuthorityDetail(actionId: string | string[]) {
    this.setDialogLoading(true);
    this.setShowAuthortyDialog(true);
    const res = await this.handleGetAuthDetail(actionId);
    const data = transformDataKey(res);
    this.setApplyUrl(data.applyUrl);
    this.setAuthorityDetail(data.authorityList);
    this.setDialogLoading(false);
  }
  @Action
  public async handleGetAuthDetail(actionId: string | string[]) {
    const res = await getAuthorityDetail({
      action_ids: Array.isArray(actionId) ? actionId : [actionId]
    }).catch(() => ({ applyUrl: '', authorityList: {} }));
    return res;
  }
  @Action
  public showAuthorityDetail(res: any) {
    if (!Array.isArray(res) && !res?.data && !res.permission) return;
    this.setDialogLoading(true);
    this.setShowAuthortyDialog(true);
    const data = transformDataKey(res);
    this.setApplyUrl(data.data.applyUrl);
    this.setAuthorityDetail(data.permission);
    this.setDialogLoading(false);
  }
  @Action // 通过actionIds获取对应权限是否放行
  public async checkAllowedByActionIds(params: any) {
    const data = await checkAllowedByActionIds({
      ...params,
      bk_biz_id: store.getters.bizId || window.cc_biz_id,
      space_uid: window.space_uid
    }).catch(() => []);
    return transformDataKey(data);
  }
}

export default getModule(Authority);
