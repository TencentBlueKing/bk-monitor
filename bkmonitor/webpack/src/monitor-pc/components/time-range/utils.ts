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
import { DateRange } from '@blueking/date-picker/vue2';
import dayjs from 'dayjs';

import type { TimeRangeType } from './time-range';
/** 相对时间范围格式正则 */
export const CUSTOM_TIME_RANGE_REG = /^now(([-+])(\d+)([m|h|d|w|M|y|Y]))?(\/[m|h|d|w|M|y|Y|fy])?/;

type TimestampsType = [number, number];

/** 处理时间范围的对象 */
export class TimeRange {
  dateRange: DateRange = null;
  /** 实例化的时间范围对象 */
  value: dayjs.Dayjs[] = [];
  constructor(times: TimeRangeType) {
    this.init(times);
  }

  /** 格式化时间范围 */
  format(str = 'YYYY-MM-DD HH:mm:ssZZ'): TimeRangeType {
    return this.value.map(item => item?.format?.(str) || null) as TimeRangeType;
  }

  /** 初始化时间对象 */
  init(times: TimeRangeType) {
    this.dateRange = new DateRange(times, 'YYYY-MM-DD HH:mm:ssZZ', window.timezone);
    this.value = [this.dateRange.startDate, this.dateRange.endDate];
  }
  /** 格式化成秒 */
  unix(): TimestampsType {
    return this.value.map(item => item?.unix?.() || null) as TimestampsType;
  }
}

/** 字符串的时间戳(毫秒)转为数字类型 */
export const intTimestampStr = (str): null | number => {
  const isTimestamp = /^\d{1}$|^([1-9]\d{1,12})$/.test(str);
  return isTimestamp ? Number.parseInt(str, 10) : str;
};

/** 将格式为 ['now-1d', 'now'] 转换为 ['YYYY-MM-DD HH:mm:ssZZ', 'YYYY-MM-DD HH:mm:ssZZ'] */
export const handleTransformTime = (value: TimeRangeType): TimeRangeType => {
  const timeRange = new TimeRange(value);
  return timeRange.format('YYYY-MM-DD HH:mm:ssZZ');
};

/** 转换成秒 */

export const handleTransformToTimestamp = (value: TimeRangeType): TimestampsType => {
  const timeRange = new TimeRange(value);
  return timeRange.unix();
};

/* 秒转换为字符串时间 */
export function timestampTransformStr(value: number[]): TimeRangeType {
  return value.map(v => {
    if (String(v).length > 10) {
      return dayjs(Number(v)).format('YYYY-MM-DD HH:mm:ssZZ');
    }
    return dayjs(Number(v) * 1000).format('YYYY-MM-DD HH:mm:ssZZ');
  }) as TimeRangeType;
}

/** 时间区间快捷选项 */
export const shortcuts = [
  {
    text: window.i18n.t('近{n}分钟', { n: 5 }),
    value: ['now-5m', 'now'],
  },
  {
    text: window.i18n.t('近{n}分钟', { n: 15 }),
    value: ['now-15m', 'now'],
  },
  {
    text: window.i18n.t('近{n}分钟', { n: 30 }),
    value: ['now-30m', 'now'],
  },
  {
    text: window.i18n.t('近{n}小时', { n: 1 }),
    value: ['now-1h', 'now'],
  },
  {
    text: window.i18n.t('近{n}小时', { n: 3 }),
    value: ['now-3h', 'now'],
  },
  {
    text: window.i18n.t('近{n}小时', { n: 6 }),
    value: ['now-6h', 'now'],
  },
  {
    text: window.i18n.t('近{n}小时', { n: 12 }),
    value: ['now-12h', 'now'],
  },
  {
    text: window.i18n.t('近{n}小时', { n: 24 }),
    value: ['now-24h', 'now'],
  },
  {
    text: window.i18n.t('近 {n} 天', { n: 2 }),
    value: ['now-2d', 'now'],
  },
  {
    text: window.i18n.t('近 {n} 天', { n: 7 }),
    value: ['now-7d', 'now'],
  },
  {
    text: window.i18n.t('近 {n} 天', { n: 30 }),
    value: ['now-30d', 'now'],
  },
  {
    text: window.i18n.t('今天'),
    value: ['now/d', 'now/d'],
  },
  {
    text: window.i18n.t('昨天'),
    value: ['now-1d/d', 'now-1d/d'],
  },
  {
    text: window.i18n.t('前天'),
    value: ['now-2d/d', 'now-2d/d'],
  },
  {
    text: window.i18n.t('本周'),
    value: ['now/w', 'now/w'],
  },
];

// 生成 formatterFunc 函数
export const generateFormatterFunc = value => {
  const [start, end] = handleTransformToTimestamp(value);
  return timestamp => {
    const duration = end - start;
    const time = dayjs(timestamp);

    if (duration < 60) {
      return time.format('mm:ss');
    }
    if (duration < 60 * 60) {
      return time.format('HH:mm:ss');
    }
    if (duration <= 60 * 60 * 24) {
      return time.format('HH:mm');
    }
    if (duration < 60 * 60 * 24 * 7) {
      return time.format('MM-DD HH:mm');
    }
    if (duration < 60 * 60 * 24 * 30) {
      return time.format('MM-DD');
    }
    return time.format('MM-DD');
  };
};

/** 默认的时间范围：近一小时 */
export const DEFAULT_TIME_RANGE: TimeRangeType = ['now-1h', 'now'];

/*  */
export const getTimeDisplay = timeRange => {
  return new DateRange(timeRange, 'YYYY-MM-DD HH:mm:ssZZ', window.timezone).toDisplayString();
};

export const getDateRange = timeRange => {
  return new DateRange(timeRange, 'YYYY-MM-DD HH:mm:ssZZ', window.timezone);
};
