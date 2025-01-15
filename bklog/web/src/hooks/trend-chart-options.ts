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

import dayjs from 'dayjs';
export default {
  useUTC: false,
  color: [
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
  ],
  // animation: true,
  tool: {
    show: false,
  },
  annotation: {
    show: false,
    list: ['ip', 'process', 'strategy'],
  },
  gradientColor: ['#f6efa6', '#d88273', '#bf444c'],
  textStyle: {
    fontFamily: 'sans-serif',
    fontSize: 12,
    fontStyle: 'normal',
    fontWeight: 'normal',
  },

  title: [
    {
      show: false,
    },
  ],
  toolbox: [
    {
      showTitle: false,
      itemSize: 0,
      iconStyle: {
        color: '#979ba5',
        fontSize: 14,
        borderWidth: 0,
        shadowColor: '#979ba5',
        shadowOffsetX: 0,
        shadowOffsetY: 0,
        borderColor: '#666',
      },
      feature: {
        saveAsImage: {
          icon: 'path://',
          show: true,
          title: '保存为图片',
          type: 'png',
          connectedBackgroundColor: '#fff',
          name: '',
          excludeComponents: ['toolbox'],
          pixelRatio: 1,
          lang: ['右键另存为图片'],
        },
        dataZoom: {
          show: true,
          yAxisIndex: [],
          iconStyle: {
            opacity: 0,
          },
          filterMode: 'filter',
          title: {
            zoom: '区域缩放',
            back: '区域缩放还原',
          },
          brushStyle: {
            borderWidth: 0,
            color: 'rgba(0,0,0,0.2)',
          },
          iconStatus: {
            zoom: 'emphasis',
            back: 'normal',
          },
        },
        restore: {
          icon: 'path://',
          show: true,
          title: '还原',
        },
      },
      show: true,
      z: 6,
      zlevel: 0,
      orient: 'horizontal',
      left: 'right',
      top: 'top',
      backgroundColor: 'transparent',
      borderColor: '#ccc',
      borderRadius: 0,
      borderWidth: 0,
      padding: 5,
      itemGap: 8,
      emphasis: {
        iconStyle: {
          borderColor: '#3E98C5',
        },
      },
      tooltip: {
        show: false,
      },
    },
  ],
  axisPointer: [
    {
      show: 'auto',
      triggerOn: null,
      zlevel: 0,
      z: 50,
      type: 'line',
      snap: false,
      triggerTooltip: true,
      value: null,
      status: null,
      link: [],
      animation: null,
      animationDurationUpdate: 200,
      lineStyle: {
        color: '#aaa',
        width: 1,
        type: 'solid',
      },
      shadowStyle: {
        color: 'rgba(150,150,150,0.3)',
      },
      label: {
        show: true,
        formatter: null,
        precision: 'auto',
        margin: 3,
        color: '#fff',
        padding: [5, 7, 5, 7],
        backgroundColor: 'auto',
        borderColor: null,
        borderWidth: 0,
        shadowBlur: 3,
        shadowColor: '#aaa',
      },
    },
  ],
  tooltip: {
    show: true,
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
      label: {
        backgroundColor: '#6a7985',
        show: false,
      },
      axis: 'auto',
      crossStyle: {
        color: 'transparent',
        opacity: 0,
        width: 0,
        type: 'dashed',
        textStyle: {},
      },
      animation: 'auto',
      animationDurationUpdate: 200,
      animationEasingUpdate: 'exponentialOut',
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
    appendToBody: true,
    zlevel: 0,
    z: 60,
    showContent: true,
    triggerOn: 'mousemove|click',
    displayMode: 'single',
    renderMode: 'auto',
    confine: false,
    showDelay: 0,
    hideDelay: 100,
    enterable: false,
    borderColor: '#333',
    borderRadius: 4,
    padding: 5,
    formatter: function (params) {
      return `<div>
        <strong>${dayjs.tz(params[0]?.data?.[0]).format('YYYY-MM-DD HH:mm:ss') ?? params[0].name}</strong>
        <div style="display: flex; align-items: center;"><span style="display: inline-block; background-color:${params[0].color};margin-right: 4px;width: 6px;height: 6px; border-radius: 50%;"></span> ${params[0]?.data?.[1]} </div>
      </div>`;
    },
  },
  yAxis: [
    {
      type: 'value',
      axisLine: {
        show: false,
        lineStyle: {
          color: '#666',
          width: 1,
          type: 'dashed',
        },
        onZero: true,
        onZeroAxisIndex: null,
        symbol: ['none', 'none'],
        symbolSize: [10, 15],
      },
      axisTick: {
        show: false,
        inside: false,
        length: 5,
        lineStyle: {
          width: 1,
        },
      },
      axisLabel: {
        color: '#979BA5',
        show: true,
        inside: false,
        rotate: 0,
        showMinLabel: null,
        showMaxLabel: null,
        margin: 8,
        fontSize: 12,
        // formatter: barChartOptionInstance.handleYxisLabelFormatter,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#F0F1F5',
          type: 'dashed',
          width: 1,
        },
      },
      scale: false,
      z: 3,
      min: 0,
      boundaryGap: [0, 0],
      splitNumber: 5,
      minorTick: {
        show: false,
        splitNumber: 5,
        length: 3,
        lineStyle: {},
      },
      minorSplitLine: {
        show: false,
        lineStyle: {
          color: '#eee',
          width: 1,
        },
      },
      show: true,
      zlevel: 0,
      inverse: false,
      name: '',
      nameLocation: 'end',
      nameRotate: null,
      nameTruncate: {
        maxWidth: null,
        ellipsis: '...',
        placeholder: '.',
      },
      nameTextStyle: {},
      nameGap: 15,
      silent: false,
      triggerEvent: false,
      tooltip: {
        show: false,
      },
      axisPointer: {
        status: 'hide',
        value: 487.7916666666667,
        seriesDataIndices: [],
      },
      splitArea: {
        show: false,
        areaStyle: {
          color: ['rgba(250,250,250,0.3)', 'rgba(200,200,200,0.3)'],
        },
      },
      offset: 0,
      rangeEnd: null,
      rangeStart: null,
    },
  ],
  xAxis: [
    {
      type: 'time',
      boundaryGap: false,
      axisTick: {
        show: false,
        inside: false,
        length: 5,
        lineStyle: {
          width: 1,
        },
      },
      axisLine: {
        show: false,
        lineStyle: {
          color: '#666',
          width: 1,
          type: 'solid',
        },
        onZero: true,
        onZeroAxisIndex: null,
        symbol: ['none', 'none'],
        symbolSize: [10, 15],
      },
      axisLabel: {
        fontSize: 12,
        color: '#979BA5',
        showMinLabel: false,
        showMaxLabel: false,
        align: 'center',
        show: true,
        inside: false,
        rotate: 0,
        margin: 8,
      },
      splitLine: {
        show: false,
        lineStyle: {
          color: ['#ccc'],
          width: 1,
          type: 'solid',
        },
      },
      minInterval: 60000,
      splitNumber: 10,
      scale: true,
      min: 'dataMin',
      max: 'dataMax',
      minorTick: {
        show: false,
        splitNumber: 5,
        length: 3,
        lineStyle: {},
      },
      minorSplitLine: {
        show: false,
        lineStyle: {
          color: '#eee',
          width: 1,
        },
      },
      show: true,
      zlevel: 0,
      z: 0,
      inverse: false,
      name: '',
      nameLocation: 'end',
      nameRotate: null,
      nameTruncate: {
        maxWidth: null,
        ellipsis: '...',
        placeholder: '.',
      },
      nameTextStyle: {},
      nameGap: 15,
      silent: false,
      triggerEvent: false,
      tooltip: {
        show: false,
      },
      axisPointer: {
        status: 'hide',
        value: 1728887040000,
        seriesDataIndices: [
          {
            seriesIndex: 0,
            dataIndexInside: 3,
            dataIndex: 3,
          },
        ],
      },
      splitArea: {
        show: false,
        areaStyle: {
          color: ['rgba(250,250,250,0.3)', 'rgba(200,200,200,0.3)'],
        },
      },
      offset: 0,
      rangeEnd: null,
      rangeStart: null,
    },
  ],
  grid: [
    {
      containLabel: true,
      left: 0,
      right: 26,
      top: 16,
      bottom: 0,
      backgroundColor: 'transparent',
      show: false,
      zlevel: 0,
      z: 0,
      borderWidth: 1,
      borderColor: '#ccc',
    },
  ],
  series: [
    {
      data: [],
      name: '',
      type: 'bar',
      barMinHeight: 0,
      z: 4,
      markLine: {},
      markArea: {},
      zlevel: 0,
      coordinateSystem: 'cartesian2d',
      legendHoverLink: true,
      large: false,
      largeThreshold: 400,
      progressive: 3000,
      progressiveChunkMode: 'mod',
      itemStyle: {},
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
    },
  ],
  visualMap: [],
  legend: [
    {
      show: false,
    },
  ],
};
