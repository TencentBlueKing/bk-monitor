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

export const lineOrBarOptions = {
  animation: true,
  color: [],
  grid: {
    backgroundColor: 'transparent',
    bottom: 0,
    containLabel: true,
    left: 0,
    right: 26,
    top: 16,
  },
  legend: {
    bottom: 0,
    icon: 'rect',
    itemGap: 12,
    itemHeight: 8,
    itemWidth: 12,
    padding: [5, 5, 0, 0],
    selectedMode: 'multiple',
    show: true,
    textStyle: {
      color: '#63656E',
      fontSize: 12,
    },
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
    feature: {
      dataZoom: {
        icon: {
          back: 'path://',
          zoom: 'path://',
        },
        iconStyle: {
          opacity: 0,
        },
        show: true,
        yAxisIndex: [],
      },
      restore: { icon: 'path://' },
      saveAsImage: {
        icon: 'path://',
      },
    },
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
      type: 'line',
    },
    backgroundColor: 'rgba(0,0,0,0.8)',
    borderWidth: 0,
    extraCssText: 'border-radius: 0',
    show: true,
    textStyle: {
      fontSize: 12,
    },
    transitionDuration: 0,
    trigger: 'axis',
  },
  useUTC: true,
  xAxis: {
    axisLabel: {
      align: 'left',
      color: '#979BA5',
      fontSize: 12,
      showMaxLabel: false,
      showMinLabel: false,
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
    boundaryGap: false,
    minInterval: 60 * 1000,
    scale: true,
    splitLine: {
      show: false,
    },
    splitNumber: 10,
    type: 'time',
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
  lengend: {
    show: false,
  },
  series: [
    {
      avoidLabelOverlap: false,
      label: {
        position: 'center',
        show: false,
      },
      labelLine: {
        show: false,
      },
      radius: ['50%', '70%'],
      type: 'pie',
    },
  ],
  tooltip: {
    trigger: 'item',
  },
};

export const pillarChartOption = {
  grid: {
    bottom: '0',
    containLabel: true,
    left: '0',
    right: '4%',
    top: '4%',
  },
  series: [],
  tooltip: {
    trigger: 'axis',
  },
  xAxis: {
    axisLabel: {
      color: '#979BA5',
    },
    axisLine: {
      show: false,
    },
    axisTick: {
      show: false,
    },
    data: [],
    type: 'category',
  },
  yAxis: {
    axisLabel: {
      color: '#979BA5',
    },
    axisLine: {
      show: false,
    },
    axisTick: {
      show: false,
    },
    splitLine: {
      lineStyle: {
        color: '#F0F1F5',
        type: 'dashed',
      },
      show: true,
    },
    type: 'value',
  },
};
