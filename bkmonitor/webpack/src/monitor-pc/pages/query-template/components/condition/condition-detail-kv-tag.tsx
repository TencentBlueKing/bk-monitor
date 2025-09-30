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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ConditionMethodAliasMap } from '../../constants';
import { getTemplateSrv } from '../../variables/template/template-srv';
import { getQueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import type { AggCondition, ConditionDetailTagItem, DimensionField } from '../../typings';

import './condition-detail-kv-tag.scss';

interface IProps {
  /* 聚合维度信息 id-聚合维度对象 映射表 */
  allDimensionMap: Record<string, DimensionField>;
  /** 是否是条件变量渲染 */
  isConditionVariable?: boolean;
  /** 条件对象 */
  value: AggCondition;
  /* 变量 variableName-变量对象 映射表 */
  variableMap?: Record<string, any>;
  /** 条件变量名称 */
  variableName?: string;
  /** 维度值允许显示个数，多出显示省略号(不传默认全显示) */
  visibleItemLimit?: number;
}
@Component
export default class ConditionDetailKvTag extends tsc<IProps> {
  /** 条件对象 */
  @Prop({ type: Object, default: () => null }) value: AggCondition;
  /** 维度值允许显示个数，多出显示省略号(不传或假值时默认全显示) */
  @Prop({ type: Number, default: 0 }) visibleItemLimit: number;
  /** 是否是条件变量渲染 */
  @Prop({ type: Boolean, default: false }) isConditionVariable: boolean;
  /** 条件变量名称 */
  @Prop({ type: String, default: '' }) variableName: string;
  /* 变量 variableName-变量对象 映射表 */
  @Prop({ type: Object, default: () => {} }) variableMap: Record<string, any>;
  /* 聚合维度信息 id-聚合维度对象 映射表 */
  @Prop({ default: () => [] }) allDimensionMap: Record<string, DimensionField>;

  hideCount = 0;

  get tipContent() {
    return `<div style="max-width: 600px;">${this.value.key} ${ConditionMethodAliasMap[this.value.method]} ${this.viewValue.map(v => v.id).join(' OR ')}<div>`;
  }

  get DomTag() {
    return this.isConditionVariable ? VariableSpan : 'span';
  }

  get dimensionValueToVariableModel(): AggCondition['value'] | ConditionDetailTagItem['value'] {
    if (!this.value.value?.length) {
      return [];
    }
    if (this.isConditionVariable) {
      return this.value.value;
    }
    return this.value.value.reduce((prev, curr) => {
      const result = getQueryVariablesTool().transformVariables(curr);
      if (!result.value) {
        return prev;
      }
      prev.push(result);
      return prev;
    }, []);
  }

  get viewValue() {
    if (this.isConditionVariable) {
      return this.dimensionValueToVariableModel.map(v => ({
        id: v,
        name: this.showNameSlice(v),
        isVariable: false,
        variableName: '',
      }));
    }

    return (this.dimensionValueToVariableModel as ConditionDetailTagItem['value'])?.reduce?.((prev, curr) => {
      if (!curr.isVariable) {
        prev.push({
          id: curr.value,
          name: this.showNameSlice(curr.value),
          isVariable: curr.isVariable,
          variableName: '',
        });
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
          ? varValue.map(v => ({
              id: v,
              name: this.showNameSlice(v),
              isVariable: curr.isVariable,
              variableName: curr.variableName,
            }))
          : [
              {
                id: curr.value,
                name: this.showNameSlice(getQueryVariablesTool().getVariableAlias(curr.value, this.variableMap)),
                isVariable: curr.isVariable,
                variableName: curr.variableName,
              },
            ];
        prev.push(...items);
        return prev;
      }
      prev.push({
        id: varValue || curr.value,
        name: this.showNameSlice(varValue || getQueryVariablesTool().getVariableAlias(curr.value, this.variableMap)),
        isVariable: curr.isVariable,
        variableName: curr.variableName,
      });
      return prev;
    }, []);
  }

  @Watch('viewValue', { immediate: true })
  calcHideCount(newVal) {
    this.hideCount = this.visibleItemLimit ? newVal?.length - this.visibleItemLimit : 0;
  }

  showNameSlice(showName: string) {
    return showName.length > 20 ? `${showName.slice(0, 20)}...` : showName;
  }

  valueWrapRenderer() {
    return (
      <div class='value-wrap'>
        {this.viewValue.slice(0, this.visibleItemLimit || this.viewValue?.length).map((item, index) => {
          // eslint-disable-next-line @typescript-eslint/naming-convention
          const ValueNameDomTag = item?.isVariable ? VariableSpan : this.DomTag;
          return [
            index > 0 && (
              <this.DomTag
                key={`${index}_condition`}
                class='value-condition'
              >
                OR
              </this.DomTag>
            ),
            <ValueNameDomTag
              id={item.variableName}
              key={`${index}_key`}
              class='value-name'
            >
              {item.name || '""'}
            </ValueNameDomTag>,
          ];
        })}
        {this.hideCount > 0 && <span class='value-condition'>{`+${this.hideCount}`}</span>}
      </div>
    );
  }

  render() {
    return this.value ? (
      <div class='condition-detail-kv-tag-component'>
        <div
          id={this.variableName}
          key={this.tipContent}
          class='condition-detail-kv-tag-component-wrap'
          v-bk-tooltips={{
            content: this.tipContent,
            delay: [300, 0],
            allowHTML: true,
          }}
        >
          <div class='key-wrap'>
            <this.DomTag class='key-name'>
              {this.value.dimension_name || this.allDimensionMap?.[this.value?.key]?.name || this.value.key}
            </this.DomTag>
            <this.DomTag class={['key-method', this.value.method]}>
              {ConditionMethodAliasMap[this.value.method]}
            </this.DomTag>
          </div>
          {this.valueWrapRenderer()}
        </div>
      </div>
    ) : undefined;
  }
}
