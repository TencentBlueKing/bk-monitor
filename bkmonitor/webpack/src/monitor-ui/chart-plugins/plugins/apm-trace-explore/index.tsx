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
import { Component, InjectReactive, Inject } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { IViewOptions } from '../../typings';
import TraceExplore from './trace-explore';
import type { TimeRangeType } from 'trace/components/time-range/utils';

import './index.scss';

@Component
export default class ApmTraceHome extends tsc<any, any> {
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange: [string, string];
  @InjectReactive('refreshInterval') readonly panelRefreshInterval: number;
  @InjectReactive('refreshImmediate') readonly panelRefreshImmediate: string;
  // 处理时间范围变化
  @Inject('handleTimeRangeChange') handleTimeRangeChange: (v: TimeRangeType) => void;

  get v3Props() {
    return {
      viewOptions: this.viewOptions,
      timeRange: this.timeRange,
      refreshInterval: this.panelRefreshInterval,
      refreshImmediate: this.panelRefreshImmediate,
    };
  }

  handleV3EventChange(eventName: string, params: any) {
    if (eventName === 'exploreChartZoomChange') {
      this.handleTimeRangeChange(params as TimeRangeType);
      return;
    }
  }

  render() {
    return (
      <div
        id='apm-trace-home-main'
        class='apm-trace-home-page'
      >
        <TraceExplore
          v3Props={this.v3Props}
          onV3Event={this.handleV3EventChange}
        />
      </div>
    );
  }
}
