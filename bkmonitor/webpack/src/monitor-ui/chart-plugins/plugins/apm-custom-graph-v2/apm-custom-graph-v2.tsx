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

import { Component, InjectReactive, Prop, Provide, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ApmCustomGraphV2 from 'monitor-pc/pages/custom-escalation/metric-detail/components/view-main';
import {
  createOrUpdateGroupingRule,
  customTimeSeriesDetail,
  customTimeSeriesList,
  customTsGroupingRuleList,
  getCustomTimeSeriesLatestDataByFields,
  getCustomTsDimensionValues,
  getCustomTsFields,
  getCustomTsGraphConfig,
  getCustomTsMetricGroups,
  getSceneView,
  modifyCustomTsFields,
} from 'monitor-pc/pages/custom-escalation/service';
import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import type { RequestHandlerMap } from 'monitor-pc/pages/custom-escalation/metric-detail/type';

import './apm-custom-graph-v2.scss';

type GetSceneViewParams = Parameters<typeof getSceneView>[0];

interface IProps {
  timeSeriesGroupId: number;
}

@Component({
  name: 'ApmCustomGraphV2',
})
export default class ApmViewContent extends tsc<object, IProps> {
  @Prop({ default: -1, type: Number }) timeSeriesGroupId: number;
  // @ProvideReactive('timeSeriesGroupId') currentTimeSeriesGroupId: number = this.seriesGroupId;
  @Provide('requestHandlerMap') requestHandlerMap: RequestHandlerMap = {
    getCustomTsMetricGroups,
    customTimeSeriesList,
    customTimeSeriesDetail, // 详情页面暂未使用过
    getCustomTsFields, // 详情页面暂未使用
    modifyCustomTsFields,
    createOrUpdateGroupingRule, // 详情页面暂未使用
    customTsGroupingRuleList, // 详情页面暂未使用
    getCustomTimeSeriesLatestDataByFields, // 详情页面暂未使用
    getCustomTsDimensionValues,
    getCustomTsGraphConfig,
    getSceneView,
  };

  @InjectReactive('viewOptions') readonly viewOptions;

  dimenstionParams: GetSceneViewParams | null = null;

  @ProvideReactive('timeSeriesGroupId')
  get seriesGroupId() {
    return Number(this.timeSeriesGroupId);
  }

  get metricsData() {
    return customEscalationViewStore.currentSelectedMetricList.map(item => {
      return {
        name: item.metric_name,
        scope_name: item.scope_name,
      };
    });
  }

  get graphConfigParams() {
    return {
      limit: {
        function: 'top' as const, // top/bottom
        limit: 50, // 0不限制
      },
      view_column: 2,
      ...this.dimenstionParams,
      metrics: this.metricsData,
    };
  }

  handleDimensionParamsChange(payload: GetSceneViewParams) {
    this.dimenstionParams = Object.freeze(payload);
  }

  handleMetricsSelectReset() {
    this.dimenstionParams = null;
  }

  handleSideslider() {
    // 打开指标管理抽屉
    // this.seriesGroupId应用id
  }

  render() {
    return (
      <div class='apm-custom-graph-v2'>
        <ApmCustomGraphV2
          config={this.graphConfigParams}
          dimenstionParams={this.dimenstionParams}
          isApm={true}
          onDimensionParamsChange={this.handleDimensionParamsChange}
          onOpenSideslider={this.handleSideslider}
          onResetMetricsSelect={this.handleMetricsSelectReset}
        />
      </div>
    );
  }
}
