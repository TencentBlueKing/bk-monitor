/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { useTraceStore } from '../../store/modules/trace';

import type { ISpanListItem, ITraceListItem } from '../../typings';
import type { MonitorEchartOptions } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
// import { formatDuration } from '../trace-view/utils/date';

/** 耗时 interval */
export const DURATION_AVERAGE_COUNT = 40;

interface IChartItem {
  xAxis: string;
  yAxis: ITraceListItem[];
}

export class DurationDataModal {
  /** 满足chart的数据源 */
  chartData: IChartItem[] = [];
  /** 横坐标耗时步长 */
  durationStep = 0;
  /** 最大耗时 */
  maxDuration = 0;
  /** 最小耗时 */
  minDuration = 0;
  /** series值 */
  seriesData: any[] = [];
  sourceList: ISpanListItem[] | ITraceListItem[] = [];
  /** x轴数据 */
  xAxisData: string[] = [];

  constructor(list: ISpanListItem[] | ITraceListItem[]) {
    this.sourceList = list;
    this.initDate(list);
  }

  handleFilter(start: number, end: number) {
    const store = useTraceStore();
    if (start === this.minDuration && end === this.maxDuration) return [];

    return this.sourceList.filter(val => {
      const curVal = store.listType === 'trace' ? val.trace_duration : val.elapsed_time;
      return curVal >= start && curVal <= end;
    });
  }

  /** 初始化数据 */
  initDate(list: ISpanListItem[] | ITraceListItem[]) {
    const store = useTraceStore();
    const durationList = list.map(val => (store.listType === 'trace' ? val.trace_duration : val.elapsed_time)); // trace列表耗时集合数组
    this.minDuration = Math.min(...durationList); // 最小耗时
    this.maxDuration = Math.max(...durationList); // 最大耗时
    this.durationStep = Math.ceil((this.maxDuration - this.minDuration) / DURATION_AVERAGE_COUNT); // 耗时区间间隔

    let curVal = this.minDuration;
    while (curVal < this.maxDuration) {
      const start = curVal;
      const end = curVal + this.durationStep;
      const rangeData = list.filter(item => {
        const target = store.listType === 'trace' ? item.trace_duration : item.elapsed_time;
        return target >= start && target < end;
      });
      curVal = end;
      this.chartData.push({
        xAxis: [start, end].join('-'),
        yAxis: rangeData,
      });
    }

    this.xAxisData = this.chartData.map((val: IChartItem) => val.xAxis);
    this.seriesData = this.chartData.map((val: IChartItem) => (val.yAxis.length === 0 ? null : val.yAxis.length));
  }
}

export const BASE_BAR_OPTIONS: MonitorEchartOptions = {
  grid: {
    left: 0,
    right: 0,
  },
  xAxis: {
    show: false,
    data: [],
  },
  yAxis: {
    type: 'value',
    show: false,
  },
  tooltip: {
    show: true,
  },
  series: [],
};
