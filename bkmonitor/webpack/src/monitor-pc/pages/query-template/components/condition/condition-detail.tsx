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

import { type AggCondition, type DimensionField } from '../../typings';
import { type VariableModelType } from '../../variables';
import { QueryVariablesTool } from '../utils/query-variable-tool';
import { type IFilterField, EFieldType } from '@/components/retrieval-filter/utils';
import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from '@/constant/constant';

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
      const conditionResult = this.variablesToolInstance.transformVariables(curr.key);
      if (!Array.isArray(conditionResult.value)) {
        prev.push(conditionResult);
        return prev;
      }
      prev.push(...conditionResult.value.map(dimensionId => ({ ...conditionResult, value: dimensionId })));
      return prev;
    }, []);
  }

  tagRenderer() {
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

  render() {
    return (
      <div class='template-condition-detail-component'>
        <span class='condition-label'>{this.$slots?.label || this.$t('过滤条件')}</span>
        <span class='condition-colon'>:</span>
        <div class='tags-wrap'>{this.tagRenderer()}</div>
      </div>
    );
  }
}
