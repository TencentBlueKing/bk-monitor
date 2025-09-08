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
import { type QueryVariablesTransformResult, getQueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';
import ConditionDetailKvTag from './condition-detail-kv-tag';

import type { AggCondition, DimensionField } from '../../typings';
import type { VariableModelType } from '../../variables';

import './condition-detail.scss';

interface IProps {
  /* 聚合维度信息 id-聚合维度对象 映射表 */
  allDimensionMap: Record<string, DimensionField>;
  /* 已选过滤条件 */
  value: AggCondition[];
  /* 变量 variableName-变量对象 映射表 */
  variableMap?: Record<string, VariableModelType>;
}

@Component
export default class ConditionDetail extends tsc<IProps> {
  /* 变量 variableName-变量对象 映射表 */
  @Prop({ default: () => [] }) variableMap?: Record<string, VariableModelType>;
  /* 已选过滤条件 */
  @Prop({ default: () => [] }) value: AggCondition[];
  /* 聚合维度信息 id-聚合维度对象 映射表 */
  @Prop({ default: () => [] }) allDimensionMap: Record<string, DimensionField>;

  get conditionToVariableModel() {
    if (!this.value?.length) {
      return [];
    }
    return this.value.reduce((prev, curr) => {
      const conditionResult = getQueryVariablesTool().transformVariables(
        curr.key
      ) as QueryVariablesTransformResult<AggCondition>;
      if (!conditionResult.value) {
        return prev;
      }
      // 浅拷贝，避免后续转换结构影响上层源数据
      conditionResult.value = { ...curr, value: [...(curr.value || [])] };
      prev.push(conditionResult);
      return prev;
    }, []);
  }

  conditionVariableTagItemRenderer(item) {
    return (
      <ConditionDetailKvTag
        allDimensionMap={this.allDimensionMap}
        isConditionVariable={item.isVariable ?? false}
        value={item.value}
        variableMap={this.variableMap}
        variableName={item.variableName}
      />
    );
  }

  emptyVariableTagItemRenderer(item) {
    return (
      <div
        id={item.variableName}
        key={item.value.key}
        class='variable-tag'
      >
        <VariableSpan>{getQueryVariablesTool().getVariableAlias(item.value?.key, this.variableMap)}</VariableSpan>
      </div>
    );
  }

  /**
   * @description 条件变量渲染逻辑
   */
  conditionVariableRenderer(item: QueryVariablesTransformResult<AggCondition>) {
    let varValue = '';
    const result = getTemplateSrv().replace(`\${${item.variableName}:json}` as string, this.variableMap);
    try {
      varValue = JSON.parse(result);
    } catch {
      varValue = '';
    }
    if (!varValue) {
      return [this.emptyVariableTagItemRenderer(item)];
    }
    if (Array.isArray(varValue)) {
      return varValue?.length
        ? varValue.map(v =>
            this.conditionVariableTagItemRenderer({
              ...item,
              value: v,
            })
          )
        : [this.emptyVariableTagItemRenderer(item)];
    }
    return [
      this.conditionVariableTagItemRenderer({
        ...item,
        value: varValue,
      }),
    ];
  }

  tagWrapRenderer() {
    const content = this.conditionToVariableModel?.reduce?.((prev, curr) => {
      // 非条件变量则判断知否存在维度值变量
      if (!curr.isVariable) {
        prev.push(this.conditionVariableTagItemRenderer(curr));
        return prev;
      }
      // 条件变量执行支线
      prev.push(...this.conditionVariableRenderer(curr));

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
