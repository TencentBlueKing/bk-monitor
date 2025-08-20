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

import { VariableTypeEnum } from '../../constants';
import { type QueryConfig } from '../../typings';
import ConditionDetail from '../condition/condition-detail';
import DimensionDetail from '../dimension/dimension-detail';
import FunctionDetail from '../function/function-detail';
import IntervalDetail from '../interval/interval-detail';
import MethodDetail from '../method/method-detail';
import MetricDetail from '../metric/metric-detail';

import type { VariableModelType } from '../../variables';

import './query-config-detail.scss';

interface IProps {
  queryConfig?: QueryConfig;
  variables?: VariableModelType[];
}

@Component
export default class QueryConfigDetail extends tsc<IProps> {
  @Prop({ default: () => null }) queryConfig: QueryConfig;
  @Prop({ default: () => [] }) variables: VariableModelType[];

  get getMethodVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.METHOD);
  }
  get getDimensionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.DIMENSION);
  }
  get getFunctionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.FUNCTION);
  }
  get getDimensionValueVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.DIMENSION_VALUE);
  }

  get getDimensionList() {
    return this.queryConfig.metricDetail?.dimensionList || [];
  }

  render() {
    return (
      <div class='template-query-config-detail-component'>
        <div class='alias-wrap'>
          <span>{this.queryConfig?.alias || 'a'}</span>
        </div>
        <div class='query-config-wrap'>
          <MetricDetail metricDetail={this.queryConfig.metricDetail} />
          <MethodDetail
            value={this.queryConfig?.agg_method}
            variables={this.getMethodVariables}
          />
          <IntervalDetail value={this.queryConfig?.agg_interval} />
          <DimensionDetail
            options={this.getDimensionList}
            value={this.queryConfig?.agg_dimension}
            variables={this.getDimensionVariables}
          />
          <ConditionDetail
            dimensionValueVariables={this.getDimensionValueVariables}
            options={this.getDimensionList}
            value={this.queryConfig.agg_condition}
            variables={this.variables}
          />
          <FunctionDetail
            value={this.queryConfig?.functions}
            variables={this.getFunctionVariables}
          />
        </div>
      </div>
    );
  }
}
