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

import { IEvent, IntervalType, IOption, IProps, unitType } from '../../../monitor-pc/components/cycle-input/typings';
import { defaultCycleOptionMin, defaultCycleOptionSec } from '../../../monitor-pc/components/cycle-input/utils';

import '../../../monitor-pc/components/cycle-input/cycle-input.scss';

const { i18n } = window;

@Component
export default class CycleInput extends tsc<IProps, IEvent> {
  @Model('change', { default: 0, type: [Number, String] }) value: IProps['value'];
  @Prop({
    type: Array,
    default: () => [
      { id: 's', name: i18n.t('秒'), children: defaultCycleOptionSec },
      { id: 'm', name: i18n.t('分'), children: defaultCycleOptionMin }
    ]
  })
  options: IOption[];
  @Prop({ default: 10, type: Number }) minSec: number; // 最小值 单位：秒
  @Prop({ default: 'body', type: String }) appendTo: string; // 默认挂在到body
  @Prop({ default: 's', type: String }) defaultUnit: unitType; // 默认秒

  @Ref('cyclePopover') cyclePopoverRef: any;
  @Ref('unitPopover') unitPopoverRef: any;

  /** 组件宽度 */
  inputWidth = 100;

  /** 本地显示值 */
  localValue: IntervalType = 10;

  /** 当前单位 */
  unit: unitType = 's';

  /** 单位按钮active状态 */
  unitActive = false;

  /** 失焦更新值标记 */
  allowBlurUpdateValue = false;

  /** 当前周期可选列表 */
  get curCycleList() {
    const list = this.options.find(item => item.id === this.unit)?.children;
    return list.filter(item => item.id !== 'auto');
  }

  /** 单位名 */
  get unitName() {
    return this.options.find(item => item.id === this.unit)?.name || this.unit;
  }

  @Emit('change')
  emitValue(): IntervalType {
    this.unitChange();
    return this.localValue;
  }

  @Emit('unitChange')
  unitChange(): string {
    return this.unit;
  }

  created() {
    this.unit = this.defaultUnit;
  }

  /**
   * @description: 选择单位
   * @param {string} id 单位id
   * @return {*}
   */
  handleSelectUnit(id: unitType) {
    if (this.unit === id) return;
    this.unitPopoverRef.instance.hide();
    this.unit = id;
    this.emitValue();
  }
  /**
   * @description: 选择周期
   * @param {number} id 周期id
   * @return {*}
   */
  handleSelectCycle(id: IntervalType) {
    if (id === this.localValue) return;
    this.localValue = id;
    this.emitValue();
    this.cyclePopoverRef.instance.hide();
  }
  /**
   * @description: 输入周期
   * @param {*} evt 输入事件
   * @return {*}
   */
  handleInput() {
    this.allowBlurUpdateValue = true;
  }

  /**
   * @description: 输入失焦
   * @param {*}
   * @return {*}
   */
  handleBlur() {
    if (this.allowBlurUpdateValue) {
      this.allowBlurUpdateValue = false;
      this.emitValue();
    }
  }
  /**
   * @description: 判断是否小于最小值
   * @param v 值
   * @return {*}
   */
  checkDisable(v: IntervalType) {
    if (v === 'auto') return false;
    const val = +v * (this.unit === 'm' ? 60 : 1);
    return val < this.minSec;
  }
  render() {
    return (
      <div class='cycle-input-wrap'>
        <bk-popover
          ref='cyclePopover'
          class='input-popover'
          trigger='click'
          placement='bottom-start'
          theme='light cycle-list-wrapper'
          animation='slide-toggle'
          arrow={false}
          offset={-1}
          distance={12}
          tippyOptions={{ appendTo: this.appendTo === 'parent' ? 'parent' : document.body }}
        >
          <slot name='trigger'>
            <bk-input
              class='input-text'
              vModel_number={this.localValue}
              type={this.localValue === 'auto' ? 'text' : 'number'}
              // precision={0}
              showControls={false}
              onInput={this.handleInput}
              onBlur={this.handleBlur}
            />
          </slot>
          <ul
            slot='content'
            class='cycle-list'
          >
            {this.curCycleList.map((item, index) => (
              <li
                key={index}
                class={[
                  'cycle-item',
                  { 'cycle-item-active': this.localValue === item.id },
                  { 'item-disabled': this.checkDisable(item.id) }
                ]}
                onClick={() => this.handleSelectCycle(item.id as number)}
              >
                {`${item.name} ${item.id !== 'auto' ? this.unit : ''}`}
              </li>
            ))}
          </ul>
        </bk-popover>
        <bk-popover
          disabled={this.localValue === 'auto'}
          ref='unitPopover'
          trigger='click'
          placement='bottom-end'
          theme='light cycle-list-wrapper'
          animation='slide-toggle'
          arrow={false}
          offset={-1}
          distance={12}
          tippyOptions={{ appendTo: this.appendTo === 'parent' ? 'parent' : document.body }}
          onHide={() => (this.unitActive = false)}
        >
          <span
            class={['cycle-unit', { 'line-active': this.unitActive, 'unit-active': this.unitActive }]}
            v-en-style='min-width: 60px'
            onClick={() => (this.unitActive = true)}
          >
            {this.unitName}
          </span>
          <ul
            slot='content'
            class='unit-list'
            ref='unitList'
          >
            {this.options.map((item, index) => (
              <li
                key={index}
                class={['cycle-item', { 'cycle-item-active': this.unit === item.id }]}
                onClick={() => this.handleSelectUnit(item.id as unitType)}
              >
                {item.name}
              </li>
            ))}
          </ul>
        </bk-popover>
      </div>
    );
  }
}
