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

import {
  actionDateHistogram,
  alertDateHistogram,
  alertEventCount,
  alertRelatedInfo,
  exportAction,
  exportAlert,
  listAllowedBiz,
  listSearchHistory,
  searchAction,
  searchAlert,
} from 'monitor-api/modules/alert';
import { exportIncident } from 'monitor-api/modules/incident';
import {
  createSearchFavorite,
  destroySearchFavorite,
  listSearchFavorite,
  partialUpdateSearchFavorite,
} from 'monitor-api/modules/model';
import { Action, getModule, Module, VuexModule } from 'vuex-module-decorators';

import store from '@store/store';

// import type { IDimensionItem } from '@/pages/event/typings/event';
// const sleep = async (timer = 1000) => await new Promise(resolve => setTimeout(resolve, timer))
@Module({ name: 'event', dynamic: true, namespaced: true, store })
class Event extends VuexModule {
  @Action
  // 新建告警搜索条件收藏
  async createSearchFavorite(params) {
    return await createSearchFavorite(params).catch(() => false);
  }

  @Action
  // 删除告警搜索条件收藏
  async destroySearchFavorite(params) {
    return await destroySearchFavorite(params)
      .then(() => true)
      .catch(() => false);
  }

  @Action
  async exportActionData(params) {
    return await exportAction(params, { needCancel: true }).catch(() => ({ download_path: '', download_name: '' }));
  }

  @Action
  // 导出告警数据
  async exportAlertData(params) {
    return await exportAlert(params, { needCancel: true }).catch(() => ({ download_path: '', download_name: '' }));
  }
  @Action
  // 导出故障数据
  async exportIncidentData(params) {
    return await exportIncident(params, { needCancel: true }).catch(() => ({ download_path: '', download_name: '' }));
  }
  @Action
  // 获取执行趋势图数据
  async getActionDateHistogram(params) {
    return await actionDateHistogram(params, { needRes: true, needMessage: false, needCancel: true });
  }
  @Action
  // 获取告警趋势图表
  async getAlertDateHistogram(params) {
    return await alertDateHistogram(params, { needRes: true, needMessage: false, needCancel: true });
  }
  @Action
  // 告警关联事件数量
  async getAlertEventCount(params) {
    return await alertEventCount(params, { needCancel: true }).catch(() => false);
  }
  @Action
  // 告警关联信息查询
  async getAlertRelatedInfo(params) {
    return await alertRelatedInfo(params, { needCancel: true }).catch(() => ({}));
  }
  @Action
  // 查询有权限的业务列表
  async getAllowedBizList(action_id = 'view_business_v2') {
    return await listAllowedBiz({ action_id }).catch(() => []);
  }
  @Action
  // 获取告警搜索条件收藏列表
  async getListSearchFavorite(params) {
    return await listSearchFavorite(params).catch(() => []);
    // return data?.fliter(item => item?.params?.query_string) || []
  }
  @Action
  // 获取最近搜索条件
  async getListSearchHistory(params) {
    return await listSearchHistory(params, { needCancel: true }).catch(() => []);
    // return data?.fliter(item => item?.params?.query_string) || []
  }
  @Action
  // 查询处理记录列表
  async getSearchActionList(params) {
    return await searchAction(params, { needRes: true, needMessage: false, needCancel: true });
  }
  @Action
  async getSearchAlertList(params) {
    return await searchAlert(params, { needRes: true, needMessage: false, needCancel: true });
  }
  @Action
  // 修改告警搜索条件收藏
  async updateSearchFavorite(params) {
    return await partialUpdateSearchFavorite(params.id, { name: params.params.name }).catch(() => false);
  }
}
export default getModule(Event);
