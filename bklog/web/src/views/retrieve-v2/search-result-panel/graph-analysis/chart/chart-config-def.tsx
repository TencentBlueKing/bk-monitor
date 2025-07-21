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
  animation: true,
  color,
  grid: {
    backgroundColor: 'transparent',
    bottom: 40,
    containLabel: true,
    left: 80,
    right: 40,
    top: 28,
  },
  legend: {
    icon: 'rect',
    itemGap: 12,
    itemHeight: 8,
    itemWidth: 12,
    left: 120,
    padding: [5, 5, 0, 0],
    selectedMode: 'multiple',
    show: true,
    textStyle: {
      color: '#63656E',
      fontSize: 12,
    },
    top: 'bottom',
    type: 'scroll',
  },
  series: [],
  title: {
    left: 'left',
    padding: [0, 0, 0, 16],
    show: false,
    subtext: null,
    subtextStyle: {
      align: 'left',
      color: '#979BA5',
      fontSize: 12,
      fontWeight: 'bold',
    },
    text: '',
    textAlign: 'auto',
    textStyle: {
      color: '#63656E',
      fontSize: 12,
      fontWeight: 'bold',
    },
    textVerticalAlign: 'auto',
    top: 12,
  },
  toolbox: {
    feature: {},
    iconStyle: {
      borderWidth: 0,
      color: '#979ba5',
      fontSize: 14,
      shadowColor: '#979ba5',
      shadowOffsetX: 0,
      shadowOffsetY: 0,
    },
    itemSize: 0,
    showTitle: false,
  },
  tooltip: {
    alwaysShowContent: false,
    axisPointer: {
      label: {
        backgroundColor: '#6a7985',
      },
      snap: true,
      type: 'cross',
    },
    backgroundColor: 'rgba(0,0,0,0.8)',
    borderWidth: 0,
    extraCssText: 'border-radius: 0',
    show: true,
    textStyle: {
      color: '#fff',
      fontSize: 12,
    },
    transitionDuration: 0,
    trigger: 'item',
  },
  useUTC: true,
  xAxis: {
    axisLabel: {
      align: 'center',
      color: '#979BA5',
      fontSize: 12,
      showMaxLabel: true,
      showMinLabel: true,
    },
    axisLine: {
      lineStyle: {
        color: '#ccd6eb',
        type: 'solid',
        width: 1,
      },
      show: false,
    },
    axisTick: {
      show: false,
    },
    boundaryGap: true,
    minInterval: 60 * 1000,
    scale: true,
    splitLine: {
      show: false,
    },
    splitNumber: 10,
    type: 'category',
  },
  yAxis: {
    axisLabel: {
      color: '#979BA5',
    },
    axisLine: {
      lineStyle: {
        color: '#ccd6eb',
        type: 'solid',
        width: 1,
      },
      show: false,
      snap: true,
    },
    axisTick: {
      show: false,
    },
    scale: false,
    splitLine: {
      lineStyle: {
        color: '#F0F1F5',
        type: 'dashed',
      },
      show: true,
    },
    type: 'value',
    // splitNumber: 3,
    z: 3,
  },
};

export const pieOptions: any = {
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
  icon: 'pin',
  padding: [0, 0],
  series: {
    center: ['50%', '50%'],
    data: [],
    emphasis: {
      labelLine: {
        show: true,
      },
    },
    label: {
      alignTo: 'none',
      color: '#666666',
      fontSize: 12,
      lineHeight: 18,
      show: true,
    },
    radius: '60%',
    type: 'pie',
  },
  tooltip: {
    appendToBody: true,
    backgroundColor: 'rgba(50, 50, 50, 0.7)', // 半透明背景
    borderColor: '#333', // 边框颜色
    borderWidth: 1,
    confine: true,
    extraCssText: 'box-shadow: 0 0 5px rgba(0, 0, 0, 0.3); padding: 5px', // 添加阴影
    order: 'seriesAsc',
    renderMode: 'html',
    show: true,
    textStyle: {
      color: '#fff',
      fontFamily: 'MicrosoftYaHei, PingFang SC',
      fontSize: 12,
      fontWeight: 'normal',
      lineHeight: 18,
    },
    trigger: 'item',
  },
};
