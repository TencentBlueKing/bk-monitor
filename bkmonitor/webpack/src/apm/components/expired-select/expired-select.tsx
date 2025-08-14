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
import { Component, Emit, Model, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { TranslateResult } from 'vue-i18n';

import './expired-select.scss';

export interface IOptionsItem {
  id: IProps['value'];
  name: string | TranslateResult;
}
interface IEvents {
  onChange: number;
}
interface IProps {
  max?: number;
  options?: IOptionsItem[];
  placeholder?: string;
  unit?: string;
  value?: number;
  width?: number;
}

const DEFAULT_OPTIONS: IOptionsItem[] = [
  {
    id: 1,
    name: window.i18n.t(' {n} 天', { n: 1 }),
  },
  {
    id: 3,
    name: window.i18n.t(' {n} 天', { n: 3 }),
  },
  {
    id: 7,
    name: window.i18n.t(' {n} 天', { n: 7 }),
  },
  {
    id: 14,
    name: window.i18n.t(' {n} 天', { n: 14 }),
  },
];

@Component
export default class ExpiredSelect extends tsc<IProps, IEvents> {
  @Model('change', { type: [Number, String] }) value: IProps['value'];
  /** 可选项 */
  @Prop({ default: () => DEFAULT_OPTIONS, type: Array }) options: IOptionsItem[];
  /** 单位 */
  @Prop({ default: window.i18n.tc('天'), type: String }) unit: string;
  /** 自定义输入占位符 */
  @Prop({ default: window.i18n.tc('输入自定义的天数，按Enter确认'), type: String }) placeholder: string;
  /** 组件宽度 */
  @Prop({ type: Number }) width: number;
  /** 最大值 */
  @Prop({ type: Number, default: Number.POSITIVE_INFINITY }) max: number;

  @Ref() selectRef: any;

  /** 自定义选项 */
  customOptions: IOptionsItem[] = [];

  customInput = '';

  get localOptions() {
    return [...this.options, ...this.customOptions]
      .filter(item => item.id <= this.max)
      .reduce((total, item) => {
        if (!total.find(set => set.id === item.id)) total.push(item);
        return total;
      }, [])
      .sort((a, b) => a.id - b.id);
  }

  @Emit('change')
  valueChange(val) {
    return val;
  }

  created() {
    this.init();
  }

  /** 初始化数据，自动添加自定义选项 */
  init() {
    const option = this.localOptions.find(item => item.id === this.value);
    if (!option) this.addCustomOptions(this.value);
  }

  /**
   * 回车确认自定义输入
   * @param val
   */
  handleEnter(val: IProps['value']) {
    if (val > this.max) {
      this.$bkMessage({ message: this.$t('最大自定义天数为{n}天', { n: this.max }), theme: 'error' });
    } else if (val < 0) {
      this.$bkMessage({ message: this.$t('不支持填写负数'), theme: 'error' });
    } else if (val !== this.value && !!+val) {
      this.valueChange(+val);
      this.addCustomOptions(+val);
      this.hide();
    } else {
      this.hide();
    }
  }

  /** 隐藏下拉 */
  hide() {
    this.selectRef?.getPopoverInstance?.()?.hide?.();
    this.customInput = '';
  }

  /** 添加自定义选项 */
  addCustomOptions(val: IProps['value']) {
    this.customOptions.push({
      id: val,
      name: `${val}${this.unit}`,
    });
  }

  /** 下拉的展开和收起 */
  handleToggle(val: boolean) {
    if (!val) this.customInput = '';
  }

  render() {
    return (
      <bk-select
        key={JSON.stringify(this.localOptions)}
        ref='selectRef'
        style={{ width: `${this.width}px` }}
        clearable={false}
        value={this.value}
        onChange={this.valueChange}
        onToggle={this.handleToggle}
      >
        {this.localOptions.map(opt => (
          <bk-option
            id={opt.id}
            name={opt.name}
          />
        ))}
        <div
          class='expired-select-custom-input-wrap'
          slot='extension'
        >
          <bk-input
            v-model={this.customInput}
            placeholder={this.placeholder}
            show-controls={false}
            size='small'
            type='number'
            onEnter={this.handleEnter}
          />
        </div>
      </bk-select>
    );
  }
}
