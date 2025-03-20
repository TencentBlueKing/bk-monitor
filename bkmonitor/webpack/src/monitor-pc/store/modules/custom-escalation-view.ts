import { type getCustomTsMetricGroups } from 'monitor-api/modules/scene_view_new';
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
import { Module, VuexModule, getModule, Mutation } from 'vuex-module-decorators';

import store from '../store';

type TCustomTsMetricGroups = ServiceReturnType<typeof getCustomTsMetricGroups>;

@Module({ name: 'customEscalationView', dynamic: true, namespaced: true, store })
class CustomEscalationViewStore extends VuexModule {
  public commonDimensionList: Readonly<TCustomTsMetricGroups['common_dimensions']> = [];
  // 当前视图选中的指标
  // public currentSelectedMetricList: Readonly<TCustomTsMetricGroups['metric_groups'][number]['metrics']> = [];
  public currentSelectedMetricNameList: string[] = [];
  public endTime = 'now';
  public metricGroupList: Readonly<TCustomTsMetricGroups['metric_groups']> = [];
  public startTime = 'now-1h';
  public timeSeriesGroupId = -1;

  get currentSelectedMetricList() {
    const metricKeyMap = makeMap(this.currentSelectedMetricNameList);
    return this.metricGroupList.reduce<TCustomTsMetricGroups['metric_groups'][number]['metrics']>(
      (result, groupItem) => {
        groupItem.metrics.forEach(metricsItem => {
          if (metricKeyMap[metricsItem.metric_name]) {
            result.push(metricsItem);
          }
        });
        return result;
      },
      []
    );
  }

  get timeRangTimestamp() {
    return handleTransformToTimestamp([this.startTime, this.endTime]);
  }

  @Mutation
  public updateCommonDimensionList(payload: TCustomTsMetricGroups['common_dimensions']) {
    // this.commonDimensionList = Object.freeze(payload);
    this.commonDimensionList = Object.freeze([
      ...payload,
      ...[
        {
          name: 'bk_biz_id',
          alias: 'alias_bk_biz_id',
        },
        {
          name: 'bk_os_name',
          alias: 'alias_bk_os_name',
        },
        {
          name: 'bk_os_type',
          alias: 'alias_bk_os_type',
        },
        {
          name: 'bk_men',
          alias: 'alias_bk_men',
        },
        {
          name: 'bk_cloudn',
          alias: 'alias_bk_cloudn',
        },
        {
          name: 'bk_area',
          alias: 'alias_bk_area',
        },
      ],
    ]);
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
