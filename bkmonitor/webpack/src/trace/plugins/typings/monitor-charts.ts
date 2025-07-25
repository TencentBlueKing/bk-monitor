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
export interface ICommonCharts {
  // 图表高度
  height: number;
  // 图表宽度
  width: number;
  // 获取图表数据
  /**
   * @description: 获取图表数据
   * @param {*} 数据开始时间
   * @return {*} 数据结束时间
   */
  getPanelData: (timeFrom?: string, timeTo?: string) => Promise<any>;
}
export interface ICommonChartTips {
  list: ICommonChartTipsItem[];
  style?: string; // 自定义样式
  title: string; // tips title
}
export interface ICommonChartTipsItem {
  color: string; // 颜色
  isCurrent: boolean; // 是否是当前hover值
  name: string; // item name
  style?: string; // 自定义样式
  unit?: string; // 单位
  value: string; // 值
}

export interface ICurPoint {
  color: string;
  dataIndex: number;
  name: string;
  seriesIndex: number;
  xAxis: number | string;
  yAxis: number | string;
}
