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

import ExpressionDetail from '../expression/expression-detail';
import FunctionDetail from '../function/function-detail';

import type { VariableModelType } from '../../variables';

import './expression-config-detail.scss';

interface IProps {
  expressionConfig?: any;
  variables?: VariableModelType[];
}

@Component
export default class ExpressionConfigDetail extends tsc<IProps> {
  @Prop({ default: () => null }) expressionConfig: any;
  @Prop({ default: () => [] }) variables: VariableModelType[];

  get variableMap(): Record<string, VariableModelType> {
    if (!this.variables?.length) {
      return {};
    }
    return this.variables?.reduce?.((prev, curr) => {
      prev[curr.variableName] = curr;
      return prev;
    }, {});
  }

  render() {
    return (
      <div class='template-expression-config-detail-component'>
        <div class='alias-wrap'>
          <span class='icon-monitor icon-arrow-turn' />
        </div>
        <div class='expression-config-wrap'>
          <ExpressionDetail
            expression={this.expressionConfig?.expression}
            variableMap={this.variableMap}
          />
          <FunctionDetail
            value={this.expressionConfig?.functions}
            variableMap={this.variableMap}
          />
        </div>
      </div>
    );
  }
}
