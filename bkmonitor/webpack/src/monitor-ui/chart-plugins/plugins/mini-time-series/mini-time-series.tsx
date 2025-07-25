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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { throttle } from 'lodash';

import { getValueFormat } from '../../../monitor-echarts/valueFormats/valueFormats';
import { type MonitorEchartOptions, echarts } from '../../typings/index';

import './mini-time-series.scss';
enum EDropType {
  compare = 'compare',
  end = 'end',
  refer = 'refer',
}
enum EPointType {
  compare = 'compare',
  end = 'end',
  refer = 'refer',
}

interface IProps {
  /* 以下参数为对比图专用 */
  compareX?: number;
  data?: [number, number][];
  disableHover?: boolean;
  dropType?: EDropType;
  groupId?: string;
  lastValueWidth?: number;
  pointType?: EPointType;
  referX?: number;
  showLastMarkPoint?: boolean;
  unit?: string;
  unitDecimal?: number;
  valueTitle?: string;
  onCompareXChange?: (x: number) => void;
  onPointTypeChange?: (type: EPointType) => void;
  onReferXChange?: (x: number) => void;
  chartStyle?: {
    chartWarpHeight: number;
    lineMaxHeight: number;
  };
}

@Component
export default class MiniTimeSeries extends tsc<IProps> {
  @Ref('chartInstance') chartRef: HTMLDivElement;
  /* 图表样式微调 （缩略图高度非常小仅24px, echarts无法渲染完全，在渲染时实际高度需尽可能占满容器） */
  @Prop({ type: Object, default: () => ({ lineMaxHeight: 24, chartWarpHeight: 50 }) }) chartStyle: IProps['chartStyle'];
  /* groupId */
  @Prop({ type: String, default: '' }) groupId: string;
  /* 数据 */
  @Prop({ type: Array, default: () => [] }) data: [number, number][];
  /* 单位 */
  @Prop({ type: String, default: '' }) unit: string;
  @Prop({ type: Number, default: 2 }) unitDecimal: number;
  /* tips显示值标题 */
  @Prop({ type: String, default: window.i18n.t('数量') }) valueTitle: string;
  /* 是否标记最后一个点并且右侧显示其值 */
  @Prop({ type: Boolean, default: true }) showLastMarkPoint: boolean;
  /* 固定右侧值的显示宽度 */
  @Prop({ type: Number, default: 0 }) lastValueWidth: number;

  options: MonitorEchartOptions = {
    grid: {
      left: 6,
      right: 6,
      bottom: 4,
      top: 1,
    },
    xAxis: {
      show: false,
      type: 'value',
      max: 'dataMax',
      min: 'dataMin',
    },
    yAxis: {
      show: false,
      type: 'value',
    },
    tooltip: {
      show: true,
      trigger: 'axis',
      appendToBody: true,
      padding: [6, 8, 6, 12],
      transitionDuration: 0,
    },
    series: [
      {
        type: 'line',
        cursor: 'auto',
        silent: false,
        emphasis: {
          disabled: true,
        },
        triggerLineEvent: true,
        data: [],
      },
    ],
  };
  // 当前视图是否hover
  isMouseOver = false;
  /* 最后一个值 */
  lastValue = '';
  /* 当前hover的标记点 */
  hoverPoint = {
    isHover: false,
  };

  resizeObserver = null;
  intersectionObserver: IntersectionObserver = null;
  throttleHandleResize = () => {};

  mounted() {
    this.throttleHandleResize = throttle(this.handleResize, 300);
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        if (entry.contentRect.width) {
          this.throttleHandleResize();
        }
      }
    });
    this.resizeObserver.observe(this.$el);
    setTimeout(this.registerObserver, 20);
  }
  destroyed() {
    (this as any).instance?.dispose?.();
    (this as any).instance = null;
    this.resizeObserver?.unobserve?.(this.$el);
    this.isMouseOver = false;
    this.unregisterObserver();
  }

  // 注册Intersection监听
  registerObserver() {
    if (this.intersectionObserver) {
      this.unregisterObserver();
    }
    this.intersectionObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (this.intersectionObserver && entry.intersectionRatio > 0) {
          this.initChart();
        }
      }
    });
    this.intersectionObserver.observe(this.$el);
  }
  unregisterObserver() {
    if (this.intersectionObserver) {
      this.intersectionObserver.unobserve(this.$el);
      this.intersectionObserver.disconnect();
      this.intersectionObserver = null;
    }
  }

  initChart() {
    if (!(this as any).instance) {
      setTimeout(() => {
        if (!this.chartRef) return;
        this.options = {
          ...this.options,
          yAxis: {
            ...this.options.yAxis,
            max: v => {
              return v.max + (((v.max || 1) * this.chartStyle.chartWarpHeight) / this.chartStyle.lineMaxHeight - v.max);
            },
            min: v => {
              return (
                0 - (((v.max || 1) * this.chartStyle.chartWarpHeight) / this.chartStyle.lineMaxHeight - v.max) / 1.5
              );
            },
          },
          tooltip: this.getTooltipParams(),
          series: [
            {
              ...this.options.series[0],
              ...this.getSymbolItemStyle(),
              ...this.getSeriesStyle(),
              data: this.data.map(item => ({
                value: [item[1], item[0]],
              })),
            },
          ],
        };
        this.setMarkPointData(false);
        this.$nextTick(() => {
          (this as any).instance = echarts.init(this.chartRef);
          (this as any).instance.setOption(this.options);
          this.seriesHandleEvents();
          this.otherInitFn();
          if (this.groupId) {
            (this as any).instance.group = this.groupId;
          }
        });
      }, 100);
    }
  }

  /**
   * @description 获取鼠标悬停标记点样式
   * @returns
   */
  getSymbolItemStyle() {
    return {
      symbol: 'none',
      symbolSize: 8,
      showSymbol: false,
      itemStyle: {
        color: '#7B29FF',
        borderColor: '#DBC5FF',
        borderWidth: 1,
      },
    };
  }

  /**
   * @description 获取折线与面积样式
   * @returns
   */
  getSeriesStyle() {
    return {
      lineStyle: {
        color: '#3A84FF',
        width: 1,
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          {
            offset: 0,
            color: '#A4C6FD',
          },
          {
            offset: 1,
            color: '#FFFFFF',
          },
        ]),
      },
    };
  }

  /**
   * @description 设置标记点数据
   * @param needSetOption
   */
  setMarkPointData(needSetOption = true) {
    const markPointData = [];
    const seriesData = this.options.series[0].data || [];
    if (this.showLastMarkPoint && seriesData.length) {
      let lastItem = seriesData[seriesData.length - 1];
      for (let i = seriesData.length - 1; i >= 0; i--) {
        if (typeof lastItem.value[1] !== 'number' && typeof seriesData[i].value[1] === 'number') {
          lastItem = seriesData[i];
          break;
        }
      }
      const valueFormatter = getValueFormat(this.unit);
      const valueItem = valueFormatter(lastItem.value[1], this.unitDecimal);
      this.lastValue = `${valueItem.text}${valueItem.suffix}`;
      markPointData.push({
        coord: [lastItem.value[0], lastItem.value[1]],
        symbol: 'circle',
        symbolSize: 6,
        itemStyle: {
          color: '#fff',
          borderColor: '#699DF4',
          borderWidth: 2,
        },
      });
    }
    this.options = {
      ...this.options,
      series: [
        {
          ...this.options.series[0],
          ...this.getSymbolItemStyle(),
          ...this.getSeriesStyle(),
          markPoint: {
            animation: false,
            data: markPointData,
          },
        },
      ],
    };
    if (needSetOption) {
      (this as any).instance?.setOption(this.options);
    }
  }

  /**
   * @description 图表事件
   */
  seriesHandleEvents() {
    for (const event of ['mousemove', 'click']) {
      (this as any).instance.on(event, _params => {});
    }
  }

  /**
   * @description tooltip 配置
   * @returns
   */
  getTooltipParams() {
    return {
      ...this.options.tooltip,
      className: 'mini-time-series-chart-tooltip',
      formatter: params => {
        if (this.isMouseOver) {
          const valueText = getValueFormat(this.unit)(params[0].value[1] || 0, this.unitDecimal);
          return `<div>
          <div>${dayjs.tz(params[0].value[0]).format('YYYY-MM-DD HH:mm:ss')}</div>
          <div>${this.valueTitle}：${valueText.text}${valueText.suffix}</div>
        </div>`;
        }
        return undefined;
      },
    };
  }

  handleResize() {
    (this as any).instance?.resize?.();
  }

  /**
   * @description 其他附加的初始化动作
   */
  otherInitFn() {}

  /**
   * @description 鼠标移入图表
   */
  handleMouseover() {
    this.isMouseOver = true;
  }
  /**
   * @description 鼠标移出图表
   */
  handleMouseleave() {
    this.isMouseOver = false;
  }

  handleClick() {}
  handleMouseDown() {}
  handleMouseMove() {}
  handleMouseUp() {}

  render() {
    return (
      <div class='mini-time-series-chart-wrap'>
        <div
          ref='chartInstance'
          style={{
            height: `${this.chartStyle.chartWarpHeight}px`,
          }}
          class={['mini-time-series-chart', { 'is-hover-point': this.hoverPoint.isHover }]}
          onClick={this.handleClick}
          onMousedown={this.handleMouseDown}
          onMouseleave={this.handleMouseleave}
          onMousemove={this.handleMouseMove}
          onMouseover={this.handleMouseover}
          onMouseup={this.handleMouseUp}
        />
        {this.showLastMarkPoint && this.lastValue ? (
          this.lastValueWidth ? (
            <span
              style={{
                'max-width': `${this.lastValueWidth}px`,
                'min-width': `${this.lastValueWidth}px`,
              }}
              class='last-value-overflow'
              v-bk-overflow-tips
            >
              {this.lastValue === 'undefined' ? '--' : this.lastValue}
            </span>
          ) : (
            <span class='last-value'>{this.lastValue === 'undefined' ? '--' : this.lastValue}</span>
          )
        ) : undefined}
      </div>
    );
  }
}
