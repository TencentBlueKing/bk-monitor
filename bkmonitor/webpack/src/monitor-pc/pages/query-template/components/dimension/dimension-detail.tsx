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

import type { DimensionField } from '../../typings';
import type { VariableModelType } from '../../variables';

import './dimension-detail.scss';

interface DimensionProps {
  /* 聚合维度信息 id-聚合维度对象 映射表 */
  allDimensionMap: Record<string, DimensionField>;
  /* 已选聚合维度id数组 */
  value: string[];
  /* 变量 variableName-变量对象 映射表 */
  variableMap?: Record<string, VariableModelType>;
}

@Component
export default class DimensionDetail extends tsc<DimensionProps> {
  /* 已选聚合维度id数组 */
  @Prop({ type: Array }) value: string[];
  /* 聚合维度信息 id-聚合维度对象 映射表 */
  @Prop({ default: () => [] }) allDimensionMap: Record<string, DimensionField>;
  /* 变量 variableName-变量对象 映射表 */
  @Prop({ default: () => [] }) variableMap?: Record<string, VariableModelType>;

  /** 将已选聚合维度id 源数据数组 转换为渲染所需的 QueryVariablesTransformResult 结构数组 */
  get dimensionToVariableModel(): QueryVariablesTransformResult[] {
    if (!this.value?.length) {
      return [];
    }
    return this.value.reduce((prev, curr) => {
      const result = getQueryVariablesTool().transformVariables(curr);
      if (!result.value) {
        return prev;
      }
      prev.push(result);
      return prev;
    }, []);
  }

  tagItemRenderer(item) {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const DomTag = item.isVariable ? VariableSpan : 'span';
    return (
      <div
        id={item.variableName}
        class='tags-item'
        v-bk-tooltips={{
          content: item.value,
          placement: 'top',
          disabled: !item.value,
          delay: [300, 0],
        }}
      >
        <DomTag class='tags-item-name'>
          {this.allDimensionMap?.[item.value]?.name ||
            getQueryVariablesTool().getVariableAlias(item.value, this.variableMap)}
        </DomTag>
      </div>
    );
  }

  tagWrapRenderer() {
    const content = this.dimensionToVariableModel?.reduce?.((prev, curr) => {
      if (!curr.isVariable) {
        prev.push(this.tagItemRenderer(curr));
        return prev;
      }
      let varValue = '';
      const templateReplaceKey = `\${${curr.variableName}:json}`;
      const result = getTemplateSrv().replace(templateReplaceKey, this.variableMap);
      try {
        varValue = JSON.parse(result);
      } catch {
        if (result !== templateReplaceKey) varValue = result || '';
      }
      if (Array.isArray(varValue)) {
        const items = varValue?.length
          ? varValue.map(v => this.tagItemRenderer({ ...curr, value: v }))
          : [this.tagItemRenderer(curr)];
        prev.push(...items);
        return prev;
      }
      prev.push(
        this.tagItemRenderer({
          ...curr,
          value: varValue || curr.value,
        })
      );
      return prev;
    }, []);

    return <div class='tags-wrap'>{content?.length ? content : '--'}</div>;
  }

  render() {
    return (
      <div class='template-dimension-detail-component'>
        <span class='dimension-label'>{this.$slots?.label || this.$t('聚合维度')}</span>
        <span class='dimension-colon'>:</span>
        {this.tagWrapRenderer()}
      </div>
    );
  }
}
