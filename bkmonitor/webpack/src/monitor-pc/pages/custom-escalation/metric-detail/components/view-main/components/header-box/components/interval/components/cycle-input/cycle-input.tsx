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
import { Component, Emit, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import './cycle-input.scss';

type unitType = 'm' | 's';

type IntervalType = 'auto' | number;

export interface IOption {
  children?: {
    id: IntervalType;
    name: number | string;
  }[];
  id: number | string;
  name: number | string;
}

interface IProps {
  appendTo?: string;
  hasExpanded?: boolean;
  isNeedDefaultVal?: boolean;
  minSec?: number;
  needAuto?: boolean;
  value?: number;
}

interface IEvent {
  onChange?: number;
}

const { i18n } = window;

@Component
export default class CycleInput extends tsc<IProps, IEvent> {
  @Model('change', { default: 0, type: [Number, String] }) value: IProps['value'];
  @Prop({
    type: Array,
    default: () => [
      { id: 's', name: i18n.t('秒'), children:
        [
          { id: 'auto', name: 'auto' },
          { id: 1, name: 1 },
          { id: 2, name: 2 },
          { id: 5, name: 5 },
          { id: 10, name: 10 },
          { id: 30, name: 30 },
          { id: 60, name: 60 }
        ]
      },
      { id: 'm', name: i18n.t('分'), children:
        [
          { id: 'auto', name: 'auto' },
          { id: 1, name: 1 },
          { id: 2, name: 2 },
          { id: 5, name: 5 },
          { id: 10, name: 10 },
          { id: 30, name: 30 },
          { id: 60, name: 60 }
        ]
      },
    ],
  })
  options: IOption[];
  @Prop({ default: 10, type: Number }) minSec: number; // 最小值 单位：秒
  @Prop({ default: 'body', type: String }) appendTo: string; // 默认挂在到body
  @Prop({ default: false, type: Boolean }) isNeedDefaultVal: boolean; // 是否需要设置默认值
  /* 是否包含下拉状态图标 */
  @Prop({ default: false, type: Boolean }) hasExpanded: boolean;

  @Ref('cyclePopover') cyclePopoverRef: any;
  @Ref('unitPopover') unitPopoverRef: any;

  /** 组件宽度 */
  inputWidth = 100;

  /** 本地显示值 */
  localValue: IntervalType = 0;

  /** 当前单位 */
  unit: unitType = 's';

  /** 单位按钮active状态 */
  unitActive = false;

  /** 失焦更新值标记 */
  isInputFocus = false;

  /** 自动模式下的显示文本 */
  autoDisplayText = 'auto';

  /** 当前周期可选列表 */
  get curCycleList() {
    return this.options.find(item => item.id === this.unit)?.children;
  }

  /** 单位名 */
  get unitName() {
    return this.options.find(item => item.id === this.unit)?.name || this.unit;
  }

  /** 是否是自动模式 */
  get isAutoMode() {
    return this.localValue === 'auto';
  }

  /** 从 store 取时间范围（用于建立响应式依赖，供 watch 监听） */
  get timeRangTimestampFromStore(): [number, number] {
    return this.$store.getters['customEscalationView/timeRangTimestamp'] ?? [0, 0];
  }

  @Watch('value', { immediate: true })
  valueChange(val: number) {
    if (this.isAutoMode) {
      customEscalationViewStore.setIntervalAuto(true);
      return;
    }
    customEscalationViewStore.setIntervalAuto(false);
    const timeVal = /([0-9]+)([sm]?)/.exec(val.toString());
    if (!timeVal) return;
    // 因为1m和60s相等， 需要进行特殊处理，否则会出现手动切换成1m时，会转化成60s
    if (val === 60) {
      this.localValue = this.unit === 's' ? 60 : 1;
      return;
    }
    if (!timeVal[2] && +timeVal[1] > 60) {
      this.unit = 'm';
      this.localValue = +timeVal[1] / 60;
    } else {
      if (this.isNeedDefaultVal && val === 0) {
        this.localValue = 0;
        this.unit = 's';
        return;
      }
      this.localValue = +timeVal[1] || Math.max(this.minSec, 60);
      this.unit = (timeVal[2] || 's') as unitType;
    }
  }

  @Watch('isAutoMode', { immediate: true })
  @Watch('timeRangTimestampFromStore', { immediate: true, deep: true })
  timeRangTimestampChange() {
    if (!this.isAutoMode) return;
    const sec = this.autoIntervalSec;
    this.autoDisplayText = this.formatIntervalDisplay(sec);
    this.emitValue();
  }

  @Emit('change')
  emitValue() {
    if (this.isAutoMode) {
      return this.autoIntervalSec;
    }
    let sec = this.timeToSec({ value: this.localValue as number, unit: this.unit });
    if (sec < this.minSec) {
      sec = this.minSec;
      this.localValue = sec;
    }
    return sec;
  }

  /**
   * 计算 auto 模式下的周期（秒）：ceil(时间范围/固定点数)，向上对齐到标准粒度，并满足下限 60s
   */
  get autoIntervalSec() {
    /** 固定数据点数，用于计算 auto 周期 */
    const AUTO_FIXED_POINTS = 300;
    /** 数据源最小采样周期（秒），最终周期不会小于此值 */
    const MIN_INTERVAL_SEC = 60;
    /** 
     * 标准粒度：10s, 30s, 1m, 2m, 5m, 10m, 15m, 30m, 1h, 2h, 6h, 12h, 1d
     * 向上（Ceil）：数据点更少，性能更安全，不会超出目标点数（对表上面的粒度对齐）
     * 标准粒度（秒）：向上对齐时在此序列中取第一个 >= 计算值的粒度 */
    const STANDARD_GRANULARITIES_SEC = [10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 21600, 43200, 86400];
    const [start, end] = this.timeRangTimestampFromStore;
    const timeRangeSec = (end ?? 0) - (start ?? 0);
    if (timeRangeSec <= 0) return MIN_INTERVAL_SEC;
    const rawIntervalSec = Math.ceil(timeRangeSec / AUTO_FIXED_POINTS);
    const alignedSec =
      STANDARD_GRANULARITIES_SEC.find(g => g >= rawIntervalSec) ??
      STANDARD_GRANULARITIES_SEC[STANDARD_GRANULARITIES_SEC.length - 1];
    return Math.max(alignedSec, MIN_INTERVAL_SEC);
  }

  /** 将秒数格式化为可读周期文案，如 60 -> '1m'，3600 -> '1h' */
  formatIntervalDisplay(sec: number): string {
    if (sec >= 86400) return `${sec / 86400}d`;
    if (sec >= 3600) return `${sec / 3600}h`;
    if (sec >= 60) return `${sec / 60}m`;
    return `${sec}s`;
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
    this.localValue = id === 's' ? Math.max(this.minSec, 10) : 1;
    this.emitValue();
  }

  /**
   * @description: 时间转秒
   */
  timeToSec(timeVal: { unit: unitType; value: number; }) {
    const unitMap: { [key in unitType]: (val: number) => number } = {
      m: (val: number) => val * 60,
      s: (val: number) => val,
    };
    const sec = unitMap?.[timeVal.unit]?.(timeVal.value);
    return sec;
  };

  /**
   * @description: 选择周期
   * @param {number} id 周期id
   * @return {*}
   */
  handleSelectCycle(id: IntervalType) {
    if (id === this.localValue) return;
    this.localValue = id;
    customEscalationViewStore.setIntervalAuto(id === 'auto');
    this.emitValue();
    this.cyclePopoverRef.instance.hide();
  }

  /**
   * @description: 输入聚焦
   * @return {*}
   */
  handleFocus() {
    this.isInputFocus = true;
  }

  /**
   * @description: 输入失焦
   * @param {*}
   * @return {*}
   */
  handleBlur() {
    if (this.isInputFocus) {
      this.isInputFocus = false;
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
          animation='slide-toggle'
          arrow={false}
          distance={12}
          offset={-1}
          placement='bottom-start'
          theme='light cycle-list-wrapper'
          tippyOptions={{ appendTo: this.appendTo === 'parent' ? 'parent' : document.body }}
          trigger='click'
        >
          <slot name='trigger'>
            {!this.isAutoMode ? (
              <bk-input
                class='input-text'
                precision={0}
                showControls={false}
                type={this.isAutoMode ? 'text' : 'number'}
                vModel_number={this.localValue}
                onBlur={this.handleBlur}
                onFocus={this.handleFocus}
              />
            ) : (
              <div class='auto-display-text'>
                <span>auto</span>
                <span style='margin-left: 4px;'>( {this.autoDisplayText} )</span>
              </div>
            )}
          </slot>
          <ul
            class='cycle-list'
            slot='content'
          >
            {this.curCycleList.map((item, index) => (
              <li
                key={index}
                class={[
                  'cycle-item',
                  { 'cycle-item-active': this.localValue === item.id },
                  { 'item-disabled': this.checkDisable(item.id) },
                ]}
                onClick={() => this.handleSelectCycle(item.id as number)}
              >
                {`${item.name} ${item.id !== 'auto' ? this.unit : ''}`}
              </li>
            ))}
          </ul>
        </bk-popover>
        {(!this.isAutoMode || this.isInputFocus) && (
          <bk-popover
            ref='unitPopover'
            class='cycle-unit-popover'
            animation='slide-toggle'
            arrow={false}
            disabled={this.isAutoMode}
            distance={12}
            offset={-1}
            placement='bottom-end'
            theme='light cycle-list-wrapper'
            tippyOptions={{ appendTo: this.appendTo === 'parent' ? 'parent' : document.body }}
            trigger='click'
            onHide={() => {
              this.unitActive = false;
            }}
          >
            <span
              class={['cycle-unit', { 'line-active': this.unitActive, 'unit-active': this.unitActive }]}
              v-en-style='min-width: 60px'
              onClick={() => {
                this.unitActive = true;
              }}
            >
              {this.unitName}
              {this.hasExpanded && (
                <span class='expand-wrap'>
                  <span class='icon-monitor icon-mc-arrow-down' />
                </span>
              )}
            </span>
            <ul
              ref='unitList'
              class='unit-list'
              slot='content'
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
        )}
      </div>
    );
  }
}
