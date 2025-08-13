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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { IOption } from '../../typings';
import type { TranslateResult } from 'vue-i18n';

import './filter-var-select-simple.scss';

export interface IEvents {
  onChange: string | string[];
}
export interface IProps {
  field: string;
  label: string | TranslateResult;
  multiple?: boolean;
  options: IOption[];
  value?: ValueType;
}

type ValueType = number | string | string[];
@Component
export default class FilterVarSelectSimple extends tsc<IProps, IEvents> {
  /** 组件标题 */
  @Prop({ default: '', type: String }) label: string | TranslateResult;
  /** 组件返回值的key */
  @Prop({ default: 'key', type: String }) field: string;
  /** 是否多选 */
  @Prop({ default: false, type: Boolean }) multiple: boolean;
  /** 组件的可选项 */
  @Prop({ default: () => [], type: Array }) options: IOption[];
  /** 回显值 */
  @Prop({ default: '', type: [String, Array, Number] }) value: ValueType;

  localValue: ValueType = '';

  @Emit('change')
  handleSelectChange(): ValueType {
    return this.localValue;
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValue = this.value;
  }

  render() {
    return (
      <span class='filter-var-select-simple-wrap'>
        {this.label && <span class='filter-var-label'>{this.label}</span>}
        <bk-select
          class='bk-select-simplicity filter-var-select'
          v-model={this.localValue}
          behavior='simplicity'
          clearable={false}
          multiple={this.multiple}
          onSelected={this.handleSelectChange}
        >
          {this.options.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            />
          ))}
        </bk-select>
      </span>
    );
  }
}
