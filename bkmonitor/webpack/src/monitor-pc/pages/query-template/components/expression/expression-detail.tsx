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

import { getTemplateSrv } from '../../variables/template/template-srv';
import { getQueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import type { VariableModelType } from '../../variables';

import './expression-detail.scss';

interface ExpressionProps {
  /* 表达式 */
  expression: string;
  /* 变量 variableName-变量对象 映射表 */
  variableMap?: Record<string, VariableModelType>;
}

@Component
export default class ExpressionDetail extends tsc<ExpressionProps> {
  /* 表达式 */
  @Prop({ type: String, default: '' }) expression: string;
  /* 变量 variableName-变量对象 映射表 */
  @Prop({ default: () => [] }) variableMap?: Record<string, VariableModelType>;

  get expressionToVariableModel() {
    const regex = /(\${(?:[\w\u4e00-\u9fa5]+)})|([^{$]+|\${(?![\w\u4e00-\u9fa5]+\}))/g;
    const strArr = [];
    let match: null | RegExpExecArray;
    while (true) {
      match = regex.exec(this.expression);
      if (match === null) break;
      const [_full, variable, str] = match;
      if (variable) {
        strArr.push(variable);
      } else if (match[2]) {
        strArr.push(str);
      }
    }
    return strArr.map(str => getQueryVariablesTool().transformVariables(str));
  }

  expressionNameWrapRenderer() {
    const content = this.expressionToVariableModel?.map?.((variableModel, index) => {
      // eslint-disable-next-line @typescript-eslint/naming-convention
      const DomTag = variableModel.isVariable ? VariableSpan : 'span';
      const result = getTemplateSrv().replace(variableModel.value as string, this.variableMap);
      return (
        <DomTag
          id={variableModel.variableName}
          key={index}
          class='expression-name'
        >
          {result || getQueryVariablesTool().getVariableAlias(variableModel.value as string, this.variableMap)}
        </DomTag>
      );
    });

    return <span class='expression-name-wrap'>{content?.length ? content : '--'}</span>;
  }

  render() {
    return (
      <div class='template-expression-detail-component'>
        <span class='expression-label'>{this.$slots?.label || this.$t('表达式')}</span>
        <span class='expression-colon'>:</span>
        {this.expressionNameWrapRenderer()}
      </div>
    );
  }
}
