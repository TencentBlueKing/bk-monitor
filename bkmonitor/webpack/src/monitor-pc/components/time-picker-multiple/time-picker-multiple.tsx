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
import { Component, Emit, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { modifiers, Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import {
  defaultAddTimeRange,
  timeRangeValidate,
} from 'fta-solutions/pages/setting/set-meal/set-meal-add/meal-content/meal-content-data';
import { Debounce, deepClone } from 'monitor-common/utils/utils';

import './time-picker-multiple.scss';

const END_TIME = '23:59:59';
const START_TIME = '00:00:00';
const TIME_FORMATER = 'HH:mm';
const TIME_FORMAT_REG = /HH|mm|ss/g;

enum EMode {
  add = 'add', // 新增时间范围
  edit = 'edit', // 编辑时间范围
}
export interface IProps {
  allowNextFocus?: boolean;
  autoSort?: boolean;
  format?: 'HH:mm' | 'HH:mm:ss';
  needHandle?: boolean;
  placeholder?: string;
  value?: Array<TimeRange>; // [['09:00:00', '10:00:00']]
}
interface IEvents {
  onChange: IProps['value'];
}
type TimeRange = [string, string];
/**
 * 多选的时间范围组件
 */
@Component
export default class TimePickerMultiple extends tsc<IProps, IEvents> {
  @Model('change', { type: Array, default: () => [] }) value: IProps['value'];
  @Prop({ type: String, default: window.i18n.tc('选择时间范围') }) placeholder: IProps['placeholder'];
  @Prop({ type: Boolean, default: true }) autoSort: IProps['autoSort']; // 值变更后时间范围自动排序
  @Prop({ type: Boolean, default: false }) needHandle: IProps['needHandle']; // 是否需要操作按钮 确认、取消
  @Prop({ type: Boolean, default: false }) allowNextFocus: IProps['allowNextFocus']; // 是否允许选中后继续添加
  @Prop({ type: String, default: TIME_FORMATER }) format: IProps['format']; // 时间格式
  @Ref() triggerInputRef: Element;
  @Ref() timeRangeListRef: Element;
  @Ref() inputRef: any;
  @Ref() timePickerRef: any;

  /** 时间范围面板展示 */
  isShow = false;
  /** 触发时间范围面板的目标 */
  targetEl: Element = null;
  /** 编辑模式 edit 编辑 add 新增 */
  mode: EMode = EMode.add;
  /** 输入框输入值 */
  triggerInputText = '';
  /** 新增、编辑索引 */
  currentIndex = 0;
  /** 面板的时间范围 */
  timeRange: TimeRange = ['', ''];
  /** 当前时间范围值 */
  localValue: IProps['value'] = [];
  /** 自定义输入时间 */
  isCustomTimeRange = false;
  /** 是否清除全部 */
  isClearAll = false;
  /** 是否聚焦状态 */
  isFocus = false;

  @Watch('value', { immediate: true })
  valueChange(val: IProps['value']) {
    this.localValue = deepClone(val);
    // this.hasEmptyTime = !!this.handleCreateTimeRange();
  }

  get isAllowAdd() {
    return this.localValue.length ? !!defaultAddTimeRange(this.localValue).length : true;
  }

  /**
   * 新增时间范围
   */
  handleAddTimeRange() {
    if (this.isShow || this.isFocus) return;
    this.mode = EMode.add;
    this.targetEl = null;
    this.timeRange = this.handleCreateTimeRange();
    if (!this.timeRange) return;
    this.currentIndex = this.localValue.length;
    this.localValue.push([...this.timeRange]);
    this.handleMoveTrigger(true);
    this.$nextTick(() => (this.isShow = true));
  }

  /**
   * 根据当前空闲时间段自动生成可选的时间段
   */
  handleCreateTimeRange() {
    let timeRange = null;
    if (!this.localValue.length) {
      // 默认添加天时间
      timeRange = [START_TIME, END_TIME];
    } else {
      const timeRanges = defaultAddTimeRange(this.localValue);
      timeRange = timeRanges?.[0] || null;
    }
    return timeRange;
  }

  /**
   * 根据时间获取当天时间对象
   * @param time '10:00:00'格式
   * @returns moment 实例
   */
  getTimeMoment(time: string) {
    const methodList = ['hour', 'minute', 'second'];
    const timeList = time.split(':');
    return methodList.reduce((moment, method, index) => {
      const val = timeList[index];
      if (val) {
        return moment[method]?.(timeList[index]);
      }
      return moment;
    }, dayjs.tz());
  }

  /**
   * 点击选中某个时间段
   * @param evt 点击事件
   * @param index 目标索引
   */
  handleClickItem(evt, index: number) {
    this.mode = EMode.edit;
    this.targetEl = evt.currentTarget;
    this.timeRange = this.localValue[index];
    this.currentIndex = index;
    this.handleMoveTrigger();
    setTimeout(() => {
      this.isShow = true;
      this.inputFocus();
    }, 100);
  }

  /** 获取输入框焦点 */
  inputFocus() {
    setTimeout(() => this.inputRef.focus(), 50);
  }

  /**
   * 删除一个时间范围
   */
  @Debounce(100)
  handleDelItem() {
    if (this.triggerInputText.length > 0) return;
    this.localValue.splice(this.currentIndex, 1);
    if (this.currentIndex) {
      this.currentIndex -= 1;
      this.targetEl = this.timeRangeListRef.children[this.currentIndex];
      this.timeRange = [...this.localValue[this.currentIndex]];
      this.$nextTick(() => this.handleMoveTrigger());
      setTimeout(() => {
        this.isShow = true;
        this.inputFocus();
      }, 300);
    } else {
      this.isShow = false;
    }
    this.triggerInputText = this.localValue[this.currentIndex]?.join?.('-') || '';
    this.mode = EMode.edit;
    this.handleValueChange();
  }

  /**
   * 点击确认
   */
  @Debounce(100)
  handleSubmit() {
    if (this.isClearAll) return;
    const allTime = deepClone(this.localValue);
    allTime.splice(this.currentIndex, 1);
    const isPass = timeRangeValidate(allTime, this.timeRange);
    if (isPass) {
      if (this.mode === EMode.edit) {
        this.isShow = false;
      }
      this.$set(this.localValue, this.currentIndex, [...this.timeRange]);
      this.handleValueChange();
      if (this.mode === EMode.add && this.allowNextFocus) {
        this.handleAddTimeRange();
      }
    } else {
      if (this.mode === EMode.add) {
        this.localValue.splice(this.localValue.length - 1, 1);
      }
      this.$bkMessage({
        theme: 'warning',
        message: this.$tc('时间段重叠了'),
      });
    }
  }

  /**
   * 点击取消
   */
  handleCancel() {
    this.isShow = false;
    if (this.mode === EMode.add) this.localValue.splice(this.localValue.length - 1, 1);
  }

  /**
   * 全部删除
   */
  handleClearAll() {
    this.localValue = [];
    this.isClearAll = true;
    this.handleValueChange();
  }

  /**
   * 将时间范围进行排序
   * @returns 升序后的值
   */
  handleSortTimeRange(): IProps['value'] {
    return this.localValue.sort((a, b) => {
      const time1 = +dayjs.tz(dayjs.tz().startOf('day').format(`YYYY-MM-DD ${a[0]}`)).format('x');
      const time2 = +dayjs.tz(dayjs.tz().startOf('day').format(`YYYY-MM-DD ${b[0]}`)).format('x');
      return time1 - time2;
    });
  }

  @Emit('change')
  handleValueChange() {
    if (this.autoSort) {
      this.localValue = this.handleSortTimeRange();
    }
    return deepClone(this.localValue);
  }

  /**
   * @param val 弹层显隐状态
   */
  handleTimePickerShow(val: boolean) {
    this.isShow = val;
    if (!val) {
      !this.isCustomTimeRange && this.handleSubmit();
      setTimeout(() => {
        this.isClearAll = false;
        this.isFocus = false;
      }, 200);
    } else {
      this.isCustomTimeRange = false;
    }
  }

  /**
   * 更新输入框的位置
   * @param insert 是否直接插入列表 新增时使用
   */
  handleMoveTrigger(insert = false) {
    if (insert) {
      this.timeRangeListRef.appendChild(this.triggerInputRef);
    } else {
      this.targetEl.append(this.triggerInputRef);
    }
    this.$nextTick(() => {
      this.triggerInputText = this.timeRange?.map?.(item => this.handleFormatTime(item))?.join('-');
      this.timePickerRef?.$refs?.drop?.update?.();
      this.inputFocus();
    });
  }

  /**
   * 格式化时间
   * @param time 'HH:mm:ss'的顺序
   */
  handleFormatTime(time: string) {
    if (!time) return;
    const timeList = time.split(':');
    const formatList = ['HH', 'mm', 'ss'];
    const timeMap = timeList.reduce((obj, time, index) => {
      const key = formatList[index];
      if (this.format.indexOf(key) > -1) {
        obj[key] = time;
      }
      return obj;
    }, {});
    return this.format.replace(TIME_FORMAT_REG, word => timeMap[word]);
  }

  /**
   * 解析自定义输入的时间范围
   * @param timeRagneStr 字符串 00:00-23:59
   * @returns TimeRange
   */
  parseTimeRangeStr(timeRagneStr: string): TimeRange {
    try {
      const timeRange = timeRagneStr.split('-');
      const startTime = timeRange[0];
      const endTime = timeRange[1];
      const fn = (timeStr: string, index: number): string => {
        const time = timeStr.split(':');
        const [hour = '00', min = '00', sec = index ? '59' : '00'] = time;
        const timeList = [hour, min, sec];
        return timeList.reduce((total, cur, index) => {
          const reg = index ? /^\d$|^[0-5]\d$/ : /^\d$|^[0-1]\d$|^[2][0-4]$/;
          if (!reg.test(cur)) throw Error('时间格式错误');
          return total.concat(`${cur.padStart(2, '0')}${index !== timeList.length - 1 ? ':' : ''}`);
        }, '');
      };
      return [startTime, endTime].map(fn) as TimeRange;
    } catch (error) {
      console.error(error);
      return null;
    }
  }

  /**
   * 处理自定义输入时间的失焦时间
   * @returns void
   */
  handleTimeRangeInputBlur() {
    this.isFocus = true;
    if (!this.isCustomTimeRange || !this.triggerInputText.length || !this.localValue.length) return;
    const customTimeRange = this.parseTimeRangeStr(this.triggerInputText);
    if (customTimeRange) {
      this.timeRange = customTimeRange;
      this.handleSubmit();
    } else {
      this.$bkMessage({
        message: this.$tc('时间格式错误'),
        theme: 'error',
      });
    }
  }
  /**
   * 自定义输入时间
   */
  handleTimeRangeInput() {
    this.isCustomTimeRange = true;
  }

  render() {
    return (
      <div
        class={['time-picker-multiple-wrap']}
        v-bk-tooltips={{
          placement: 'top',
          content: this.$t('暂无可选时间段'),
          // showOnInit: true,
          delay: 200,
          disabled: this.isAllowAdd,
        }}
        onClick={this.handleAddTimeRange}
      >
        <i class='icon-monitor icon-mc-time' />
        {
          <ul
            ref='timeRangeListRef'
            class='time-range-list'
          >
            {this.localValue.map((item, index) => (
              <li
                class={[
                  'time-range-item',
                  {
                    'no-empty-time': !this.isAllowAdd && index === this.localValue.length - 1,
                  },
                ]}
                onClick={modifiers.stop(evt => this.handleClickItem(evt, index))}
              >
                {!(this.currentIndex === index && this.isShow) && (
                  <span>
                    <span>{this.handleFormatTime(item[0])}</span>
                    <span>-</span>
                    <span>{this.handleFormatTime(item[1])}</span>
                  </span>
                )}
              </li>
            ))}
            <li
              ref='triggerInputRef'
              style={{ display: this.isShow ? '' : 'none' }}
              class={[
                'trigger-input-wrap',
                {
                  'hide-second': this.format === 'HH:mm',
                },
              ]}
              onClick={modifiers.stop(() => {})}
            >
              <bk-time-picker
                ref='timePickerRef'
                v-model={this.timeRange}
                ext-popover-cls='time-range-multiple-popover'
                open={this.isShow}
                type='timerange'
                allow-cross-day
                on-open-change={this.handleTimePickerShow}
              >
                <input
                  ref='inputRef'
                  class='trigger-input'
                  v-model={this.triggerInputText}
                  slot='trigger'
                  onBlur={this.handleTimeRangeInputBlur}
                  onFocus={() => (this.isFocus = true)}
                  onInput={this.handleTimeRangeInput}
                  onKeydown={modifiers.del(this.handleDelItem)}
                />
                {this.needHandle && (
                  <div
                    class='timerange-footer'
                    slot='footer'
                  >
                    <bk-button
                      size='small'
                      theme='primary'
                      onClick={modifiers.stop(this.handleSubmit)}
                    >
                      {this.$t('确认')}
                    </bk-button>
                    <bk-button
                      size='small'
                      onClick={modifiers.stop(this.handleCancel)}
                    >
                      {this.$t('取消')}
                    </bk-button>
                  </div>
                )}
              </bk-time-picker>
            </li>
          </ul>
        }
        {!this.localValue.length && !this.isShow && <span class='placeholder'>{this.placeholder}</span>}
        {!!this.localValue.length && (
          <i
            class='icon-monitor icon-mc-close-fill'
            onMousedown={modifiers.stop(this.handleClearAll)}
          />
        )}
      </div>
    );
  }
}
