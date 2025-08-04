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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  type IDetectionTypeItem,
  type IDetectionTypeRuleData,
  type MetricDetail,
  DetectionRuleTypeEnum,
} from '../../../typings';
import AbnormalCluster from '../abnormal-cluster/abnormal-cluster';
import IntelligentDetect, { type ChartType } from '../intelligent-detect/intelligent-detect';
import PartialNodes from '../partial-nodes/partial-nodes';
import RingRatio from '../ring-ratio/ring-ratio';
import Threshold from '../threshold/threshold';
import TimeSeriesForecast, { type IModelData } from '../time-series-forecast/time-series-forecast';
import YearRound from '../year-round/year-round';

import './rule-wrapper.scss';

interface RuleWrapperEvent {
  onChartTypeChange: ChartType;
  onDataChange: IDetectionTypeRuleData;
  onDelete: void;
  onInitVM: RuleWrapper;
  onModelChange: IModelData;
}

interface RuleWrapperProps {
  data?: IDetectionTypeRuleData;
  index: number;
  isEdit?: boolean;
  isRealtime?: boolean;
  metricData?: MetricDetail[];
  readonly?: boolean;
  resultTableId?: string;
  rule: IDetectionTypeItem;
  selectRuleData?: IDetectionTypeRuleData[];
  unit?: string;
}

@Component({})
export default class RuleWrapper extends tsc<RuleWrapperProps, RuleWrapperEvent> {
  /** 算法类型 */
  @Prop({ type: Object, required: true }) rule: IDetectionTypeItem;
  /** 已选择的算法数据 */
  @Prop({ type: Array, default: () => [] }) selectRuleData: IDetectionTypeRuleData[];
  /** 当前算法数据 */
  @Prop({ type: Object }) data: IDetectionTypeRuleData;
  /** 当前算法索引 */
  @Prop({ type: Number, required: true }) index: number;
  /** 是否只读 */
  @Prop({ type: Boolean, default: false }) readonly: boolean;
  /** 是否编辑 */
  @Prop({ type: Boolean, default: false }) isEdit: boolean;
  /** 是否是实时选项 */
  @Prop({ type: Boolean, default: false }) isRealtime: boolean;
  /** 指标数据 */
  @Prop({ type: Array, default: () => [] }) metricData: MetricDetail[];
  /** 是否是实时选项 */
  @Prop({ type: String, default: '' }) unit: string;
  /** 结果表id */
  @Prop({ type: String, default: '' }) resultTableId: string;

  @Ref() ruleRef: any;

  validError = false;

  @Emit('delete')
  handleDel() {}

  @Emit('dataChange')
  handleDataChange(val: IDetectionTypeRuleData) {
    return val;
  }

  @Emit('modelChange')
  handleModelChange(val: IModelData) {
    return val;
  }
  @Emit('chartTypeChange')
  handleChartTypeChange(val: ChartType) {
    return val;
  }
  /** 其他已选择算法的数据 */
  get otherSelectRuleData() {
    return this.selectRuleData.filter((item, index) => index !== this.index);
  }

  /** 指标的汇聚周期 */
  get interval() {
    return this.metricData[0]?.agg_interval;
  }

  mounted() {
    this.initVm();
  }

  /**
   * 因为jsx中，map循环渲染组件，无法通过ref拿到所有的组件，所以需要向外提供组件实例供调用
   * @returns 当前组件实例
   */
  @Emit('initVM')
  initVm() {
    return this;
  }

  validate() {
    return new Promise((res, rej) => {
      if (!this.ruleRef.validate) {
        res(true);
      } else {
        this.ruleRef
          .validate()
          .then(validator => {
            this.validError = false;
            res(validator);
          })
          .catch(validator => {
            this.validError = true;
            rej(validator);
          });
      }
    });
  }

  clearError() {
    this.ruleRef.clearError?.();
  }

  renderContent() {
    switch (this.rule.id) {
      case DetectionRuleTypeEnum.IntelligentDetect:
        return (
          <IntelligentDetect
            ref='ruleRef'
            data={this.data}
            interval={this.interval}
            isEdit={this.isEdit}
            readonly={this.readonly}
            resultTableId={this.resultTableId}
            onChartTypeChange={this.handleChartTypeChange}
            onDataChange={this.handleDataChange}
            onModelChange={this.handleModelChange}
          />
        );
      case DetectionRuleTypeEnum.AbnormalCluster:
        return (
          <AbnormalCluster
            ref='ruleRef'
            data={this.data}
            interval={this.interval}
            isEdit={this.isEdit}
            metricData={this.metricData}
            readonly={this.readonly}
            onDataChange={this.handleDataChange}
            onModelChange={this.handleModelChange}
          />
        );
      case DetectionRuleTypeEnum.TimeSeriesForecasting:
        return (
          <TimeSeriesForecast
            ref='ruleRef'
            data={this.data}
            interval={this.interval}
            isEdit={this.isEdit}
            readonly={this.readonly}
            unit={this.unit}
            onDataChange={this.handleDataChange}
            onModelChange={this.handleModelChange}
          />
        );
      case DetectionRuleTypeEnum.Threshold:
        return (
          <Threshold
            ref='ruleRef'
            data={this.data}
            otherSelectRuleData={this.otherSelectRuleData}
            readonly={this.readonly}
            unit={this.unit}
            onDataChange={this.handleDataChange}
          />
        );
      case DetectionRuleTypeEnum.RingRatio:
        return (
          <RingRatio
            ref='ruleRef'
            data={this.data}
            is-realtime={this.isRealtime}
            otherSelectRuleData={this.otherSelectRuleData}
            readonly={this.readonly}
            onDataChange={this.handleDataChange}
          />
        );
      case DetectionRuleTypeEnum.YearRound:
        return (
          <YearRound
            ref='ruleRef'
            data={this.data}
            is-realtime={this.isRealtime}
            otherSelectRuleData={this.otherSelectRuleData}
            readonly={this.readonly}
            onDataChange={this.handleDataChange}
          />
        );
      case DetectionRuleTypeEnum.PartialNodes:
        return (
          <PartialNodes
            ref='ruleRef'
            data={this.data}
            is-realtime={this.isRealtime}
            otherSelectRuleData={this.otherSelectRuleData}
            readonly={this.readonly}
            onDataChange={this.handleDataChange}
          />
        );
    }
  }

  render() {
    return (
      <div class={{ 'rule-wrapper': true, 'valid-error': this.validError }}>
        <div class='header'>
          <div class='title-wrap'>
            <img
              class='type-icon'
              alt=''
              src={this.rule.icon}
            />
            <span class='title'>{this.rule.name}</span>
            {/* <p class='explain'>({this.rule.tip})</p> */}
          </div>
          {!this.readonly && (
            <span
              class='icon-monitor icon-mc-delete-line del-btn'
              onClick={this.handleDel}
            />
          )}
        </div>
        <div class='content'>{this.renderContent()}</div>
      </div>
    );
  }
}
