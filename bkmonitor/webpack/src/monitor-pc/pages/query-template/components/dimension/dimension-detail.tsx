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

import type { IDimensionOptionsItem } from '../type/query-config';

import './dimension-detail.scss';

interface DimensionProps {
  /* 已选聚合维度id数组 */
  dimensions: string[];
  /* 所有聚合维度信息列表数组 */
  options: IDimensionOptionsItem[];
  /* 变量列表 */
  variables?: VariableModelType[];
}

@Component
export default class DimensionDetail extends tsc<DimensionProps> {
  /* 已选聚合维度id数组 */
  @Prop({ type: Array }) dimensions: string[];
  /* 所有聚合维度信息列表数组 */
  @Prop({ default: () => [] }) options: IDimensionOptionsItem[];
  /* 变量列表 */
  @Prop({ default: () => [] }) variables?: VariableModelType[];
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

  get dimensionConfigs() {
    if (!this.dimensions?.length) {
      return [];
    }
    return this.dimensions.reduce((prev, curr) => {
      const result = this.variablesToolInstance.transformVariables(curr, this.variableMap);
      if (!Array.isArray(result.value)) {
        prev.push(result);
        return prev;
      }
      prev.push(...result.value.map(dimensionId => ({ ...result, value: dimensionId })));
      return prev;
    }, []);
  }

  tagRenderer() {
    if (!this.dimensionConfigs?.length) {
      return '--';
    }
    return this.dimensionConfigs?.map?.((item, index) => {
      const domTag = item.isVariable ? VariableSpan : 'span';
      return (
        <div
          class='tags-item'
          v-bk-tooltips={{
            content: item.value,
            placement: 'top',
            disabled: !item.value,
            delay: [300, 0],
          }}
        >
          <domTag
            id={item.variableName}
            key={index}
            class='tags-item-name'
          >
            {this.allDimensionMap?.[item.value]?.name || item.value}
          </domTag>
        </div>
      );
    });
  }

  render() {
    return (
      <div class='template-dimension-detail-component'>
        <span class='dimension-label'>{`${this.$t('聚合维度')}`}</span>
        <span class='dimension-colon'>:</span>
        <div class='tags-wrap'>{this.tagRenderer()}</div>
      </div>
    );
  }
}
