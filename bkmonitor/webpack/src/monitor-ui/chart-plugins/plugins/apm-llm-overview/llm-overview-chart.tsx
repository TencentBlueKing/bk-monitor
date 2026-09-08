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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { Debounce } from 'monitor-common/utils/utils';

import BaseEchart from '../monitor-base-echart';

import type { MonitorEchartOptions } from '../../typings';

interface ILlmOverviewChartProps {
  options: MonitorEchartOptions;
}

@Component
export default class LlmOverviewChart extends tsc<ILlmOverviewChartProps> {
  @Prop({ required: true, type: Object }) options: MonitorEchartOptions;
  @Ref('chart') chartRef: HTMLDivElement;

  height = 100;
  width = 300;

  mounted() {
    addListener(this.$el as HTMLDivElement, this.handleResize);
    this.handleResize();
  }

  beforeDestroy() {
    removeListener(this.$el as HTMLDivElement, this.handleResize);
  }

  @Debounce(100)
  handleResize() {
    if (!this.chartRef) return;
    const { height = 0, width = 0 } = this.chartRef.getBoundingClientRect();
    if (height > 32 && width >= 0) {
      this.height = height;
      this.width = width;
    }
  }

  render() {
    return (
      <div class='llm-overview-chart'>
        <div
          ref='chart'
          class='llm-overview-chart-instance'
        >
          {this.height > 32 && (
            <BaseEchart
              height={this.height}
              options={this.options}
              width={this.width}
            />
          )}
        </div>
      </div>
    );
  }
}
