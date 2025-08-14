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

import { type VariableModelType } from '../../variables';
import { QueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import './expression-detail.scss';

interface ExpressionProps {
  /* 表达式 */
  expression: string;
  /* 变量列表 */
  variables?: VariableModelType[];
}

@Component
export default class ExpressionDetail extends tsc<ExpressionProps> {
  /* 表达式 */
  @Prop({ type: String, default: '' }) expression: string;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables?: VariableModelType[];
  variablesToolInstance = new QueryVariablesTool();

  get variableMap() {
    if (!this.variables?.length) {
      return {};
    }
    return this.variables?.reduce?.((prev, curr) => {
      prev[curr.name] = curr.value;
      return prev;
    }, {});
  }

  get expressionToVariableModel() {
    const regex = /(\${(?:\w+)})|([^{$]+|\${(?!\w+\}))/g;
    const strArr = [];
    let match;
    while ((match = regex.exec(this.expression)) !== null) {
      const [_full, variable, str] = match;
      if (variable) {
        strArr.push(variable);
      } else if (match[2]) {
        strArr.push(str);
      }
    }
    const models = strArr.map(str => this.variablesToolInstance.transformVariables(str, this.variableMap));
    return models;
  }

  render() {
    return (
      <div class='template-expression-detail-component'>
        <span class='expression-label'>{`${this.$t('表达式')}`}</span>
        <span class='expression-colon'>:</span>
        <span class='expression-name-wrap'>
          {this.expressionToVariableModel.map(variableModel => {
            const domTag = variableModel.isVariable ? VariableSpan : 'span';
            return <domTag class='expression-name'>{variableModel.value}</domTag>;
          })}
        </span>
      </div>
    );
  }
}
