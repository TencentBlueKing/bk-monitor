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
import { Component, Emit, Prop, PropSync, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IScenarioItem, type MetricDetail, type strategyType, MetricType } from '../typings/index';
import StrategyMetricAlert from './strategy-metric-alert';
import StrategyMetricCommon from './strategy-metric-common-new';
import StrategyMetricWrap, { type TMode } from './strategy-metric-wrap';

interface IStrategyMetricSelectorProps {
  isEdit: boolean;
  maxLength?: number;
  metricData: MetricDetail[];
  monitorType?: string;
  multiple: boolean;
  readonly?: boolean;
  scenarioList: IScenarioItem[];
  show: boolean;
  strategyType?: strategyType;
  type: string;
}

@Component({
  name: 'StrategyMetricSelector',
})
export default class StrategyMetricSelector extends tsc<IStrategyMetricSelectorProps> {
  @Prop({ default: MetricType.TimeSeries, type: String }) readonly type: MetricType; // 监控指标 | 事件 | 日志
  @Prop({ default: false, type: Boolean }) readonly show: boolean;
  @Prop({ default: false, type: Boolean }) readonly isEdit: boolean;
  @Prop({ default: null, type: Number }) readonly id: number;
  @PropSync('monitorType', { type: String }) monitorTypeSync!: string;
  @Prop({ default: () => [], type: Array }) readonly scenarioList: IScenarioItem[]; // 理监控对象数据
  @Prop({ default: 10, type: Number }) readonly maxLength: number; // 多指标最大个数 默认10

  // 监控指标 && 事件
  @Prop({ default: null, type: Object }) readonly metric: any; // 编辑的指标

  // 监控指标
  @Prop({ default: false, type: Boolean }) multiple: boolean; // 指标多选
  @Prop({ default: () => [], type: Array }) metricData: MetricDetail[];

  @Prop({ default: false, type: Boolean }) readonly: boolean; // 是否只读
  @Prop({ default: 'monito', type: String }) strategyType: strategyType;

  private isShow = false;

  @Watch('show')
  showChange(v) {
    !v && (this.isShow = v);
    v &&
      this.$nextTick(() => {
        this.isShow = v;
      });
  }

  @Emit('change')
  emitMetricValue(metric: any) {
    return metric;
  }

  @Emit('on-hide')
  emitShowChange(isShow: boolean) {
    this.isShow = isShow;
    return false;
  }
  @Emit('scenario')
  emitScenarioType(v) {
    return v;
  }

  render() {
    return (
      <div>
        <StrategyMetricCommon
          isShow={this.isShow && this.type === MetricType.TimeSeries}
          maxLength={this.maxLength}
          metricData={this.metricData}
          monitorType={this.monitorTypeSync}
          multiple={this.multiple}
          readonly={this.readonly}
          scenarioList={this.scenarioList}
          on-add={this.emitMetricValue}
          on-hide-dialog={this.emitShowChange}
          on-scenariotype={this.emitScenarioType}
          on-show-change={this.emitShowChange}
        />
        {['event', 'log'].includes(this.type) && (
          <StrategyMetricWrap
            checkedMetric={this.metricData}
            isEdit={this.isEdit}
            isShow={this.isShow}
            mode={this.type as TMode}
            monitorType={this.monitorTypeSync}
            readonly={this.readonly}
            scenarioList={this.scenarioList}
            strategyType={this.strategyType}
            onLeftSelect={this.emitScenarioType}
            onSelected={v => this.emitMetricValue(v[0])}
            onShowChange={this.emitShowChange}
          />
        )}
        {this.type === 'alert' && (
          <StrategyMetricAlert
            isShow={this.isShow && this.type === 'alert'}
            metricData={this.metricData}
            monitorType={this.monitorTypeSync}
            scenarioList={this.scenarioList}
            onScenarioChange={this.emitScenarioType}
            onSelected={this.emitMetricValue}
            onShowChange={this.emitShowChange}
          />
        )}
      </div>
    );
  }
}
