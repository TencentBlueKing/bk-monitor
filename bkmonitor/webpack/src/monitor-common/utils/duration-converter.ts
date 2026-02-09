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

/**
 * 批量转换时长区间数组
 * @param durationData 时长数据数组
 * @returns 转换后的查询条件数组
 */
export function convertDurationArray(durationStr: string[]): Array<{
  condition: string;
  key: string;
  method: string;
  value: string[];
}> {
  const result = [];

  for (const item of durationStr) {
    const conditions = convertDurationToQueryCondition(item);
    result.push(...conditions);
  }

  return result;
}

/**
 * 将时长区间字符串转换为查询条件格式
 * @param durationStr 时长区间字符串，如 "<3600", "<=3600", ">=3600", ">86400", "[3600 TO 86400]"
 * @returns 查询条件对象数组
 */
export function convertDurationToQueryCondition(
  durationStr: string,
  key = 'duration'
): Array<{
  condition: string;
  key: string;
  method: string;
  value: string[];
}> {
  const conditions = [];

  if (durationStr.startsWith('<=')) {
    // 小于等于格式: "<=3600"
    const value = durationStr.substring(2);
    conditions.push({
      key,
      method: 'lte',
      value: [value],
    });
  } else if (durationStr.startsWith('<')) {
    // 小于格式: "<3600"
    const value = durationStr.substring(1);
    conditions.push({
      key,
      method: 'lt',
      value: [value],
    });
  } else if (durationStr.startsWith('>=')) {
    // 大于等于格式: ">=3600"
    const value = durationStr.substring(2);
    conditions.push({
      key,
      method: 'gte',
      value: [value],
    });
  } else if (durationStr.startsWith('>')) {
    // 大于格式: ">86400"
    const value = durationStr.substring(1);
    conditions.push({
      key,
      method: 'gt',
      value: [value],
    });
  } else if (durationStr.startsWith('[') && durationStr.includes(' TO ') && durationStr.endsWith(']')) {
    // 区间格式: "[3600 TO 86400]"
    const rangeMatch = durationStr.match(/\[(.*?) TO (.*?)\]/);
    if (rangeMatch && rangeMatch.length === 3) {
      const [_, lower, upper] = rangeMatch;
      conditions.push({
        key,
        method: 'gte',
        value: [lower],
      });
      conditions.push({
        key,
        method: 'lte',
        value: [upper],
      });
    }
  } else {
    // 默认处理，直接等于
    conditions.push({
      key,
      method: 'eq',
      value: [durationStr],
    });
  }

  return conditions;
}

// 使用示例
/*
const inputData = [
  {
    "id": "<3600",
    "name": "小于1h",
    "count": 49
  },
  {
    "id": "[3600 TO 86400]",
    "name": "大于1h且小于1d",
    "count": 6
  },
  {
    "id": ">86400",
    "name": "大于1d",
    "count": 0
  }
];
*/

// 输出结果示例：
/*
[
  { key: 'duration', method: 'lt', value: ['3600'], condition: 'and' },
  { key: 'duration', method: 'gte', value: ['3600'], condition: 'and' },
  { key: 'duration', method: 'lte', value: ['86400'], condition: 'and' },
  { key: 'duration', method: 'gt', value: ['86400'], condition: 'and' }
]
*/
