import { makeMap } from 'monitor-common/utils/make-map';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
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
import { getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import store from '../store';

import type { getCustomTsMetricGroups } from '../../pages/custom-escalation/new-metric-view/services/scene_view_new';

type TCustomTsMetricGroups = ServiceReturnType<typeof getCustomTsMetricGroups>;

@Module({ name: 'customEscalationView', dynamic: true, namespaced: true, store })
class CustomEscalationViewStore extends VuexModule {
  public commonDimensionList: Readonly<TCustomTsMetricGroups['common_dimensions']> = [];
  public currentSelectedMetricNameList: string[] = [];
  public endTime = 'now';
  public metricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  public startTime = 'now-1h';
  public timeSeriesGroupId = -1;

  get currentSelectedMetricList() {
    const metricKeyMap = makeMap(this.currentSelectedMetricNameList);
    const result: TCustomTsMetricGroups['metric_groups'][number]['metrics'] = [];
    const repeatMap: Record<string, boolean> = {};

    for (const groupItem of this.metricGroupList) {
      for (const metricsItem of groupItem.metrics) {
        if (repeatMap[metricsItem.metric_name]) {
          break;
        }
        if (metricKeyMap[metricsItem.metric_name]) {
          repeatMap[metricsItem.metric_name] = true;
          result.push(metricsItem);
        }
      }
    }
    return result;
  }

  get dimensionAliasNameMap() {
    return this.metricGroupList.reduce<Record<string, string>>((result, groupItem) => {
      for (const metricsItem of groupItem.metrics) {
        for (const dimensionItem of metricsItem.dimensions) {
          Object.assign(result, {
            [dimensionItem.name]: dimensionItem.alias,
          });
        }
      }
      return result;
    }, {});
  }

  get timeRangTimestamp() {
    return handleTransformToTimestamp([this.startTime, this.endTime]);
  }

  @Mutation
  public updateCommonDimensionList(payload: TCustomTsMetricGroups['common_dimensions']) {
    this.commonDimensionList = Object.freeze(payload);
  }

  @Mutation
  public updateCurrentSelectedMetricNameList(payload: string[]) {
    this.currentSelectedMetricNameList = payload;
  }

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
