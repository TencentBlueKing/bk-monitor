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

import dayjs from 'dayjs';

import { EPreDateType } from './utils';

import './compare-time.scss';

const preDateTypeList = [
  {
    label: window.i18n.t('昨天'),
    value: EPreDateType.yesterday,
  },
  {
    label: window.i18n.t('上周'),
    value: EPreDateType.lastWeek,
  },
];

interface IProps {
  value?: string[];
  onChange?: (value: string[]) => void;
}

function timeOffsetDateFormat(t: string) {
  if (preDateTypeList.map(item => item.value).includes(t as any)) {
    return t;
  }
  const regex = /^(\d+)d$/; // 匹配类似 '1d', '10d' 的格式
  const match = t.match(regex);
  if (match) {
    const days = Number.parseInt(match[1], 10); // 提取天数
    const targetDate = dayjs().subtract(days, 'day'); // 当前日期减去天数
    return targetDate.format('YYYY-MM-DD'); // 格式化为 YYYY-MM-DD
  }
  return t;
}

function timeShiftFormat(t: string) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (regex.test(t)) {
    return `${dayjs().diff(dayjs(t), 'day')}d`;
  }
  return t;
}

@Component
export default class CompareTime extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: string[];

  localValue = [];
  /* 预设日期 */
  checkboxGroupValue = [];
  /* 日期选择器时间 */
  initDateTime = '';
  /* 是否显示时间选择器 */
  isShowPicker = false;
  /* 日期选择器禁用配置 */
  pickerOptions = {
    disabledDate: this.setDisabledDate,
  };
  /* 日期选择器展开状态 */
  datePickOpen = false;
  /* 自定义日期tag */
  dateTime = [];
  timeOffset = [];

  get isChooseDateOrType() {
    return this.checkboxGroupValue.length === 1 && this.dateTime.length === 1;
  }
  get isDateAdd() {
    return this.checkboxGroupValue.length === 2 || this.dateTime.length === 2 || this.isChooseDateOrType;
  }

  @Watch('value', { immediate: true })
  handleWatchValue(value) {
    if (JSON.stringify(value) !== JSON.stringify(this.timeOffset)) {
      this.timeOffset = value;
      const localValue: any[] = this.timeOffset.map(item => timeOffsetDateFormat(item));
      this.localValue = localValue;
      const typeList = preDateTypeList.map(item => item.value);
      const checkboxGroupValue = [];
      const dateTime = [];
      for (const item of localValue) {
        if (typeList.includes(item)) {
          checkboxGroupValue.push(item);
        } else {
          dateTime.push(item);
        }
      }
      this.checkboxGroupValue = checkboxGroupValue;
      this.dateTime = dateTime;
    }
  }

  @Emit('change')
  handleChange() {
    const result = [];
    for (const item of this.checkboxGroupValue) {
      result.push(item);
    }
    for (const item of this.dateTime) {
      result.push(item);
    }
    this.localValue = result;
    this.timeOffset = result.map(item => timeShiftFormat(item));
    return this.timeOffset;
  }
  /**
   * @description 展开日期选择器
   */
  handleAdd() {
    if (!this.isDateAdd) {
      this.isShowPicker = !this.isShowPicker;
      this.initDateTime = '';
      this.$nextTick(() => {
        this.datePickOpen = true;
      });
    }
  }
  /**
   * @description 删除自定义日期
   * @param item
   */
  handleClose(item) {
    this.dateTime = this.dateTime.filter(date => date !== item);
    this.handleChange();
  }
  /** 设置日历组件禁用时间 */
  setDisabledDate(date) {
    const preDateStr = preDateTypeList.map(item => item.value);
    const preSelects = [];
    for (const item of this.localValue) {
      if (preDateStr.includes(item)) {
        preSelects.push(item);
      }
    }
    const dayDate = dayjs(date);
    let diffDay = `${dayjs().diff(dayDate, 'day')}d`;
    diffDay = diffDay === '7d' ? EPreDateType.lastWeek : diffDay;
    return (
      (date && date.valueOf() > Date.now()) ||
      this.localValue.includes(diffDay) ||
      this.localValue.includes(dayDate.format('YYYY-MM-DD'))
    );
  }

  disabledCheck(key) {
    if (this.dateTime.length === 2) {
      return true;
    }
    if (this.isChooseDateOrType) {
      return !this.checkboxGroupValue.includes(key);
    }
    return false;
  }

  handleFormateDate() {
    const dateArr = [];
    this.dateTime.map(item => dateArr.push({ label: item, value: item }));
    return dateArr;
  }

  /* 日期选择器选择 */
  changePicker(date) {
    this.isShowPicker = false;
    let dayDiff = `${dayjs().diff(dayjs(date), 'day')}d`;
    dayDiff = dayDiff === '7d' ? EPreDateType.lastWeek : dayDiff;
    const preDateStr = preDateTypeList.map(item => item.value);
    if (preDateStr.includes(dayDiff as any)) {
      if (!this.checkboxGroupValue.includes(dayDiff)) {
        this.checkboxGroupValue.push(dayDiff);
      }
    } else {
      date && this.dateTime.push(date);
    }
    this.handleChange();
  }

  /* 选择预设日期 */
  handleCheckboxChange() {
    this.isShowPicker = false;
    this.handleChange();
  }
  /**
   * @description 日期选择器展开
   * @param state
   */
  handleOpenChange(state) {
    this.datePickOpen = state;
  }

  render() {
    return (
      <div class='group-compare-select___compare-time'>
        <bk-checkbox-group
          class='contrast-view-checkbox-group'
          v-model={this.checkboxGroupValue}
          onChange={this.handleCheckboxChange}
        >
          {preDateTypeList.map(item => (
            <bk-checkbox
              key={item.value}
              v-bk-tooltips={{
                disabled: !this.isDateAdd || !this.disabledCheck(item.value),
                content: this.$t('最多选择不超过两个日期'),
              }}
              disabled={this.disabledCheck(item.value)}
              label={item.value}
            >
              {item.label}
              {/* {this.checkboxGroupValue.includes(item.value) && (
                <span class='time-tips'>{this.timeStrShow[item.value]}</span>
              )} */}
            </bk-checkbox>
          ))}
        </bk-checkbox-group>
        <div class='contrast-custom'>
          <span class='custom-title'>{this.$t('自定义日期')}</span>
          {this.dateTime.map(
            item =>
              !!item && (
                <bk-tag
                  key={item}
                  closable
                  onClose={() => this.handleClose(item)}
                >
                  {item}
                </bk-tag>
              )
          )}
          {!this.isShowPicker ? (
            <span
              class={['contrast-custom-add', { disabled: this.isDateAdd }]}
              v-bk-tooltips={{
                disabled: !this.isDateAdd,
                content: this.$t('最多选择不超过两个日期'),
              }}
              onClick={this.handleAdd}
            >
              <i class='icon-monitor icon-plus-line' />
            </span>
          ) : undefined}
          {this.isShowPicker && (
            <bk-date-picker
              class='custom-date-picker'
              v-model={this.initDateTime}
              behavior='simplicity'
              open={this.datePickOpen}
              options={this.pickerOptions}
              transfer={true}
              on-open-change={this.handleOpenChange}
              onChange={this.changePicker}
            />
          )}
        </div>
      </div>
    );
  }
}
