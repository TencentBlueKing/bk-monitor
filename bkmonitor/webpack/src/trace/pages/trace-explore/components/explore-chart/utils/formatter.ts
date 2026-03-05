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

import type { ValueFormatter } from '../types';

/**
 * @method handleGetMinPrecision 获取数据的最小精度
 * @param {number[]} data 数据数组
 * @param {ValueFormatter} formatter 数值格式化函数
 * @param {string} unit 单位
 * @returns {number} 最小精度
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
