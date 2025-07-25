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
import { ofType } from 'vue-tsx-support';

import MonitorCharts from './monitor-echarts-new.vue';

import type {
  ChartType,
  IStatusChartOption,
  IStatusSeries,
  ITextChartOption,
  ITextSeries,
} from './options/type-interface';
import type { MonitorEchartOptions, MonitorEchartSeries } from './types/monitor-echarts';

interface IAlarmStatus {
  alert_number: number;
  status: number;
  strategy_number: number;
}
interface IMonitorEchartsProps {
  autoresize: boolean;
  // 背景图
  backgroundUrl: string;
  // 图表类型
  chartType: ChartType;
  // 图标系列颜色集合
  colors: string[];
  emptyText: string;
  // 图表高度
  height: number | string;
  lineWidth: number;
  // 是有fullscreen递归
  needChild: boolean;
  // 是否需要设置全屏
  needFullScreen: boolean;
  options: IStatusChartOption | ITextChartOption | MonitorEchartOptions;
  // 图表刷新间隔
  refreshInterval: number;
  // 图表系列数据
  series: IStatusSeries | ITextSeries | MonitorEchartSeries;
  // 是使用组件内的无数据设置
  setNoData: boolean;
  subtitle: string;
  // 图表title
  title: string;
  watchOptionsDeep: boolean;
  // 获取指标告警状态信息
  getAlarmStatus: (param: any) => Promise<IAlarmStatus>;
  // 获取图标数据
  getSeriesData: (timeFrom?: string, timeTo?: string, range?: boolean) => Promise<void>;
}
ofType<IMonitorEchartsProps>().convert(MonitorCharts);
