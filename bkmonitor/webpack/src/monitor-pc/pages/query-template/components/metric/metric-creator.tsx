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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import SelectWrap from '../utils/select-wrap';
import MetricSelector from './components/metric-selector';

import type { MetricDetailV2 } from '../../typings/metric';
import type { IGetMetricListData, IGetMetricListParams } from './components/types';

import './metric-creator.scss';

interface IProps {
  metricDetail?: MetricDetailV2;
  getMetricList: (params: IGetMetricListParams) => Promise<IGetMetricListData>;
  onSelectMetric?: (metric: MetricDetailV2) => void;
}

@Component
export default class MetricCreator extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) metricDetail: MetricDetailV2;
  @Prop({ type: Function, required: true }) getMetricList: (
    params: IGetMetricListParams
  ) => Promise<IGetMetricListData>;

  loading = false;

  abortController: AbortController | null = null;

  handleSelectMetric(metric: MetricDetailV2[]) {
    this.$emit('selectMetric', metric[0]);
  }

  render() {
    return (
      <div class='template-metric-creator-component'>
        <div class='metric-label'>{this.$t('指标')}</div>
        <MetricSelector
          getMetricList={this.getMetricList}
          selectedMetric={this.metricDetail}
          triggerLoading={this.loading}
          onConfirm={this.handleSelectMetric}
        />
        {/* <SelectWrap
          id={this.selectId}
          backgroundColor={'#FDF4E8'}
          expanded={this.showSelect}
          loading={this.loading}
          minWidth={432}
          tips={this.metricTips}
          tipsPlacements={['right']}
          onClick={() => this.handleClick()}
        >
          {this.metricDetail ? (
            <span class='metric-name'>{this.metricDetail?.metricAlias || this.metricDetail?.name}</span>
          ) : (
            <span class='metric-placeholder'>{this.$t('点击添加指标')}</span>
          )}
        </SelectWrap>
        <MetricSelector
          key={this.selectId}
          metricId={this.metricDetail?.metric_id as string}
          show={this.showSelect}
          targetId={`#${this.selectId}`}
          onSelected={this.handleSelectMetric}
          onShowChange={val => {
            this.showSelect = val;
          }}
        /> */}
      </div>
    );
  }
}
