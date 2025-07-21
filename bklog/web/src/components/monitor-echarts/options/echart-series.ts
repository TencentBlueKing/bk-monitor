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

import { ILegendItem, ChartType } from './type-interface';
export default class EchartsSeries {
  public chartType: Partial<ChartType>;
  public series = [];
  public colors = [];
  public constructor(chartType: ChartType, seriesData = [], colors = []) {
    this.chartType = chartType;
    this.series = seriesData;
    this.colors = colors;
  }

  public getSeriesOption(plotBands = [], thresholdLine = []) {
    const hasPlotBand = Array.isArray(plotBands) && plotBands.length > 0;
    const legendData: ILegendItem[] = [];
    const series = this.series.map((item: any, index) => {
      let showSymbol = hasPlotBand;
      const legendItem: ILegendItem = {
        avg: 0,
        color: this.colors[index % this.colors.length],
        max: 0,
        min: 0,
        name: String(item.name),
        show: true,
        total: 0,
      };
      item.data.forEach((seriesItem: any, seriesIndex: number) => {
        if (seriesItem?.length && seriesItem[1]) {
          const pre = item.data[seriesIndex - 1];
          const next = item.data[seriesIndex + 1];
          const curValue = +seriesItem[1];
          legendItem.max = Math.max(legendItem.max, curValue);
          legendItem.min = Math.min(+legendItem.min, curValue);
          legendItem.total = legendItem.total + curValue;
          if (
            hasPlotBand &&
            plotBands.some((set: any) => set.from === seriesItem[0])
          ) {
            item.data[seriesIndex] = {
              itemStyle: {
                borderWidth: 6,
                enabled: true,
                opacity: 1,
                shadowBlur: 0,
              },
              label: {
                show: false,
              },
              symbolSize: 12,
              value: [seriesItem[0], seriesItem[1]],
            };
          } else {
            const hasBrother =
              pre && next && pre.length && next.length && !pre[1] && !next[1];
            item.data[seriesIndex] = {
              itemStyle: {
                borderWidth: hasBrother ? 4 : 1,
                enabled: true,
                opacity: 1,
                shadowBlur: 0,
              },
              symbolSize: hasBrother ? 4 : 1,
              value: [seriesItem[0], seriesItem[1]],
            };
          }
        } else if (seriesItem.symbolSize) {
          showSymbol = true;
        }
      });
      legendItem.avg = +(legendItem.total / item.data.length).toFixed(2);
      legendItem.total = +legendItem.total.toFixed(2);
      const seriesItem = {
        ...item,
        showSymbol,
        smooth: 0.2,
        symbol: 'circle',
        type: this.chartType,
        z: 4,
      };
      if (thresholdLine?.length) {
        seriesItem.markLine = this.handleSetThresholdLine(thresholdLine);
      }
      if (plotBands?.length) {
        seriesItem.markArea = this.handleSetThresholdBand(plotBands);
      }
      legendData.push(legendItem);
      return seriesItem;
    });
    return { legendData, series };
  }
  // 设置阈值线
  public handleSetThresholdLine(
    thresholdLine: { value: number; name: string }[]
  ) {
    return {
      data: thresholdLine.map((item) => ({
        name: item.name,
        yAxis: item.value,
      })),
      label: {
        position: 'insideStartTop',
        show: true,
      },
      lineStyle: {
        color: '#FD9C9C',
        distance: 3,
        type: 'dashed',
        width: 1,
      },
      symbol: [],
    };
  }
  // 设置阈值面板
  public handleSetThresholdBand(plotBands: { to: number; from: number }[]) {
    return {
      data: plotBands.map((item) => [
        {
          xAxis: item.from,
          yAxis: 0,
        },
        {
          xAxis: item.to || 'max',
          yAxis: 'max', // this.delegateGet('getModel').getComponent('yAxis').axis.scale._extent[1]
        },
      ]),
      itemStyle: {
        borderColor: '#FFE9D5',
        borderWidth: 1,
        color: '#FFF5EC',
        shadowBlur: 0,
        shadowColor: '#FFF5EC',
      },
      opacity: 0.1,
      show: true,
      silent: true,
    };
  }
}
