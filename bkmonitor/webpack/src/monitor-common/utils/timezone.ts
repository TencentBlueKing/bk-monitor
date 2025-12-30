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
import dayjs from 'dayjs';
import tz from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
dayjs.extend(tz);
dayjs.extend(utc);

/**
 * @description 获取时区
 * @returns {string} 时区
 */
export const getTimezone = () => {
  return getDefaultTimezone();
};

/**
 * @description 解析时间戳
 * @param {number | string} ts 时间戳
 * @returns {number} 解析后的时间戳
 */
export const parseTimestamp = (ts: number | string) => {
  try {
    const n = Number(ts);
    const len = ts.toString().length;

    if (len === 10) return n * 1000; // 秒
    if (len === 13) return n; // 毫秒
    if (len === 16) return Math.floor(n / 1000); // 微秒
    if (len === 19) return Math.floor(n / 1e6); // 纳秒
    return +n.toString().padEnd(13, '0');
  } catch {
    return ts;
  }
};

/**
 * @description 格式化时间戳
 * @param {Date | number | string} date 时间戳
 * @param {string} format 格式
 * @returns {string} 格式化后的时间戳
 */
export const formatWithTimezone = (date: Date | number | string, format?: string) => {
  try {
    if (!date || !dayjs(date).isValid()) return date;
    const timezone = getDefaultTimezone();
    let formatString = format || 'YYYY-MM-DD HH:mm:ssZZ';

    if (!/ZZ$/.test(formatString)) {
      formatString += 'ZZ';
    }

    // 如果是 ISO 8601 格式字符串（以 Z 结尾），先解析为 UTC，再转换到目标时区
    if (typeof date === 'string' && date.endsWith('Z')) {
      return dayjs.utc(date).tz(timezone).format(formatString);
    }
    if (date instanceof Date) {
      return dayjs(date).tz(timezone).format(formatString);
    }
    // 其他格式直接解析并转换时区
    return dayjs(!Number.isNaN(Number(date)) ? parseTimestamp(date) : date)
      .tz(timezone)
      .format(formatString);
  } catch {
    return date;
  }
};
