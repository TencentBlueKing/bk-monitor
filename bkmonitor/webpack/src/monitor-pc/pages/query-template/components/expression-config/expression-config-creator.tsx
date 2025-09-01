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
import ExpressionCreator from '../expression/expression-creator';
import FunctionCreator from '../function/function-creator';

import type { Expression } from '../../typings/expression';
import type { AggFunction } from '../../typings/query-config';
import type { IFunctionOptionsItem, IVariablesItem } from '../type/query-config';

import './expression-config-creator.scss';

interface IProps {
  expressionConfig?: Expression;
  metricFunctions?: IFunctionOptionsItem[];
  variables?: IVariablesItem[];
  onChangeExpression?: (val: string) => void;
  onChangeFunction?: (val: AggFunction[]) => void;
  onCreateVariable?: (val: IVariablesItem) => void;
}

@Component
export default class ExpressionConfigCreator extends tsc<IProps> {
  @Prop({ default: () => null }) expressionConfig: Expression;
  @Prop({ default: () => [] }) metricFunctions: IFunctionOptionsItem[];
  @Prop({ default: () => [] }) variables: IVariablesItem[];

  get getFunctionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.FUNCTIONS);
  }

  get getExpressionVariables() {
    return this.variables.filter(item => item.type === VariableTypeEnum.CONSTANTS);
  }

  handleCreateFunctionVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: VariableTypeEnum.FUNCTIONS,
      metric: null,
    });
  }

  handleCreateExpressionVariable(val) {
    this.$emit('createVariable', {
      name: val,
      type: VariableTypeEnum.CONSTANTS,
      metric: null,
    });
  }

  handleExpressionChange(val) {
    this.$emit('changeExpression', val);
  }
  handleFunctionChange(val) {
    this.$emit('changeFunction', val);
  }

  render() {
    return (
      <div class='template-expression-config-creator-component'>
        <div class='alias-wrap'>
          <span class='icon-monitor icon-arrow-turn' />
        </div>
        <div class='expression-config-wrap'>
          <ExpressionCreator
            value={this.expressionConfig?.expression || ''}
            variables={this.getExpressionVariables}
            onChange={this.handleExpressionChange}
            onCreateVariable={this.handleCreateExpressionVariable}
          />
          <FunctionCreator
            options={this.metricFunctions}
            showVariables={true}
            value={this.expressionConfig?.functions || []}
            variables={this.getFunctionVariables}
            onChange={this.handleFunctionChange}
            onCreateVariable={this.handleCreateFunctionVariable}
          />
        </div>
      </div>
    );
  }
}
