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
import dayjs from 'dayjs';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { ValueFormatter } from 'monitor-ui/monitor-echarts/valueFormats';

interface NestedObject<T = unknown> {
  [key: string]: NestedObject<T> | T;
}
export const typeEnums = {
  '1h': window.i18n.tc('1小时前'),
  '1d': window.i18n.tc('1天前'),
  '7d': window.i18n.tc('7天前'),
  '30d': window.i18n.tc('30天前'),
  current: window.i18n.tc('当前'),
};
export const refreshList = [
  // 刷新间隔列表
  {
    name: 'off',
    id: -1,
  },
  {
    name: '1m',
    id: 60 * 1000,
  },
  {
    name: '5m',
    id: 5 * 60 * 1000,
  },
  {
    name: '15m',
    id: 15 * 60 * 1000,
  },
  {
    name: '30m',
    id: 30 * 60 * 1000,
  },
  {
    name: '1h',
    id: 60 * 60 * 1000,
  },
  {
    name: '2h',
    id: 60 * 2 * 60 * 1000,
  },
  {
    name: '1d',
    id: 60 * 24 * 60 * 1000,
  },
];

export function getNumberAndUnit(str) {
  const match = str.match(/^(\d+)([a-zA-Z])$/);
  return match ? { number: Number.parseInt(match[1], 10), unit: match[2] } : null;
}

// 设置x轴label formatter方法
export function handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
  let formatterFunc = null;
  const [firstItem] = seriesData;
  const lastItem = seriesData[seriesData.length - 1];
  const val = new Date('2010-01-01').getTime();
  const getXVal = (timeVal: any) => {
    if (!timeVal) return timeVal;
    return timeVal[0] > val ? timeVal[0] : timeVal[1];
  };
  const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
  const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);
  minX &&
    maxX &&
    // biome-ignore lint/suspicious/noAssignInExpressions: <explanation>
    (formatterFunc = (v: any) => {
      const duration = Math.abs(dayjs.tz(maxX).diff(dayjs.tz(minX), 'second'));
      if (onlyBeginEnd && v > minX && v < maxX) {
        return '';
      }
      if (duration < 1 * 60) {
        return dayjs.tz(v).format('mm:ss');
      }
      if (duration < 60 * 60 * 24 * 1) {
        return dayjs.tz(v).format('HH:mm');
      }
      if (duration < 60 * 60 * 24 * 6) {
        return dayjs.tz(v).format('MM-DD HH:mm');
      }
      if (duration <= 60 * 60 * 24 * 30 * 12) {
        return dayjs.tz(v).format('MM-DD');
      }
      return dayjs.tz(v).format('YYYY-MM-DD');
    });
  return formatterFunc;
}
/** 处理时间对比时线条名字 */
export function handleTimeOffset(timeOffset: string) {
  const match = timeOffset.match(/(current|(\d+)([hdwM]))/);
  if (match) {
    const [target, , num, type] = match;
    const map = {
      d: window.i18n.tc('{n} 天前', { n: num }),
      w: window.i18n.tc('{n} 周前', { n: num }),
      M: window.i18n.tc('{n} 月前', { n: num }),
      current: window.i18n.tc('当前'),
    };
    return map[type || target];
  }
  return timeOffset;
}

// 转换time_shift显示
export function handleTransformTimeShift(val: string) {
  const timeMatch = val.match(/(-?\d+)(\w+)/);
  const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
  const hasMatch = timeMatch && timeMatch.length > 2;
  if (dateRegex.test(val)) {
    return val;
  }
  if (val === '1d') {
    return window.i18n.tc('昨天');
  }
  if (val === '1w') {
    return window.i18n.tc('上周');
  }
  return hasMatch
    ? (dayjs() as any).add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
    : val.replace('current', window.i18n.tc('当前'));
}
/**
 * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
 * @param {number} num
 * @return {*}
 */
export function handleYAxisLabelFormatter(num: number): string {
  const si = [
    { value: 1, symbol: '' },
    { value: 1e3, symbol: 'K' },
    { value: 1e6, symbol: 'M' },
    { value: 1e9, symbol: 'G' },
    { value: 1e12, symbol: 'T' },
    { value: 1e15, symbol: 'P' },
    { value: 1e18, symbol: 'E' },
  ];
  const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
  let i: number;
  for (i = si.length - 1; i > 0; i--) {
    if (num >= si[i].value) {
      break;
    }
  }
  return (num / si[i].value).toFixed(3).replace(rx, '$1') + si[i].symbol;
}
export function timeToDayNum(t) {
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (regex.test(t)) {
    return dayjs().diff(dayjs(t), 'day');
  }
  const timeInfo = getNumberAndUnit(t);
  if (timeInfo?.unit === 'd') {
    return timeInfo.number;
  }
  if (timeInfo?.unit === 'w') {
    return timeInfo.number * 7;
  }
  return 0;
}

export const chunkArray = <T extends any[]>(array: T, chunkSize: number): T[] => {
  const result = []; // 存储结果的二维数组

  // 循环处理每个分块
  for (let i = 0; i < array.length; i += chunkSize) {
    // 使用slice截取当前分块
    const chunk = array.slice(i, i + chunkSize);
    result.push(chunk);
  }

  return result;
};

// 处理时间范围字符串
export const generateTimeStrings = (tipsKey: string, timeRange: TimeRangeType) => {
  const formatStr = 'MM-DD HH:mm:ss';
  const [startTime, endTime] = handleTransformToTimestamp(timeRange);
  const timeDiffs = {
    '1h': 3600000,
    '1d': 86400000,
    '7d': 7 * 86400000,
    '30d': 30 * 86400000,
  };
  const diff = timeDiffs[tipsKey];
  const start = startTime * 1000 - diff;
  const end = endTime * 1000;
  const year = new Date(start).getFullYear();
  return `${year}（${dayjs(start).format(formatStr)} ~ ${dayjs(end).format(formatStr)}）`;
};

/**
 * @description: 设置精确度
 * @param {number} data
 * @param {ValueFormatter} formatter
 * @param {string} unit
 * @return {*}
 */
export const handleGetMinPrecision = (data: number[], formatter: ValueFormatter, unit: string) => {
  if (!data || data.length === 0) {
    return 0;
  }
  data.sort((a, b) => a - b);
  const len = data.length;
  if (data[0] === data[len - 1]) {
    if (['none', ''].includes(unit) && !data[0].toString().includes('.')) return 0;
    const setList = String(data[0]).split('.');
    return !setList || setList.length < 2 ? 2 : setList[1].length;
  }
  let precision = 0;
  let sampling = [];
  const middle = Math.ceil(len / 2);
  sampling.push(data[0]);
  sampling.push(data[Math.ceil(middle / 2)]);
  sampling.push(data[middle]);
  sampling.push(data[middle + Math.floor((len - middle) / 2)]);
  sampling.push(data[len - 1]);
  sampling = Array.from(new Set(sampling.filter(n => n !== undefined)));
  while (precision < 5) {
    const samp = sampling.reduce((pre, cur) => {
      pre[Number(formatter(cur, precision).text)] = 1;
      return pre;
    }, {});
    if (Object.keys(samp).length >= sampling.length) {
      return precision;
    }
    precision += 1;
  }
  return precision;
};

/**
 * @description: 格式化tooltips展示的内容
 * @param {string} name  指标名
 * @param {string} alias  指标别名
 * */
export const formatTipsContent = (name: string, alias: string) => {
  return `${window.i18n.tc('指标名：')}${name || '--'} <br/> ${window.i18n.tc('指标别名：')}${alias || '--'}`;
};

export const optimizedDeepEqual = (obj1: NestedObject, obj2: NestedObject) => {
  // 处理特殊情况：非对象或 null
  if (obj1 === obj2) return true;
  if (typeof obj1 !== 'object' || obj1 === null || typeof obj2 !== 'object' || obj2 === null) return false;

  // 排序键名（确保键顺序不影响比较）
  const sortKeys = obj =>
    Object.fromEntries(
      Object.keys(obj)
        .sort()
        .map(key => [key, obj[key]])
    );

  // 转为字符串并比较（忽略空格，处理数组和嵌套对象）
  const str1 = JSON.stringify(sortKeys(obj1));
  const str2 = JSON.stringify(sortKeys(obj2));

  return str1 === str2;
};
