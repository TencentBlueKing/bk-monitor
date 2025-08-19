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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { ConditionMethodAliasMap } from '../../constants';
import { type AggCondition, type ConditionDetailTagItem } from '../../typings';
import { getTemplateSrv } from '../../variables/template/template-srv';
import { type QueryVariablesTransformResult, QueryVariablesTool } from '../utils/query-variable-tool';
import VariableSpan from '../utils/variable-span';

import './condition-detail-kv-tag.scss';

interface IProps {
  /** 是否是条件变量渲染 */
  isConditionVariable?: boolean;
  /** 条件对象 */
  value: AggCondition | ConditionDetailTagItem;
  variableMap?: Record<string, any>;
  /** 条件变量名称 */
  variableName?: string;
  /** 维度值允许显示个数，多出显示省略号(不传默认全显示) */
  visibleItemLimit?: number;
}
@Component
export default class ConditionDetailKvTag extends tsc<IProps> {
  /** 条件对象 */
  @Prop({ type: Object, default: () => null }) value: AggCondition | ConditionDetailTagItem;
  /** 维度值允许显示个数，多出显示省略号(不传或假值时默认全显示) */
  @Prop({ type: Number, default: 0 }) visibleItemLimit: number;
  /** 是否是条件变量渲染 */
  @Prop({ type: Boolean, default: false }) isConditionVariable: boolean;
  /** 条件变量名称 */
  @Prop({ type: String, default: '' }) variableName: string;
  @Prop({ type: Object, default: () => {} }) variableMap: Record<string, any>;
  templateSrv = getTemplateSrv();
  localValue: Omit<AggCondition, 'value'> & {
    value: { id: string; isVariable?: boolean; name: string; variableName?: string }[];
  } = null;
  hideCount = 0;

  get tipContent() {
    return `<div style="max-width: 600px;">${this.localValue.key} ${ConditionMethodAliasMap[this.localValue.method]} ${this.localValue.value.map(v => v.id).join(' OR ')}<div>`;
  }

  get DomTag() {
    return this.isConditionVariable ? VariableSpan : 'span';
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.value && JSON.stringify(this.localValue || {}) !== JSON.stringify(this.value)) {
      const localValue = JSON.parse(JSON.stringify(this.value));
      const value = [];
      if (this.isConditionVariable) {
        for (const v of this.value.value as AggCondition['value']) {
          value.push({
            id: v,
            name: this.showNameSlice(v),
            isVariable: false,
          });
        }
      } else {
        for (const variableMode of this.value.value as ConditionDetailTagItem['value']) {
          if (!variableMode.isVariable) {
            const id = variableMode.value;
            value.push({
              id: id,
              name: this.showNameSlice(id),
              isVariable: variableMode.isVariable,
            });
            continue;
          }
          let varValue = '';
          const result = this.templateSrv.replace(`\${${variableMode.variableName}:json}` as string, this.variableMap);
          try {
            varValue = JSON.parse(result);
          } catch {
            varValue = '';
          }
          if (Array.isArray(varValue)) {
            value.push(
              ...varValue.map(v => ({
                id: v,
                name: this.showNameSlice(v),
                isVariable: variableMode.isVariable,
              }))
            );
            continue;
          }
          const id = varValue || variableMode.value;
          value.push({
            id: id,
            name: this.showNameSlice(id),
            isVariable: variableMode.isVariable,
          });
        }
      }
      this.localValue = {
        ...localValue,
        value,
      };
      this.hideCount = this.visibleItemLimit ? this.value.value.length - this.visibleItemLimit : 0;
    }
  }

  showNameSlice(showName: string) {
    return showName.length > 20 ? `${showName.slice(0, 20)}...` : showName;
  }

  valueWrapRenderer() {
    return (
      <div class='value-wrap'>
        {this.localValue.value.map((item, index) => {
          const valueNameDomTag = item?.isVariable ? VariableSpan : this.DomTag;
          return [
            index > 0 && (
              <this.DomTag
                key={`${index}_condition`}
                class='value-condition'
              >
                OR
              </this.DomTag>
            ),
            <valueNameDomTag
              key={`${index}_key`}
              class='value-name'
            >
              {item.name || '""'}
            </valueNameDomTag>,
          ];
        })}
        {this.hideCount > 0 && <span class='value-condition'>{`+${this.hideCount}`}</span>}
      </div>
    );
  }

  render() {
    return this.localValue ? (
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
            <this.DomTag class='key-name'>{this.localValue.dimension_name}</this.DomTag>
            <this.DomTag class={['key-method', this.localValue.method]}>
              {ConditionMethodAliasMap[this.localValue.method]}
            </this.DomTag>
          </div>
          {this.valueWrapRenderer()}
        </div>
      </div>
    ) : undefined;
  }
}
