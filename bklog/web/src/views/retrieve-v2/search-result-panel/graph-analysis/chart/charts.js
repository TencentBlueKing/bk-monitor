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
 * @description 图表默认配置颜色
 */

import { cloneDeep } from 'lodash';
// 默认色 图表非ECharts图表默认颜色修改（需要配置到主题中, 进行覆盖）
export const COLOR_CHART_CONFIG_DEFAULT = {
  tooltipsBackgroundColor: '#fff',
  tooltipsBorderColor: '',
  tooltipsTextColor: '',
  axisLabelColor: '#666666',
  axisLineColor: '#DCDEE5',
  markPointTextBorderColor: '#fff',
  splitLineColor: '#EAEBF0',
  totalLabelColor: '#666666',
  axiosBarLabelColor: '#313238',
  pieLabelColor: '#666666',
  trendUpColor: '#8CC97D',
  trendDownColor: '#E9706B',
  trendAreaColor: '#ffffff',
  calendarNotDataColor: '#ff0000',
  calendarMinMaxColor: '#4289FF',
  calendarMinMaxBorderColor: '#fff',
  calendarScatterTimeColor: '#63656E',
  calendarDayLabelColor: '#979BA5',
  calendarItemColor: '#FFFFFF',
  calendarScatterLightColor: '#FFF',
  calendarScatterDarkColor: '#63656E',
  calendarItemBorderColor: '#DCDEE5',
  calendarSimpleSplitBorderColor: '',
  calendarSimpleBorderColor: '#fff',
  sunburstBorderColor: '#fff',
  sunburstParentColor: '#313238',
  sunburstTextColor: '#63656',
  radarLabelColor: '#63656E',
  radarIndicatorLine: '#ECEDF1',
  radarLegendTextColor: '#313238',
  radarInnerZebraBackground: '#FFFFFF',
  radarOuterZebraBackground: '#F5F7FA',
  numberPanelExpectBarBackground: '#EAEBF0',
  numberPanelGradientBackground: '#FFF',
};
export const COLOR_CHART_CONFIG = cloneDeep(COLOR_CHART_CONFIG_DEFAULT);

// ECharts图表颜色序列
export const COLOR_LIST = [
  '#96C989',
  '#F1CE1A',
  '#7EC7E7',
  '#E28D68',
  '#5766ED',
  '#EC6D93',
  '#8F87E1',
  '#6ECD94',
  '#F6A52C',
  '#5ACCCC',
  '#CC7575',
  '#4185EB',
  '#DD6CD2',
  '#8A88C1',
  '#7CB3A3',
  '#DBD84D',
  '#8DBAD3',
  '#D38D8D',
  '#4E76B1',
  '#BF92CB',
];
export const COLOR_TABLE_LEGEND = [
  '#3A84FF',
  '#96C989',
  '#F1CE1A',
  '#7EC7E7',
  '#FFA065',
  '#5A65F4',
  '#EC6D93',
  '#879CE1',
  '#6ECD94',
];
window.COLOR_LIST = COLOR_LIST;

// 图表全局配置
export const BASE_CHART_OPTIONS = {
  color: COLOR_LIST,
  legend: {
    show: true,
    type: 'scroll',
    bottom: 10,
    padding: [5, 10],
    icon: 'circle',
  },
  tooltip: {
    trigger: 'none',
    confine: true,
    borderWidth: 0,
    hideDelay: 0,
    transitionDuration: 0,
    // order,
    axisPointer: {
      type: 'line',
      snap: true,
    },
    textStyle: {
      fontSize: 10,
    },
  },
  grid: [
    {
      top: 10,
      left: 10,
      right: 10,
      bottom: 10,
      containLabel: true,
    },
  ],
  toolbox: {
    itemSize: 0,
    feature: {
      dataZoom: {
        show: true,
        xAxisIndex: 0,
        yAxisIndex: 'none',
      },
    },
  },
  animation: false,
  stateAnimation: {
    duration: 0,
  },
};
