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

const color = [
  '#A3C5FD',
  '#EAB839',
  '#6ED0E0',
  '#EF843C',
  '#E24D42',
  '#1F78C1',
  '#BA43A9',
  '#705DA0',
  '#508642',
  '#CCA300',
  '#447EBC',
  '#C15C17',
  '#890F02',
  '#0A437C',
  '#6D1F62',
  '#584477',
  '#B7DBAB',
  '#F4D598',
  '#70DBED',
  '#F9BA8F',
  '#F29191',
  '#82B5D8',
  '#E5A8E2',
  '#AEA2E0',
  '#629E51',
  '#E5AC0E',
  '#64B0C8',
  '#E0752D',
  '#BF1B00',
  '#0A50A1',
  '#962D82',
  '#614D93',
  '#9AC48A',
  '#F2C96D',
  '#65C5DB',
  '#F9934E',
  '#EA6460',
  '#5195CE',
  '#D683CE',
  '#806EB7',
  '#3F6833',
  '#967302',
  '#2F575E',
  '#99440A',
  '#58140C',
  '#052B51',
  '#511749',
  '#3F2B5B',
  '#E0F9D7',
  '#FCEACA',
  '#CFFAFF',
  '#F9E2D2',
  '#FCE2DE',
  '#BADFF4',
  '#F9D9F9',
  '#DEDAF7',
];

export const lineOrBarOptions = {
  useUTC: true,
  title: {
    text: '',
    show: false,
    textAlign: 'auto',
    textVerticalAlign: 'auto',
    left: 'left',
    top: 12,
    padding: [0, 0, 0, 16],
    textStyle: {
      color: '#63656E',
      fontSize: 12,
      fontWeight: 'bold',
    },
    subtext: null,
    subtextStyle: {
      color: '#979BA5',
      fontSize: 12,
      fontWeight: 'bold',
      align: 'left',
    },
  },
  color,
  legend: {
    type: 'scroll',
    top: 'bottom',
    left: 120,
    show: true,
    itemGap: 12,
    itemWidth: 12,
    itemHeight: 8,
    padding: [5, 5, 0, 0],
    selectedMode: 'multiple',
    textStyle: {
      color: '#63656E',
      fontSize: 12,
    },
    icon: 'rect',
  },
  tooltip: {
    show: true,
    trigger: 'item',
    axisPointer: {
      type: 'cross',
      snap: true,
      label: {
        backgroundColor: '#6a7985',
      },
    },
    transitionDuration: 0,
    alwaysShowContent: false,
    backgroundColor: 'rgba(0,0,0,0.8)',
    borderWidth: 0,
    textStyle: {
      fontSize: 12,
      color: '#fff',
    },
    extraCssText: 'border-radius: 0',
  },
  toolbox: {
    showTitle: false,
    itemSize: 0,
    iconStyle: {
      color: '#979ba5',
      fontSize: 14,
      borderWidth: 0,
      shadowColor: '#979ba5',
      shadowOffsetX: 0,
      shadowOffsetY: 0,
    },
    feature: {},
  },
  grid: {
    containLabel: true,
    top: 28,
    left: 80,
    right: 40,
    bottom: 40,
    backgroundColor: 'transparent',
  },
  xAxis: {
    type: 'category',
    boundaryGap: true,
    axisTick: {
      show: false,
    },
    axisLine: {
      show: false,
      lineStyle: {
        color: '#ccd6eb',
        width: 1,
        type: 'solid',
      },
    },
    axisLabel: {
      fontSize: 12,
      color: '#979BA5',
      showMinLabel: true,
      showMaxLabel: true,
      align: 'center',
    },
    splitLine: {
      show: false,
    },
    minInterval: 60 * 1000,
    splitNumber: 10,
    scale: true,
  },
  yAxis: {
    type: 'value',
    axisLine: {
      show: false,
      snap: true,
      lineStyle: {
        color: '#ccd6eb',
        width: 1,
        type: 'solid',
      },
    },
    axisTick: {
      show: false,
    },
    axisLabel: {
      color: '#979BA5',
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: '#F0F1F5',
        type: 'dashed',
      },
    },
    scale: false,
    // splitNumber: 3,
    z: 3,
  },
  series: [],
  animation: true,
};

export const pieOptions: any = {
  padding: [0, 0],
  series: {
    type: 'pie',
    radius: '60%',
    center: ['50%', '50%'],
    label: {
      show: true,
      alignTo: 'none',
      fontSize: 12,
      lineHeight: 18,
      color: '#666666',
    },
    emphasis: {
      labelLine: {
        show: true,
      },
    },
    data: [],
  },
  tooltip: {
    show: true,
    trigger: 'item',
    confine: true,
    backgroundColor: 'rgba(50, 50, 50, 0.7)', // 半透明背景
    borderColor: '#333', // 边框颜色
    borderWidth: 1,
    textStyle: {
      fontSize: 12,
      lineHeight: 18,
      fontWeight: 'normal',
      fontFamily: 'MicrosoftYaHei, PingFang SC',
      color: '#fff',
    },
    order: 'seriesAsc',
    appendToBody: true,
    renderMode: 'html',
    extraCssText: 'box-shadow: 0 0 5px rgba(0, 0, 0, 0.3); padding: 5px', // 添加阴影
  },
  icon: 'pin',
  color: [
    '#5BCCD8',
    '#F77FA8',
    '#F1CD46',
    '#67C19B',
    '#FABC47',
    '#79A9D5',
    '#F09D6B',
    '#60C3B6',
    '#C793E6',
    '#E98C8C',
    '#9FC8CC',
    '#E6A3BA',
    '#DBCE9E',
    '#8DC2A3',
    '#E0CBA2',
    '#99B1C7',
    '#DBB59E',
    '#91B8B3',
    '#C0ABCC',
    '#CFA5A5',
  ],
};
