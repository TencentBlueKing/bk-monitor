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

import { type AggFunction } from '../../typings';
import { type VariableModelType } from '../../variables';
import { QueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import './function-detail.scss';

interface FunctionProps {
  /* 函数 */
  value: AggFunction[];
  /* 变量列表 */
  variables?: VariableModelType[];
}

@Component
export default class FunctionDetail extends tsc<FunctionProps> {
  /* 函数 */
  @Prop({ type: Array }) value: AggFunction[];
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

  get functionsToVariableModel() {
    if (!this.value?.length) {
      return [];
    }
    const models = this.value.reduce((prev, curr) => {
      const result = this.variablesToolInstance.transformVariables(curr, this.variableMap);
      if (!Array.isArray(result.value)) {
        prev.push(result);
        return prev;
      }
      prev.push(...result.value.map(dimensionId => ({ ...result, value: dimensionId })));
      return prev;
    }, []);

    return models.filter(item => item.value?.id);
  }

  render() {
    return (
      <div class='template-function-detail-component'>
        <span class='function-label'>{this.$slots?.label || this.$t('函数')}</span>
        <span class='function-colon'>:</span>
        <span class='function-name-wrap'>
          {this.functionsToVariableModel.map(variableModel => {
            const domTag = variableModel.isVariable ? VariableSpan : 'span';
            const paramsStr = variableModel.value?.params?.map?.(param => param.value)?.toString?.();
            return (
              <domTag class='function-name'>{`${variableModel.value?.id}${paramsStr ? `(${paramsStr})` : ''}; `}</domTag>
            );
          })}
        </span>
      </div>
    );
  }
}
