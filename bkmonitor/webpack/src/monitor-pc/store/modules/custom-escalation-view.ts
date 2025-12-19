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

@Module({ name: 'customEscalationView', dynamic: true, namespaced: true, store })
class CustomEscalationViewStore extends VuexModule {
  // public commonDimensionList: Readonly<TCustomTsMetricGroups['common_dimensions']> = [];
  public currentSelectedGroupAndMetricNameList: GroupItem[] = [];
  // public currentSelectedMetricNameList: string[] = [];
  public endTime = 'now';
  public metricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  public startTime = 'now-1h';
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

  // get currentSelectedMetricList() {
  //   // const metricKeyMap = makeMap(this.currentSelectedMetricNameList);
  //   const metricKeyMap = {};
  //   for (const item of this.currentSelectedGroupAndMetricNameList) {
  //     for (const metric of item.metricsName) {
  //       metricKeyMap[metric] = true;
  //     }
  //   }
  //   const result: (TCustomTsMetricGroups['metric_groups'][number]['metrics'][0] & { scope_name: string })[] = [];
  //   const repeatMap: Record<string, boolean> = {};
  //   for (const groupItem of this.metricGroupList) {
  //     for (const metricsItem of groupItem.metrics) {
  //       if (repeatMap[metricsItem.metric_name]) {
  //         break;
  //       }
  //       if (metricKeyMap[metricsItem.metric_name]) {
  //         repeatMap[metricsItem.metric_name] = true;
  //         result.push({
  //           ...metricsItem,
  //           scope_name: groupItem.name,
  //         });
  //       }
  //     }
  //   }
  //   return result;
  // }

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
  }

  @Mutation
  public updateTimeSeriesGroupId(payload: number) {
    this.timeSeriesGroupId = payload;
  }
}

export default getModule(CustomEscalationViewStore);
