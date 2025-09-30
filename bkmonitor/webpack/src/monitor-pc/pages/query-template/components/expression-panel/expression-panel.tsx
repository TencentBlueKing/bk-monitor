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

import ExpressionConfigCreator from '../expression-config/expression-config-creator';

import type { AggFunction } from '../../typings';
import type { Expression, IVariableModel } from '../../typings';
import type { VariableModelType } from '../../variables';
import type { IFunctionOptionsItem } from '../type/query-config';

import './expression-panel.scss';

interface IProps {
  expressionConfig?: Expression;
  metricFunctions?: IFunctionOptionsItem[];
  variables?: VariableModelType[];
  onChangeExpression?: (val: string) => void;
  onChangeFunction?: (val: AggFunction[]) => void;
  onCreateVariable?: (val: IVariableModel) => void;
}
@Component
export default class ExpressionPanel extends tsc<IProps> {
  @Prop({ default: () => [] }) metricFunctions: IFunctionOptionsItem[];
  @Prop({ default: () => [] }) variables: VariableModelType[];
  @Prop({ default: () => null }) expressionConfig: Expression;

  handleCreateVariable(val: IVariableModel) {
    this.$emit('createVariable', val);
  }

  handleChangeFunction(val: AggFunction[]) {
    this.$emit('changeFunction', val);
  }
  handleChangeExpression(val: string) {
    this.$emit('changeExpression', val);
  }

  render() {
    return (
      <div class='template-expression-panel-component'>
        <div class='template-expression-panel'>
          <ExpressionConfigCreator
            expressionConfig={this.expressionConfig}
            metricFunctions={this.metricFunctions}
            variables={this.variables}
            onChangeExpression={this.handleChangeExpression}
            onChangeFunction={this.handleChangeFunction}
            onCreateVariable={this.handleCreateVariable}
          />
        </div>
        <div class='template-expression-panel-desc'>{this.$t('支持四则运算 + - * / % ^ ( ) ,如(A+B)/100')}</div>
      </div>
    );
  }
}
