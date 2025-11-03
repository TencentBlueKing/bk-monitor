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

import deepMerge from 'deepmerge';

import MonitorBaseSeries from './base-chart-option';
import { pieOptions } from './echart-options-config';

import type { ILegendItem, IChartInstance } from './type-interface';
export default class MonitorPieSeries extends MonitorBaseSeries implements IChartInstance {
  public defaultOption: any;
  public constructor(props: any) {
    super(props);
    this.defaultOption = deepMerge(
      deepMerge(
        pieOptions,
        {
          color: this.colors,
        },
        { arrayMerge: this.overwriteMerge },
      ),
      this.chartOption,
      { arrayMerge: this.overwriteMerge },
    );
  }
  public getOptions(data: any, otherOptions = {}) {
    let { series } = data || {};
    series = deepMerge([], series);
    const hasSeries = series && series.length > 0;
    const legendData: any = [];
    const options = {
      series: hasSeries
        ? series.map((item: any, index: number) => {
            for (const seriesItem of item.data) {
              const legendItem: ILegendItem = {
                name: '',
                max: 0,
                min: 0,
                avg: 0,
                total: 0,
                color: this.colors[index % this.colors.length],
                show: true,
              };
              if (seriesItem?.name) {
                const curValue = +seriesItem.value;
                legendItem.max = Math.max(legendItem.max, curValue);
                legendItem.min = Math.min(+legendItem.min, curValue);
                legendItem.total += curValue;
                legendItem.name = seriesItem.name;
              }
              legendItem.avg = +(legendItem.total / 1).toFixed(2);
              legendItem.total = +legendItem.total.toFixed(2);
              legendItem.name && legendData.push(legendItem);
            }
            const seriesItem = {
              radius: ['50%', '70%'],
              avoidLabelOverlap: false,
              label: {
                show: false,
                position: 'center',
              },
              labelLine: {
                show: false,
              },
              type: this.chartType,
              ...item,
            };
            return seriesItem;
          })
        : [],
    };
    return {
      options: deepMerge(deepMerge(this.defaultOption, otherOptions, { arrayMerge: this.overwriteMerge }), options, {
        arrayMerge: this.overwriteMerge,
      }),
      legendData,
    };
  }
}
