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
import { getTemplateSrv } from '../../variables/template/template-srv';
import { type QueryVariablesTransformResult, QueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import './method-detail.scss';

interface MethodProps {
  /* 汇聚方法 */
  value: string;
  /* 变量列表 */
  variables?: VariableModelType[];
}

@Component
export default class MethodDetail extends tsc<MethodProps> {
  /* 汇聚方法 */
  @Prop({ type: String, default: '' }) value: string;
  /* 变量列表 */
  @Prop({ default: () => [] }) variables?: VariableModelType[];
  variablesToolInstance = new QueryVariablesTool();
  templateSrv = getTemplateSrv();

  get variableMap() {
    if (!this.variables?.length) {
      return {};
    }
    return this.variables?.reduce?.((prev, curr) => {
      prev[curr.name] = curr;
      return prev;
    }, {});
  }

  /** 将已选汇聚方法字符串 转换为渲染所需的 QueryVariablesTransformResult 结构数据 */
  get methodToVariableModel(): QueryVariablesTransformResult {
    return this.variablesToolInstance.transformVariables(this.value);
  }

  get methodViewDom() {
    return this.methodToVariableModel.isVariable ? VariableSpan : 'span';
  }

  get methodValue() {
    if (!this.methodToVariableModel.isVariable) {
      return this.methodToVariableModel?.value || '--';
    }

    return (
      this.templateSrv.replace(this.methodToVariableModel.value as string, this.variableMap) ||
      this.methodToVariableModel?.value
    );
  }

  render() {
    return (
      <div class='template-method-detail-component'>
        <span class='method-label'>{this.$slots?.label || this.$t('汇聚方法')}</span>
        <span class='method-colon'>:</span>
        <this.methodViewDom
          id={this.methodToVariableModel.variableName}
          class='method-name'
        >
          {this.methodValue}
        </this.methodViewDom>
      </div>
    );
  }
}
