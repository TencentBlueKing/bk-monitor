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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import DimensionCreator from '../dimension/dimension-creator';
import FunctionCreator from '../function/function-creator';
import IntervalCreator from '../interval/interval-creator';
import MethodCreator from '../method/method-creator';
import MetricCreator from '../metric/metric-creator';
import {
  type IDimensionOptionsItem,
  type IVariablesItem,
  type TMetricDetail,
  TVariableType,
} from '../type/query-config';

import './query-config-creator.scss';

interface IProps {
  queryConfig?: IQueryConfig;
  variables?: IVariablesItem[];
  onCreateVariable?: (val: IVariablesItem) => void;
}
interface IQueryConfig {
  alias?: string;
  metric_id: string;
}

@Component
export default class QueryConfigCreator extends tsc<IProps> {
  @Prop({ default: null }) queryConfig: IQueryConfig;
  @Prop({ default: () => [] }) variables: IVariablesItem[];

  /* 当前指标 */
  curMetric: TMetricDetail = null;
  /* 汇聚周期 */
  method = 'avg';

  get getMethodVariables() {
    return this.variables.filter(item => item.type === TVariableType.METHOD);
  }
  get getDimensionVariables() {
    return this.variables.filter(item => item.type === TVariableType.DIMENSION);
  }
  get getAggMethodList() {
    return this.curMetric?.aggMethodList || [];
  }
  get getDimensionList() {
    return this.curMetric?.dimensions || [];
  }

  handleSelectMetric(metric: TMetricDetail) {
    this.curMetric = metric;
  }
  handleCreateMethodVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: TVariableType.METHOD,
    });
  }
  handleCreateDimensionVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: TVariableType.DIMENSION,
    });
  }

  render() {
    return (
      <div class='template-query-config-creator-component'>
        <div class='alias-wrap'>
          <span>{this.queryConfig?.alias || 'a'}</span>
        </div>
        <div class='query-config-wrap'>
          <MetricCreator
            metricId={this.queryConfig?.metric_id}
            onSelectMetric={this.handleSelectMetric}
          />
          {!!this.curMetric && [
            <MethodCreator
              key={'method'}
              options={this.getAggMethodList}
              showVariables={true}
              variables={this.getMethodVariables}
              onCreateVariable={this.handleCreateMethodVariable}
            />,
            <IntervalCreator key={'interval'} />,
            <DimensionCreator
              key={'dimension'}
              options={this.getDimensionList as IDimensionOptionsItem[]}
              showVariables={true}
              variables={this.getDimensionVariables}
              onCreateVariable={this.handleCreateDimensionVariable}
            />,
            <FunctionCreator key={'function'} />,
          ]}
        </div>
      </div>
    );
  }
}
