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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './simple-select.scss';

interface IItem {
  id: string;
  name: string;
}

interface IProps {
  value: string[] | string;
  list?: IItem[];
  multiple?: boolean;
  popoverMinWidth?: number;
  disabled?: boolean;
}

interface IEvents {
  onChange?: IValue;
  onToggle?: boolean;
}

type IValue = string[] | string;

@Component
export default class SimpleSelect extends tsc<IProps, IEvents> {
  @Prop({ default: '', type: [Array, String] }) value: string[] | string;
  @Prop({ default: () => [], type: Array }) list: IItem[];
  @Prop({ default: false, type: Boolean }) multiple: boolean; // 是否多选
  @Prop({ default: 100, type: [Number, String] }) popoverMinWidth: number;
  @Prop({ default: false, type: Boolean }) disabled: boolean;

  @Ref('selectDropdown') selectRef: any;

  localValue: IValue = [];

  @Watch('value', { immediate: true, deep: true })
  handleValue(v: IValue) {
    this.localValue = v;
  }

  @Emit('change')
  handleChange() {
    return this.localValue;
  }
  // 切换下拉折叠状态时调用
  @Emit('toggle')
  handleToggle(v: boolean) {
    return v;
  }
  handleSelectChange(v: IValue) {
    this.localValue = v;
    this.handleChange();
  }
  handleClick() {
    if (this.disabled) return;
    this.selectRef?.show();
  }

  render() {
    return (
      <span
        class='simple-select-component'
        onClick={this.handleClick}
      >
        <span class='btn-content'>{this.$slots?.default}</span>
        <bk-select
          class='select-dropdown'
          ref='selectDropdown'
          value={this.localValue}
          popoverMinWidth={this.popoverMinWidth || 100}
          multiple={this.multiple}
          on-toggle={v => this.handleToggle(v)}
          on-change={this.handleSelectChange}
        >
          {this.list.map(item => (
            <bk-option
              key={item.id}
              id={item.id}
              name={item.name}
            ></bk-option>
          ))}
        </bk-select>
      </span>
    );
  }
}
