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

export const COLOR_LIST = [
  '#A4B3CD',
  '#F59789',
  '#F5C78E',
  '#6FC5BF',
  '#92D4F1',
  '#DCDEE5',
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
export default {
  animation: false,
  animationDelay: 300,
  animationDuration: 20,
  animationDurationUpdate: 0,
  animationThreshold: 2000,
  grid: {
    backgroundColor: 'transparent',
    bottom: 25,
    containLabel: true,
    left: 16,
    right: 16,
    top: 10,
  },
  // color: COLOR_LIST,
  legend: {
    animation: false,
    bottom: 0,
    height: 25,
    icon: 'rect',
    itemGap: 20,
    itemHeight: 10,
    itemWidth: 10,
    padding: [10, 10, 5, 10],
    show: true,
    textStyle: {
      color: '#313238',
      fontFamily: 'Roboto-Regular',
      fontSize: 12,
    },
    type: 'scroll',
  },
  markLine: [
    {
      z: 100, // markLine markArea不支持单独设置层级
    },
  ],
  series: [],
  title: {
    show: false,
    text: '',
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
        yAxisIndex: false,
      },
      restore: { icon: 'path://' },
      saveAsImage: {
        icon: 'path://',
      },
    },
    iconStyle: {
      borderWidth: 0,
      color: '#979ba5',
      shadowColor: '#979ba5',
      shadowOffsetX: 0,
      shadowOffsetY: 0,
    },
    itemSize: 0,
    showTitle: false,
  },
  tooltip: {
    alwaysShowContent: false,
    appendToBody: true,
    axisPointer: {
      label: {
        backgroundColor: '#6a7985',
      },
      type: 'line',
    },
    backgroundColor: 'rgba(54,58,67,.88)',
    borderWidth: 0,
    extraCssText: 'border-radius: 4px',
    show: true,
    textStyle: {
      color: '#BEC0C6',
      fontSize: 12,
    },
    transitionDuration: 0,
    trigger: 'axis',
  },
  useUTC: false,
  xAxis: [
    {
      axisLabel: {
        align: 'center',
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
      minInterval: 5 * 60 * 1000,
      scale: true,
      splitLine: {
        show: false,
      },
      splitNumber: 10,
      type: 'time',
    },
  ],
  yAxis: [
    {
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
      min: (value) => Math.min(0, value.min),
      scale: true,
      splitLine: {
        lineStyle: {
          color: '#F0F1F5',
          type: 'dashed',
        },
        show: true,
      },
      type: 'value',
      z: 3,
    },
  ],
};

export const getSeriesData = ({ color, data, name }) => ({
  animationDuration: 1000, // 动画持续时间
  animationEasing: 'cubicOut', // 动画缓动效果
  backgroundStyle: {
    borderColor: null,
    borderRadius: 0,
    borderType: 'solid',
    borderWidth: 0,
    color: 'rgba(180, 180, 180, 0.2)',
    opacity: 1,
    shadowBlur: 0,
    shadowColor: null,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
  },
  clip: true,
  color: [],
  colorBy: 'data',
  coordinateSystem: 'cartesian2d',
  data,
  emphasis: {
    label: {},
  },
  itemStyle: {
    color,
  },
  label: {},
  large: false,
  largeThreshold: 400,
  legendHoverLink: true,
  markArea: {},
  markLine: {},

  name,
  progressive: 3000,
  progressiveChunkMode: 'mod',
  roundCap: false,
  showBackground: false,

  stack: 'total',
  type: 'bar',
  z: 4,
  zlevel: 0,
});
