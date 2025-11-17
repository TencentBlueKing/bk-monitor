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

import type { IChartOptionPorps, ChartType } from './type-interface';
export default class EchartsSeries {
  public lineWidth = 1;
  public chartType: ChartType;
  public colors: string[] = [];
  public showExtremum = false;
  public chartOption = {};
  public constructor({ chartType, colors, showExtremum, chartOption, lineWidth }: IChartOptionPorps) {
    this.chartType = chartType;
    this.colors = colors;
    this.showExtremum = showExtremum;
    this.chartOption = chartOption;
    this.lineWidth = lineWidth || 1;
  }

  // 设置x轴label formatter方法
  public handleSetFormatterFunc(seriesData: any, map?: Map<number, string[]>) {
    const minX = Array.isArray(seriesData[0]) ? seriesData[0][0] : seriesData[0].x;
    const [maxX] = seriesData.at(-1);
    if (minX && maxX) {
      return (v: any) => this.formatTimeStamp(v, minX, maxX, map);
    }
    return null;
  }

  public overwriteMerge(_destinationArray: any, sourceArray: any) {
    return sourceArray;
  }
  public handleYxisLabelFormatter(num: number): string {
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
  private formatTimeStamp(v: any, minX: any, maxX: any, map?: Map<number, string[]>) {
    // 用绝对值兼容倒叙的情况
    const duration = Math.abs(dayjs.duration(dayjs(maxX).diff(dayjs(minX))).asSeconds());
    const stringValue = map?.get(v)?.[1];
    if (duration < 60 * 60 * 24) {
      if (duration < 60 * 5) {
        return stringValue ?? dayjs.tz(v).format('HH:mm:ss').replace(/:00$/, '');
      }

      return dayjs.tz(v).format('HH:mm:ss').replace(/:00$/, '');
    }
    if (duration < 60 * 60 * 24 * 2) {
      return dayjs.tz(v).format('HH:mm:ss').replace(/:00$/, '');
    }
    if (duration < 60 * 60 * 24 * 8) {
      return dayjs.tz(v).format('MM-DD HH:mm:ss').replace(/:00$/, '');
    }
    if (duration <= 60 * 60 * 24 * 30 * 12) {
      return dayjs.tz(v).format('MM-DD');
    }
    return dayjs.tz(v).format('YYYY-MM-DD');
  }
}
