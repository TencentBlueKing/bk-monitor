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
  // color: COLOR_LIST,
  legend: {
    show: true,
    bottom: 0,
    icon: 'rect',
    height: 25,
    itemWidth: 10,
    itemHeight: 10,
    itemGap: 20,
    padding: [10, 10, 3, 10],
    animation: false,
    type: 'scroll',
    textStyle: {
      fontSize: 12,
      color: '#313238',
      fontFamily: 'Roboto-Regular',
    },
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
    appendToBody: true,
    formatter: null,
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
    bottom: 25,
    backgroundColor: 'transparent',
  },
  xAxis: [
    {
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
      },
      splitLine: {
        show: false,
      },
      minInterval: 5 * 60 * 1000,
      splitNumber: 10,
      scale: true,
    },
  ],
  markLine: [
    {
      z: 100, // markLine markArea不支持单独设置层级
    },
  ],
  yAxis: [
    {
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
      min: value => Math.min(0, value.min),
      z: 3,
    },
  ],
  series: [],
};

export const getSeriesData = ({ data, name, color }) => ({
  data,
  name,
  type: 'bar',
  stack: 'total',
  z: 4,
  markLine: {},
  markArea: {},
  color: [],
  zlevel: 0,
  coordinateSystem: 'cartesian2d',
  legendHoverLink: true,
  large: false,
  largeThreshold: 400,
  progressive: 3000,
  progressiveChunkMode: 'mod',
  itemStyle: {
    color,
  },

  colorBy: 'data',
  emphasis: {
    label: {},
  },
  clip: true,
  roundCap: false,
  showBackground: false,

  backgroundStyle: {
    color: 'rgba(180, 180, 180, 0.2)',
    borderColor: null,
    borderWidth: 0,
    borderType: 'solid',
    borderRadius: 0,
    shadowBlur: 0,
    shadowColor: null,
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    opacity: 1,
  },
  label: {},
  animationDuration: 1000, // 动画持续时间
  animationEasing: 'cubicOut', // 动画缓动效果
});
