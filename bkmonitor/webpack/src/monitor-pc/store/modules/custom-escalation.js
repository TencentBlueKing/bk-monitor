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
  createOrUpdateGroupingRule,
  customTimeSeriesDetail,
  customTimeSeriesList,
  deleteCustomEventGroup,
  deleteCustomTimeSeries,
  deleteGroupingRule,
  getCustomEventGroup,
  getCustomTimeSeriesLatestDataByFields,
  getCustomTsFields,
  modifyCustomEventGroup,
  modifyCustomTimeSeries,
  modifyCustomTsFields,
  previewGroupingRule,
  proxyHostInfo,
  queryCustomEventGroup,
  updateGroupingRuleOrder,
  validateCustomEventGroupName,
  validateCustomTsGroupName,
} from 'monitor-api/modules/custom_report';
import { getScenarioList } from 'monitor-api/modules/strategies';
import { transformDataKey } from 'monitor-common/utils/utils';

const actions = {
  //  获取监控对象列表
  async getScenarioList() {
    const data = await getScenarioList().catch(() => []);
    return data;
  },

  //  获取自定义指标列表
  async getCustomTimeSeriesList(_, params) {
    const data = await customTimeSeriesList(params).catch(() => ({ list: [], total: 0 }));
    return transformDataKey(data);
  },

  //  获取自定义指标详情
  async getCustomTimeSeriesDetail(_, params) {
    const data = await customTimeSeriesDetail(params).catch(() => ({}));
    return data;
  },
  //  获取自定义指标详情
  async getCustomTSFields(_, params) {
    const data = await getCustomTsFields(params).catch(() => ({}));
    return data;
  },
  //  修改自定义指标详情
  async modifyCustomTsFields(_, params) {
    const data = await modifyCustomTsFields(params).catch(() => ({}));
    return data;
  },

  //  保存指标分组排序
  async saveGroupingRuleOrder(_, params) {
    const data = await updateGroupingRuleOrder(params).catch(() => ({}));
    return data;
  },

  //  编辑自定义指标配置
  async editCustomTime(_, params) {
    const data = await modifyCustomTimeSeries(params, { needMessage: false }).catch(() => []);
    return transformDataKey(data);
  },

  //  删除自定义指标
  async deleteCustomTimeSeries(_, params) {
    const data = await deleteCustomTimeSeries(params)
      .then(() => true)
      .catch(() => false);
    return transformDataKey(data);
  },

  //  获取云区域proxy信息
  async getProxyInfo() {
    const data = await proxyHostInfo().catch(() => []);
    return transformDataKey(data);
  },

  //  获取自定义事件列表
  async getCustomEventList(_, params) {
    const data = await queryCustomEventGroup(params).catch(() => ({ list: [], total: 0 }));
    return transformDataKey(data);
  },

  //  获取自定义事件配置详情
  async getCustomEventDetail(_, params) {
    const data = await getCustomEventGroup(params).catch(() => ({ event_info_list: [] }));
    return data;
  },

  //  编辑自定义事件配置
  async editCustomEvent(_, params) {
    const data = await modifyCustomEventGroup(params).catch(() => false);
    return transformDataKey(data);
  },

  //  删除自定义事件配置
  async deleteCustomEvent(_, params) {
    const data = await deleteCustomEventGroup(params)
      .then(() => true)
      .catch(() => false);
    return transformDataKey(data);
  },

  //  校验事件名称
  validateCustomEventName(_, { params, options }) {
    return validateCustomEventGroupName(params, options).catch(err => err);
  },

  //  校验指标名称
  validateCustomTimetName(_, { params, options }) {
    return validateCustomTsGroupName(params, options).catch(err => err);
  },
  async getCustomTimeSeriesLatestDataByFields(_, params) {
    const data = await getCustomTimeSeriesLatestDataByFields(params).catch(() => false);
    return data;
  },

  /* 根据分组规则获取预览信息 */
  async getGroupRulePreviews(_, params) {
    const data = await previewGroupingRule(params).catch(() => false);
    return data;
  },

  /* 删除分组 */
  async deleteGroupingRule(_, params) {
    const data = await deleteGroupingRule(params).catch(() => false);
    return data;
  },

  /* 创建/更新分组 */
  async createOrUpdateGroupingRule(_, params) {
    const data = await createOrUpdateGroupingRule(params).catch(() => false);
    return data;
  },
};

export default {
  namespaced: true,
  actions,
};
