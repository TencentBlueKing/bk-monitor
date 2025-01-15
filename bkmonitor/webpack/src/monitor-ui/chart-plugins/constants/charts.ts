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
import type { MonitorEchartOptions } from '../typings';

export const COLOR_LIST = [
  '#F0AE69',
  '#689DF3',
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

export const COLOR_LIST_BAR = ['#4051A3', ...COLOR_LIST];

/** 离群检测算法图表线条颜色组 */
export const COLOR_LIST_OUTLIER = [
  '#FDB980',
  '#96C989',
  '#5766ED',
  '#F1CE1A',
  '#EC6D93',
  '#8F87E1',
  '#6ECD94',
  '#F6A52C',
  '#4185EB',
  '#DD6CD2',
  '#8A88C1',
  '#7CB3A3',
  '#DBD84D',
  '#4E76B1',
  '#BF92CB',
  ...COLOR_LIST,
];

/** 线性图配置 */
export const MONITOR_LINE_OPTIONS: MonitorEchartOptions = {
  useUTC: false,
  animation: false,
  animationThreshold: 2000,
  animationDurationUpdate: 0,
  animationDuration: 20,
  animationDelay: 300,
  title: {
    text: '',
    show: false,
  },
  color: COLOR_LIST,
  legend: {
    show: false,
  },
  tooltip: {
    show: true,
    trigger: 'axis',
    axisPointer: {
      type: 'line',
      label: {
        backgroundColor: '#6a7985',
      },
    },
    transitionDuration: 0,
    alwaysShowContent: false,
    backgroundColor: 'rgba(54,58,67,.88)',
    borderWidth: 0,
    textStyle: {
      fontSize: 12,
      color: '#BEC0C6',
    },
    extraCssText: 'border-radius: 4px',
  },
  toolbox: {
    showTitle: false,
    itemSize: 0,
    iconStyle: {
      color: '#979ba5',
      borderWidth: 0,
      shadowColor: '#979ba5',
      shadowOffsetX: 0,
      shadowOffsetY: 0,
    },
    feature: {
      saveAsImage: {
        icon: 'path://',
      },
      dataZoom: {
        icon: {
          zoom: 'path://',
          back: 'path://',
        },
        show: true,
        yAxisIndex: false,
        iconStyle: {
          opacity: 0,
        },
      },
      restore: { icon: 'path://' },
    },
  },
  grid: {
    containLabel: true,
    left: 16,
    right: 16,
    top: 10,
    bottom: 10,
    backgroundColor: 'transparent',
  },
  xAxis: {
    type: 'time',
    boundaryGap: false,
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
      showMinLabel: false,
      showMaxLabel: false,
      align: 'left',
    },
    splitLine: {
      show: false,
    },
    minInterval: 5 * 60 * 1000,
    splitNumber: 10,
    scale: true,
  },
  markLine: [
    {
      z: 100, // markLine markArea不支持单独设置层级
    },
  ],
  yAxis: {
    type: 'value',
    axisLine: {
      show: false,
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
    scale: true,
    min: 'dataMin',
    z: 3,
  },
  series: [],
};

/** 柱状图配置 */
export const MONITOR_BAR_OPTIONS = {
  useUTC: false,
  color: COLOR_LIST_BAR,
  grid: {
    containLabel: true,
    left: 16,
    right: 16,
    top: 10,
    bottom: 10,
    backgroundColor: 'transparent',
  },
  xAxis: {
    type: 'time',
    boundaryGap: false,
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
      showMinLabel: false,
      showMaxLabel: false,
      align: 'center',
      interval: 0,
    },
    splitLine: {
      show: false,
    },
    minInterval: 0,
    splitNumber: 10,
    scale: true,
  },
  yAxis: {
    type: 'value',
    axisLine: {
      show: false,
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
    z: 3,
  },
  tooltip: {
    show: true,
    trigger: 'axis',
    axisPointer: {
      type: 'line',
      label: {
        backgroundColor: '#6a7985',
      },
    },
    transitionDuration: 0,
    alwaysShowContent: false,
    backgroundColor: 'rgba(54,58,67,.88)',
    borderWidth: 0,
    textStyle: {
      fontSize: 12,
      color: '#BEC0C6',
    },
    extraCssText: 'border-radius: 4px',
  },
  markLine: [
    {
      z: 100, // markLine markArea不支持单独设置层级
    },
  ],
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
    feature: {
      saveAsImage: {
        icon: 'path://',
      },
      dataZoom: {
        icon: {
          zoom: 'path://',
          back: 'path://',
        },
        show: true,
        yAxisIndex: false,
        iconStyle: {
          opacity: 0,
        },
      },
      restore: { icon: 'path://' },
    },
  },
  legend: {
    show: false,
  },
};

/** 饼图配置 */
export const MONITOR_PIE_OPTIONS = {
  tooltip: {
    trigger: 'item',
    formatter: '',
  },
  legend: {
    show: false,
  },
  series: [],
};

/** 地图配置 */
export const CHINA_MAP_OPTIONS = {
  tooltip: {
    formatter(params: any) {
      if (Number.isNaN(params.value)) return '';
      return `${params.seriesName}<br />${params.name}：${params.value}`;
    }, // 数据格式化
  },
  // visualMap: {
  //   min: 0,
  //   max: 1500,
  //   left: 'left',
  //   top: 'bottom',
  //   text: ['高', '低'], // 取值范围的文字
  //   inRange: {
  //     color: ['#e0ffff', '#006edd']// 取值范围的颜色
  //   },
  //   show: true// 图注
  // },
  geo: {
    map: 'china',
    roam: false, // 不开启缩放和平移
    zoom: 1.23, // 视角缩放比例
    label: {
      normal: {
        show: false,
        fontSize: '10',
        color: 'rgba(0,0,0,0.7)',
      },
    },
    itemStyle: {
      normal: {
        borderColor: 'rgba(0, 0, 0, 0.2)',
        borderWidth: 1,
      },
      emphasis: {
        areaColor: '#f7f7f7', // 鼠标选择区域颜色
        shadowOffsetX: 0,
        shadowOffsetY: 0,
        // shadowBlur: 20,
        borderWidth: 1,
        shadowColor: 'rgba(0, 0, 0, 0.5)',
      },
    },
  },
  series: [
    {
      name: '中国',
      type: 'map',
      map: 'china',
      zoom: 1.23, // 视角缩放比例
      itemStyle: {
        normal: {
          // 未选中状态
          borderColor: 'rgba(0, 0, 0, 0.2)',
        },
        emphasis: {
          areaColor: '#f7f7f7', // 鼠标选择区域颜色
        },
      },
      data: [],
    },
  ],
};
