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

import type { AggCondition, DimensionField } from '../../typings';
import type { VariableModelType } from '../../variables';

import './condition-detail.scss';

interface IProps {
  /* 所有聚合维度信息列表数组 */
  options?: DimensionField[];
  /* 已选过滤条件 */
  value: AggCondition[];
  /* 变量列表 */
  variables?: VariableModelType[];
}

@Component
export default class ConditionCreator extends tsc<IProps> {
  /* 变量列表 */
  @Prop({ default: () => [] }) variables: VariableModelType[];
  /* 已选过滤条件 */
  @Prop({ default: () => [] }) value: AggCondition[];
  /* 所有聚合维度信息列表数组 */
  @Prop({ default: () => [] }) options: DimensionField[];
  variablesToolInstance = new QueryVariablesTool();
  templateSrv = getTemplateSrv();

  get allDimensionMap() {
    if (!this.options?.length) {
      return {};
    }
    return this.options?.reduce?.((prev, curr) => {
      prev[curr.id] = curr;
      return prev;
    }, {});
  }

  get variableMap() {
    if (!this.variables?.length) {
      return {};
    }
    return this.variables?.reduce?.((prev, curr) => {
      prev[curr.name] = curr.value;
      return prev;
    }, {});
  }

  get conditionToVariableModel() {
    if (!this.value?.length) {
      return [];
    }
    return this.value.reduce((prev, curr) => {
      const conditionResult = this.variablesToolInstance.transformVariables(
        curr.key
      ) as QueryVariablesTransformResult<AggCondition>;
      if (!conditionResult.value) {
        return prev;
      }
      // 浅拷贝，避免后续转换结构影响上层源数据
      conditionResult.value = { ...curr, value: [...(curr.value || [])] };
      prev.push(conditionResult);
      // 非条件变量的数据则还需要判断是否存在维度值变量
      if (!conditionResult.isVariable) {
        conditionResult.value.value = conditionResult.value.value.reduce((prev, curr) => {
          const conditionValueResult = this.variablesToolInstance.transformVariables(curr);
          if (!conditionValueResult.value) {
            return prev;
          }
          prev.push(conditionValueResult);
          return prev;
        }, []);
      }
      return prev;
    }, []);
  }

  tagItemRenderer(item) {
    if (!this.conditionToVariableModel?.length) {
      return '--';
    }
    return '--';
    // return this.conditionToVariableModel?.map?.((item, index) => {
    //   const domTag = item.isVariable ? VariableSpan : 'span';
    //   return (
    //     <div
    //       class='tags-item'
    //       v-bk-tooltips={{
    //         content: item.value,
    //         placement: 'top',
    //         disabled: !item.value,
    //         delay: [300, 0],
    //       }}
    //     >
    //       <domTag
    //         id={item.variableName}
    //         key={index}
    //         class='tags-item-name'
    //       >
    //         {this.allDimensionMap?.[item.value]?.name || item.value}
    //       </domTag>
    //     </div>
    //   );
    // });
  }

  /**
   * @description 条件变量渲染逻辑
   */
  conditionVariableRenderer(item: QueryVariablesTransformResult<AggCondition>) {
    let varValue = '';
    const result = this.templateSrv.replace(`\${${item.variableName}:json}` as string, this.variableMap);
    try {
      varValue = JSON.parse(result);
    } catch {
      varValue = '';
    }
    if (Array.isArray(varValue)) {
      return varValue.map(v =>
        this.tagItemRenderer({ value: v, variableName: item.variableName, isVariable: item.isVariable })
      );
    }
    return [
      this.tagItemRenderer({
        value: varValue || item.value,
        variableName: item.variableName,
        isVariable: item.isVariable,
      }),
    ];
  }

  /**
   * @description 非条件变量渲染逻辑
   */
  conditionRenderer(condition: Omit<AggCondition, 'value'> & { value: QueryVariablesTransformResult<AggCondition>[] }) {
    return '--';
  }

  tagWrapRenderer() {
    const content = this.conditionToVariableModel?.reduce?.((prev, curr) => {
      // 条件变量执行支线
      if (curr.isVariable) {
        prev.push(...this.conditionVariableRenderer(curr));
        return prev;
      }
      console.log('================ curr.value ================', curr.value);
      // 非条件变量则判断知否存在维度值变量
      prev.push(this.conditionRenderer(curr.value));

      return prev;
    }, []);
    return <div class='tags-wrap'>{content?.length ? content : '--'}</div>;
  }

  render() {
    return (
      <div class='template-condition-detail-component'>
        <span class='condition-label'>{this.$slots?.label || this.$t('过滤条件')}</span>
        <span class='condition-colon'>:</span>
        {this.tagWrapRenderer()}
      </div>
    );
  }
}
