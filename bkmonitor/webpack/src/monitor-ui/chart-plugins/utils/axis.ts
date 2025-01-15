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
 *
 * @param series 时序数据 series 数据
 * @returns 数据列中最大时间间隔
 */
export function getSeriesMaxInterval<T extends Array<{ datapoints: [number, number][] }>>(series: T) {
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxLength = 0;
  for (const s of series) {
    minX = Math.min(minX, +s.datapoints.at(0)?.[1]);
    maxX = Math.max(maxX, +s.datapoints.at(-1)?.[1]);
    maxLength = Math.max(maxLength, s.datapoints?.length);
  }
  return {
    maxXInterval: Math.abs(maxX - minX),
    maxSeriesCount: maxLength,
  };
}
/**
 *
 * @param maxXInterval 最大时间间隔
 * @param width 图表宽度
 * @returns 适配于 echarts 中X轴关于限制ticks的设置
 */
export function getTimeSeriesXInterval(maxXInterval: number, width: number, maxSeriesCount: number) {
  const splitNumber = width < 180 ? 2 : 4;
  if (!maxXInterval || !width || maxSeriesCount < 3)
    return {
      max: 'dataMax',
      min: 'dataMin',
      splitNumber: Math.min(maxSeriesCount < 3 ? maxSeriesCount : 4, splitNumber),
    };
  const hasDayAndHour = maxXInterval > 60 * 60 * 24 * 1000 && maxXInterval < 60 * 60 * 24 * 6000;
  const labelWidth = hasDayAndHour ? 180 : 80;
  const preInterval = Math.ceil(
    maxXInterval / Math.min(Math.min(maxSeriesCount || 9, 9), Math.ceil(width / labelWidth))
  );
  const interval = hasDayAndHour ? Math.max(preInterval, 60 * 60 * 24 * 1000) : preInterval;
  return {
    interval,
    minInterval: interval,
    splitNumber: Math.min(maxSeriesCount < 3 ? maxSeriesCount : 4, splitNumber),
    max: 'dataMax',
    min: 'dataMin',
  };
}
