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

import { VariableTypeEnum } from '../../constants';
import ConditionCreator from '../condition/condition-creator';
import DimensionCreator from '../dimension/dimension-creator';
import FunctionCreator from '../function/function-creator';
import IntervalCreator from '../interval/interval-creator';
import MethodCreator from '../method/method-creator';
import MetricCreator from '../metric/metric-creator';

import type { AggCondition, AggFunction, MetricDetailV2, QueryConfig } from '../../typings';
import type { IGetMetricListData, IGetMetricListParams } from '../metric/components/types';
import type {
  IConditionOptionsItem,
  IDimensionOptionsItem,
  IFunctionOptionsItem,
  IVariablesItem,
} from '../type/query-config';

import './query-config-creator.scss';

interface IProps {
  hasVariableOperate?: boolean;
  metricFunctions?: IFunctionOptionsItem[];
  queryConfig?: QueryConfig;
  variables?: IVariablesItem[];
  getMetricList: (params: IGetMetricListParams) => Promise<IGetMetricListData>;
  onChangeCondition?: (val: AggCondition[]) => void;
  onChangeDimension?: (val: string[]) => void;
  onChangeFunction?: (val: AggFunction[]) => void;
  onChangeInterval?: (val: number | string) => void;
  onChangeMethod?: (val: string) => void;
  onCreateVariable?: (val: IVariablesItem) => void;
  onSelectMetric?: (metric: MetricDetailV2) => void;
}

@Component
export default class QueryConfigCreator extends tsc<IProps> {
  @Prop({ default: () => [] }) variables: IVariablesItem[];
  @Prop({ default: () => [] }) metricFunctions: IFunctionOptionsItem[];
  @Prop({ default: () => null }) queryConfig: QueryConfig;
  @Prop({ required: true, type: Function }) getMetricList: (
    params: IGetMetricListParams
  ) => Promise<IGetMetricListData>;
  @Prop({ default: false }) hasVariableOperate: boolean;
  get getMethodVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.METHOD);
  }
  get getDimensionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.GROUP_BY);
  }
  get getFunctionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.FUNCTIONS);
  }
  get getConditionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.CONDITIONS);
  }
  get getDimensionValueVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.TAG_VALUES);
  }
  get allVariables() {
    return this.variables.map(item => ({ name: item.name }));
  }
  get getAggMethodList() {
    return this.queryConfig.metricDetail?.methodList || [];
  }
  get getDimensionList() {
    return this.queryConfig.metricDetail?.dimensionList || [];
  }
  get getWhereDimensionList() {
    return this.queryConfig.metricDetail.whereDimensionList || [];
  }

  handleSelectMetric(metric) {
    this.$emit('selectMetric', metric);
  }
  handleCreateMethodVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: VariableTypeEnum.METHOD,
      metric: this.queryConfig.metricDetail,
    });
  }
  handleCreateDimensionVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: VariableTypeEnum.GROUP_BY,
      metric: this.queryConfig.metricDetail,
    });
  }
  handleCreateFunctionVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: VariableTypeEnum.FUNCTIONS,
      metric: this.queryConfig.metricDetail,
    });
  }
  handleCreateConditionVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: VariableTypeEnum.CONDITIONS,
      metric: this.queryConfig.metricDetail,
    });
  }
  handleCreateDimensionValueVariable(val) {
    this.$emit('createVariable', {
      name: val.name,
      type: VariableTypeEnum.TAG_VALUES,
      metric: this.queryConfig.metricDetail,
      related_tag: val.related_tag,
    });
  }

  handleChangeMethod(val: string) {
    this.$emit('changeMethod', val);
  }
  handleDimensionChange(val: string[]) {
    this.$emit('changeDimension', val);
  }
  handleChangeFunction(val: AggFunction[]) {
    this.$emit('changeFunction', val);
  }
  handleChangeInterval(val: number | string) {
    this.$emit('changeInterval', val);
  }
  handleConditionChange(val: AggCondition[]) {
    this.$emit('changeCondition', val);
  }

  render() {
    return (
      <div class='template-query-config-creator-component'>
        <div class='alias-wrap'>
          <span>{this.queryConfig.alias || 'a'}</span>
        </div>
        <div class='query-config-wrap'>
          {[
            <div
              key={'row1'}
              class='query-config-row'
            >
              <MetricCreator
                getMetricList={this.getMetricList}
                metricDetail={this.queryConfig.metricDetail}
                onSelectMetric={this.handleSelectMetric}
              />
              {!!this.queryConfig.metricDetail && [
                <MethodCreator
                  key={'method'}
                  allVariables={this.allVariables}
                  options={this.getAggMethodList}
                  showVariables={this.hasVariableOperate}
                  value={this.queryConfig.agg_method}
                  variables={this.getMethodVariables}
                  onChange={this.handleChangeMethod}
                  onCreateVariable={this.handleCreateMethodVariable}
                />,
                <IntervalCreator
                  key={'interval'}
                  value={this.queryConfig.agg_interval}
                  onChange={this.handleChangeInterval}
                />,
              ]}
            </div>,
            !!this.queryConfig.metricDetail && (
              <div
                key={'row2'}
                class='query-config-row'
              >
                <DimensionCreator
                  key={'dimension'}
                  allVariables={this.allVariables}
                  options={this.getDimensionList as IDimensionOptionsItem[]}
                  showVariables={true}
                  value={this.queryConfig.agg_dimension}
                  variables={this.getDimensionVariables}
                  onChange={this.handleDimensionChange}
                  onCreateVariable={this.handleCreateDimensionVariable}
                />
                <FunctionCreator
                  key={'function'}
                  allVariables={this.allVariables}
                  options={this.metricFunctions}
                  showVariables={true}
                  value={this.queryConfig.functions}
                  variables={this.getFunctionVariables}
                  onChange={this.handleChangeFunction}
                  onCreateVariable={this.handleCreateFunctionVariable}
                />
              </div>
            ),
            !!this.queryConfig.metricDetail && (
              <div
                key={'row3'}
                class='query-config-row'
              >
                <ConditionCreator
                  allVariables={this.allVariables}
                  dimensionValueVariables={this.getDimensionValueVariables as { name: string }[]}
                  hasVariableOperate={true}
                  metricDetail={this.queryConfig.metricDetail}
                  options={this.getWhereDimensionList as IConditionOptionsItem[]}
                  value={this.queryConfig.agg_condition}
                  variables={this.getConditionVariables}
                  onChange={this.handleConditionChange}
                  onCreateValueVariable={this.handleCreateDimensionValueVariable}
                  onCreateVariable={this.handleCreateConditionVariable}
                />
              </div>
            ),
          ]}
        </div>
      </div>
    );
  }
}
