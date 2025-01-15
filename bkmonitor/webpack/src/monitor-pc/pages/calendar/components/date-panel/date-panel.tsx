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
import { Component, Emit, Model, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type Days, MonthsPanel } from './utils';

import './date-panel.scss';
/** 星期名称 */
const WEEKS_NAME_LIST = ['日', '一', '二', '三', '四', '五', '六'];

interface IProps {
  value?: number;
}
/**
 * 日期选择面板
 */
@Component
export default class DatePanel extends tsc<IProps> {
  @Model('change', { type: Number, default: +new Date() }) value: number;

  /** 本地值 */
  localValue = null;

  /** 本月数据实例 */
  months: MonthsPanel = null;

  /** 星期名称 */
  get weeksName(): string[] {
    return WEEKS_NAME_LIST.map(item => this.$tc(item));
  }

  created() {
    this.handleUpdateMonths();
  }

  @Watch('value')
  valueChange(val: number) {
    this.localValue = val;
  }

  /** 更新视图数据 */
  handleUpdateMonths() {
    this.months = new MonthsPanel(this.localValue || this.value);
  }
  /** 切换月份 */
  handleMonthChange(num: number) {
    let newMonth = this.months.month + num;
    let newYear = this.months.year;
    /** 上一年 */
    if (newMonth === -1) {
      newYear -= 1;
      newMonth = 11;
    } else if (newMonth === 12) {
      /** 下一年 */
      newYear += 1;
      newMonth = 0;
    }
    this.months = new MonthsPanel(+new Date(newYear, newMonth, 1));
  }

  /**
   * 点击选择日期
   * @param day 日期实例
   */
  handleSelectDate(day: Days) {
    this.handleDateChange(day);
    this.localValue = day.timestamp;
    this.months.selectedDays = [day.timestamp];
    // this.handleUpdateMonths()
  }

  @Emit('change')
  handleDateChange(day: Days) {
    return day.timestamp;
  }

  render() {
    return (
      <div class='date-panel-wrap'>
        <div class='date-panel-main'>
          <div class='date-panel-header'>
            <i
              class='icon-monitor icon-arrow-left icon-left'
              onClick={() => this.handleMonthChange(-1)}
            />
            <span class='header-text'>{`${this.months.year}年${this.months.month + 1}月`}</span>
            <i
              class='icon-monitor icon-arrow-right icon-right'
              onClick={() => this.handleMonthChange(1)}
            />
          </div>
          <div class='date-row'>
            {this.weeksName.map(item => (
              <span class='date-cell'>{item}</span>
            ))}
          </div>
          {new Array(6).fill(null).map((item, rowIndex) => (
            <div class='date-row date-num'>
              {new Array(7).fill(null).map((item, cellIndex) => {
                const day = this.months.dateList[rowIndex * 7 + cellIndex];
                return (
                  <span
                    class={[
                      'date-cell',
                      {
                        'not-this-month': !(day.currentMonthsDay ?? true),
                        'is-today': day.isToday,
                        selected: this.months.selectedDays.includes(day.timestamp),
                      },
                    ]}
                    onClick={() => this.handleSelectDate(day)}
                  >
                    <span class='date-cell-text'>{day.day}</span>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    );
  }
}
