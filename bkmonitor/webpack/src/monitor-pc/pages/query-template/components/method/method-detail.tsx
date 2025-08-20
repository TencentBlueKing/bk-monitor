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

import { getTemplateSrv } from '../../variables/template/template-srv';
import { type QueryVariablesTransformResult, QueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import type { VariableModelType } from '../../variables';

import './method-detail.scss';

interface MethodProps {
  /* 汇聚方法 */
  value: string;
  /* 变量 variableName-变量对象 映射表 */
  variableMap?: Record<string, VariableModelType>;
}

@Component
export default class MethodDetail extends tsc<MethodProps> {
  /* 汇聚方法 */
  @Prop({ type: String, default: '' }) value: string;
  /* 变量 variableName-变量对象 映射表 */
  @Prop({ default: () => [] }) variableMap?: Record<string, VariableModelType>;
  variablesToolInstance = new QueryVariablesTool();

  /** 将已选汇聚方法字符串 转换为渲染所需的 QueryVariablesTransformResult 结构数据 */
  get methodToVariableModel(): QueryVariablesTransformResult {
    return this.variablesToolInstance.transformVariables(this.value);
  }

  render() {
    return (
      <div class='template-method-detail-component'>
        <span class='method-label'>{this.$slots?.label || this.$t('汇聚方法')}</span>
        <span class='method-colon'>:</span>
        {this.methodToVariableModel.isVariable ? (
          <VariableSpan
            id={this.methodToVariableModel.variableName}
            class='method-name'
          >
            {getTemplateSrv().replace(this.methodToVariableModel.value as string, this.variableMap) ||
              this.methodToVariableModel?.value}
          </VariableSpan>
        ) : (
          <span
            id={this.methodToVariableModel.variableName}
            class='method-name'
          >
            {this.methodToVariableModel?.value || '--'}
          </span>
        )}
      </div>
    );
  }
}
