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

/**
 * 日志下载进度计算工具
 * 根据接口返回的真实条数计算进度
 */

/** 单位数组 */
const UNITS = ['', 'K', 'M', 'G'];

/**
 * 计算百分比进度
 *
 * @param exportedCount - 当前已下载条数
 * @param totalCount - 总条数
 * @returns 百分比整数（0-100）
 */
export function calculateProgressPercent(exportedCount: number, totalCount: number) {
  if (!totalCount || totalCount <= 0) return 0;
  return Math.floor((exportedCount / totalCount) * 100);
}

/**
 * 数字格式化（K/M/G）
 * 供使用方组装显示文本时使用
 *
 * @param num - 要格式化的数字
 * @returns 格式化后的字符串，如 "567M"
 */
export function formatNumber(num: number | null | undefined) {
  if (num === undefined || num === null) return '--';

  let unitIndex = 0;
  let value = num;

  while (value >= 1000 && unitIndex < UNITS.length - 1) {
    value /= 1000;
    unitIndex += 1;
  }

  value = Number(value.toFixed(1));

  // 四舍五入后达到1000，则升级单位
  if (value >= 1000 && unitIndex < UNITS.length - 1) {
    value = 1;
    unitIndex += 1;
  }

  return `${value}${UNITS[unitIndex]}`;
}
