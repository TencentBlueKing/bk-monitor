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

/** 一天的毫秒时长 */
const ONE_DAY_TIME = 24 * 60 * 60 * 1000;

/**
 * 一天的日期数据
 */
export class Days {
  /** 当前时间 */
  currentTimestamp: number = null;
  /** 日期对象 */
  date: Date = null;
  /** 日期 */
  day: number = null;
  /** 月份 */
  month: number = null;
  /** 当前面板的月份 */
  panelMoth: number = null;
  /** 时间戳 */
  timestamp: number = null;
  /** 年份 */
  year: number = null;
  /**
   * @param timestamp 时间戳
   */
  constructor(timestamp: number) {
    this.initData(timestamp);
  }

  /** 是否为当月面板的日期 null 为没有归属的面板 boolean 为归属当前月的日期 */
  get currentMonthsDay(): boolean | null {
    return this.panelMoth === null ? null : this.month === this.panelMoth;
  }

  /** 当前日期 */
  get isToday() {
    const { year, month, day } = this.getYearMonthDay(this.currentTimestamp);
    return this.year === year && this.month === month && this.day === day;
  }

  /**
   * 获取指定时间戳的年、月、日数据
   * @param timestamp 时间戳
   */
  getYearMonthDay(timestamp: number): {
    day: number;
    month: number;
    year: number;
  } {
    const date = new Date(timestamp);
    const year = date.getFullYear();
    const month = date.getMonth();
    const day = date.getDate();
    return { year, month, day };
  }

  /** 初始化数据 */
  initData(timestamp: number) {
    this.date = new Date(timestamp);
    this.timestamp = timestamp;
    this.year = this.date.getFullYear();
    this.month = this.date.getMonth();
    this.day = this.date.getDate();
    this.currentTimestamp = +new Date();
  }
}

/**
 * 一个月的日期类
 */
export class MonthsPanel {
  /** 当前月面板需要展示的日期数据 */
  dateList: Days[] = [];
  /** 月份 0 - 11 */
  month: number = null;
  /** 选中的日期 */
  selectedDays: number[] = [];
  /** 时间戳 */
  timestamp: number = null;
  /** 年份 */
  year: number = null;
  /**
   *
   * @param year 年份
   * @param month 月份
   */
  constructor(timestamp: number) {
    this.initDate(timestamp);
  }
  /** 当月的某号 */
  get dateListNum() {
    return this.dateList.map(date => date.day);
  }
  /** 初始化数据 */
  initDate(timestamp: number) {
    this.timestamp = timestamp;
    const currentDate = new Date(timestamp);
    this.year = currentDate.getFullYear();
    this.month = currentDate.getMonth();
    /** 当月一号 */
    const firstOfMonth: Date = new Date(this.year, this.month, 1);
    /** 当月一号星期数 0 - 6 周日 - 周六 */
    const week = firstOfMonth.getDay();
    /** 日历开始日期 */
    const startDate = week === 0 ? firstOfMonth : new Date(+firstOfMonth - week * ONE_DAY_TIME);
    for (let i = 0; i < 42; i++) {
      const dateItem = +startDate + i * ONE_DAY_TIME;
      const days = new Days(dateItem);
      days.panelMoth = this.month;
      this.dateList.push(days);
    }
  }
}
