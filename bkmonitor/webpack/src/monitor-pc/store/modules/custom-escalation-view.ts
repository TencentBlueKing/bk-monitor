import { makeMap } from 'monitor-common/utils/make-map';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import store from '../store';

import type { getCustomTsMetricGroups } from '../../pages/custom-escalation/metric-detail/services/scene_view_new';

interface GroupItem {
  groupName: string;
  metricsName: string[];
}

type TCustomTsMetricGroups = ServiceReturnType<typeof getCustomTsMetricGroups>;

/** 自定义指标时间范围本地存储 key（仅在此模块内部使用） */
const CUSTOM_METRIC_TIME_RANGE_KEY = '__CUSTOM_METRIC_TIME_RANGE__';

/** 默认时间范围 */
const DEFAULT_TIME_RANGE: [string, string] = ['now-1h', 'now'];

@Module({ name: 'customEscalationView', dynamic: true, namespaced: true, store })
class CustomEscalationViewStore extends VuexModule {
  // public commonDimensionList: Readonly<TCustomTsMetricGroups['common_dimensions']> = [];
  public currentSelectedGroupAndMetricNameList: GroupItem[] = [];
  // public currentSelectedMetricNameList: string[] = [];
  public endTime = DEFAULT_TIME_RANGE[1];
  public metricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  public startTime = DEFAULT_TIME_RANGE[0];
  public timeSeriesGroupId = -1;

  // 过滤条件(并集)：通过currentSelectedGroupNameList在metricGroupList中找到对应的common_dimensions
  get commonDimensionList() {
    const selectedGroupNames = new Set(this.currentSelectedMetricList.map(i => i.scope_name));
    const currentSelectedCommonDimensionList: TCustomTsMetricGroups['metric_groups'][number]['common_dimensions'] = [];
    const seen = new Set();
    // 获取已选择的指标分组的过滤条件数据(common_dimensions)
    for (const group of this.metricGroupList) {
      if (selectedGroupNames.has(group.name)) {
        for (const dimension of group.common_dimensions) {
          const identifier = dimension.name; // 去重标识符，相同name没必要多次显示
          if (!seen.has(identifier)) {
            seen.add(identifier);
            currentSelectedCommonDimensionList.push(dimension);
          }
        }
      }
    }
    return currentSelectedCommonDimensionList;
  }

  get currentSelectedMetricList() {
    const result: (TCustomTsMetricGroups['metric_groups'][number]['metrics'][0] & { scope_name: string })[] = [];
    for (const groupItem of this.metricGroupList) {
      for (const metricsItem of groupItem.metrics) {
        const metricName = metricsItem.metric_name;
        // 检查该 metric_name 是否在当前分组的 metricKeyMap 中
        const groupNames = this.currentSelectedGroupAndMetricNameList
          .filter(item => item.metricsName.includes(metricName))
          .map(item => item.groupName);
        // 如果 metricName 对应的 groupName 存在，添加到结果中
        if (groupNames.includes(groupItem.name)) {
          result.push({
            ...metricsItem,
            scope_name: groupItem.name, // 每个 metric 都附带其分组名称
          });
        }
      }
    }
    return result;
  }

  get dimensionAliasNameMap() {
    return this.currentSelectedMetricList.reduce<Record<string, string>>((result, groupItem) => {
      for (const dimensionItem of groupItem.dimensions) {
        // 如果 alias 存在，则直接赋值；否则保持原值
        if (dimensionItem.alias) {
          result[dimensionItem.name] = dimensionItem.alias;
        } else if (!(dimensionItem.name in result)) {
          // 如果当前别名为空且之前没有赋值，则保留为空字符串
          result[dimensionItem.name] = '';
        }
      }
      return result;
    }, {});
  }

  get timeRangTimestamp() {
    return handleTransformToTimestamp([this.startTime, this.endTime]);
  }

  @Mutation
  public initTimeRangeFromStorage() {
    // 从本地存储初始化时间范围（按业务ID读取）
    const bizId = window.cc_biz_id || window.bk_biz_id;
    if (bizId) {
      const timeRange = getTimeRangeFromStorage(bizId);
      [this.startTime, this.endTime] = timeRange;
    }
  }

  // @Mutation
  // public updateCommonDimensionList(payload: TCustomTsMetricGroups['common_dimensions']) {
  //   this.commonDimensionList = Object.freeze(payload);
  // }

  @Mutation
  public updateCurrentSelectedGroupAndMetricNameList(payload: GroupItem[]) {
    this.currentSelectedGroupAndMetricNameList = payload;
  }

  // @Mutation
  // public updateCurrentSelectedMetricNameList(payload: string[]) {
  //   this.currentSelectedMetricNameList = payload;
  // }

  @Mutation
  public updateMetricGroupList(payload: TCustomTsMetricGroups['metric_groups']) {
    this.metricGroupList = Object.freeze(payload);
  }

  @Mutation
  public updateTimeRange(payload: [string, string]) {
    [this.startTime, this.endTime] = payload;
    // 保存时间范围到本地存储（按业务ID存储）
    const bizId = window.cc_biz_id || window.bk_biz_id;
    if (bizId) {
      saveTimeRangeToStorage(bizId, payload);
    }
  }

  @Mutation
  public updateTimeSeriesGroupId(payload: number) {
    this.timeSeriesGroupId = payload;
  }
}

/**
 * 从本地存储获取自定义指标时间范围
 * @param {number | string} bizId 业务ID
 * @returns {[string, string]} 时间范围
 */
function getTimeRangeFromStorage(bizId: number | string): [string, string] {
  try {
    const storageData = localStorage.getItem(CUSTOM_METRIC_TIME_RANGE_KEY);
    if (storageData) {
      const data = JSON.parse(storageData);
      if (data[bizId] && Array.isArray(data[bizId]) && data[bizId].length === 2) {
        return data[bizId] as [string, string];
      }
    }
  } catch (e) {
    console.warn('Failed to parse custom metric time range from localStorage:', e);
  }
  return DEFAULT_TIME_RANGE;
}

/**
 * 保存自定义指标时间范围到本地存储
 * @param {number | string} bizId 业务ID
 * @param {[string, string]} timeRange 时间范围
 */
function saveTimeRangeToStorage(bizId: number | string, timeRange: [string, string]) {
  try {
    const storageData = localStorage.getItem(CUSTOM_METRIC_TIME_RANGE_KEY);
    const data = storageData ? JSON.parse(storageData) : {};
    data[bizId] = timeRange;
    localStorage.setItem(CUSTOM_METRIC_TIME_RANGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn('Failed to save custom metric time range to localStorage:', e);
  }
}

export default getModule(CustomEscalationViewStore);
