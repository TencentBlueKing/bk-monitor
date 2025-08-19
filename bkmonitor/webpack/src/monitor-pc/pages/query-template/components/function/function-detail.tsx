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

import type { AggFunction } from '../../typings';
import type { VariableModelType } from '../../variables';

import './function-detail.scss';

interface FunctionProps {
  /* 已选函数数组 */
  value: AggFunction[];
  /* 变量列表 */
  variables?: VariableModelType[];
}

@Component
export default class FunctionDetail extends tsc<FunctionProps> {
  /* 已选函数数组 */
  @Prop({ type: Array }) value: AggFunction[];
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

  /** 将已选函数数组 源数据数组 转换为渲染所需的 QueryVariablesTransformResult 结构数组 */
  get functionsToVariableModel(): QueryVariablesTransformResult[] {
    if (!this.value?.length) {
      return [];
    }
    const models = this.value.reduce((prev, curr) => {
      const result = this.variablesToolInstance.transformVariables(curr.id);
      if (!result.value) {
        return prev;
      }
      result.value = curr;
      prev.push(result);
      return prev;
    }, []);

    return models;
  }

  functionNameRenderer(item) {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const DomTag = item.isVariable ? VariableSpan : 'span';
    const paramsStr = item.value?.params?.map?.(param => param.value)?.toString?.();
    return <DomTag class='function-name'>{`${item.value?.id}${paramsStr ? `(${paramsStr})` : ''}; `}</DomTag>;
  }

  createFunctionNameVariableChunk(variableName, content) {
    return (
      <span
        id={variableName}
        class='function-name-variable-chunk'
      >
        {content}
      </span>
    );
  }

  functionNameWrapRenderer() {
    let content: HTMLElement[] | string = '--';
    if (this.functionsToVariableModel?.length) {
      content = this.functionsToVariableModel.reduce((prev, curr) => {
        if (!curr.isVariable) {
          prev.push(this.functionNameRenderer(curr));
          return prev;
        }
        let varValue = '';
        const result = this.templateSrv.replace(`\${${curr.variableName}:json}` as string, this.variableMap);
        try {
          varValue = JSON.parse(result);
        } catch {
          varValue = '';
        }

        if (Array.isArray(varValue)) {
          prev.push(
            this.createFunctionNameVariableChunk(
              curr.variableName,
              varValue.map(v =>
                this.functionNameRenderer({ value: v, variableName: curr.variableName, isVariable: curr.isVariable })
              )
            )
          );
          return prev;
        }
        prev.push(
          this.createFunctionNameVariableChunk(
            curr.variableName,
            this.functionNameRenderer({
              value: varValue || curr.value,
              variableName: curr.variableName,
              isVariable: curr.isVariable,
            })
          )
        );
        return prev;
      }, []);
    }

    return <div class='function-name-wrap'>{content}</div>;
  }

  render() {
    return (
      <div class='template-function-detail-component'>
        <span class='function-label'>{this.$slots?.label || this.$t('函数')}</span>
        <span class='function-colon'>:</span>
        {this.functionNameWrapRenderer()}
      </div>
    );
  }
}
