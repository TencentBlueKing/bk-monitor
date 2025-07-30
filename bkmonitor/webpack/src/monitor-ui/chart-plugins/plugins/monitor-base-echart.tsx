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
import { Component, Prop } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { hexToRgbA } from 'monitor-common/utils/utils';

import { type MonitorEchartOptions, echarts } from '../typings/index';
import BaseEchart, { type IChartEvent, type IChartProps } from './base-echart';

import type { ICurPoint } from '../typings';

import './base-echart.scss';
interface IBaseEvent extends IChartEvent {
  onDataZoom: (start_time: string, end_time: string) => void;
  // 复位事件
  onRestore: () => void;
}
interface IBaseProps extends IChartProps {
  groupId?: string;
  needMenuClick?: boolean;
  needTooltips?: boolean;
  needZrClick?: boolean;
  showRestore?: boolean;
  sortTooltipsValue?: boolean;
  customTooltips?: (v: any) => string; // 自定义tooltip内容
  tooltipsContentLastItemFn?: (v: any) => string;
}
@Component
class MonitorBaseEchart extends BaseEchart {
  // echarts图表实例分组id
  @Prop({ type: String, default: '' }) groupId: string;
  @Prop({ type: Boolean, default: false }) showRestore: boolean;
  @Prop({ type: Boolean, default: false }) hoverAllTooltips: boolean;
  // 是否需要排序tooltip内容
  @Prop({ type: Boolean, default: true }) sortTooltipsValue: boolean;
  @Prop({ type: Boolean, default: true }) needTooltips: boolean;
  @Prop({ type: Boolean, default: false }) needZrClick: boolean;
  /** 是否需要图表的鼠标右击事件 */
  @Prop({ type: Boolean, default: false }) needMenuClick: boolean;
  /* tooltips内容最后一项格式化函数 */
  @Prop({ type: Function, default: null }) tooltipsContentLastItemFn: (v: any) => string;
  @Prop({ type: Function, default: null }) customTooltips: (v: any) => string; // 自定义tooltip内容
  // hover视图上 当前对应最近点数据
  curPoint: ICurPoint = { xAxis: '', yAxis: '', dataIndex: -1, color: '', name: '', seriesIndex: -1 };
  // tooltips大小 [width, height]
  tooltipSize: number[];
  // tableToolSize
  tableToolSize = 0;
  getMonitorEchartOptions(): MonitorEchartOptions {
    return Object.freeze(
      deepmerge(
        {
          tooltip: {
            axisPointer: {
              type: 'cross',
              axis: 'auto',
              label: {
                show: false,
                formatter: params => {
                  if (params.axisDimension === 'y') {
                    this.curPoint.yAxis = params.value;
                  } else {
                    this.curPoint.xAxis = params.value;
                    this.curPoint.dataIndex = params.seriesData?.length ? params.seriesData[0].dataIndex : -1;
                  }
                },
              },
              crossStyle: {
                color: 'transparent',
                opacity: 0,
                width: 0,
              },
            },
            appendToBody: true,
            formatter: p => this.handleSetTooltip(p),
            position: (pos, params, dom, rect, size: any) => {
              const { contentSize } = size;
              const chartRect = this.$el.getBoundingClientRect();
              const posRect = {
                x: chartRect.x + +pos[0],
                y: chartRect.y + +pos[1],
              };
              const position = {
                left: 0,
                top: 0,
              };
              const canSetBottom = window.innerHeight - posRect.y - contentSize[1];
              if (canSetBottom > 0) {
                position.top = +pos[1] - Math.min(20, canSetBottom);
              } else {
                position.top = +pos[1] + canSetBottom - 20;
              }
              const canSetLeft = window.innerWidth - posRect.x - contentSize[0];
              if (canSetLeft > 0) {
                position.left = +pos[0] + Math.min(20, canSetLeft);
              } else {
                position.left = +pos[0] - contentSize[0] - 20;
              }
              if (contentSize[0]) this.tooltipSize = contentSize;
              return {
                left: position.left,
                top: position.top < -chartRect.y ? -chartRect.y : position.top,
              };
            },
          },
        },
        this.options
      )
    );
  }
  initChart() {
    if (!(this as any).instance) {
      setTimeout(() => {
        if (!this.chartRef) return;
        (this as any).instance = echarts.init(this.chartRef);
        (this as any).instance.setOption(this.getMonitorEchartOptions());
        this.initPropsWatcher();
        this.initChartEvent();
        this.initChartAction();
        (this as any).curChartOption = (this as any).instance.getOption();
        this.groupId && ((this as any).instance.group = this.groupId);
        (this as any).instance.on('dataZoom', this.handleDataZoom);
        if (this.needMenuClick) {
          (this as any).instance.on('contextmenu', params => {
            /** 返回当前鼠标右击选择图表的数据下标 */
            this.$emit('menuClick', {
              dataIndex: params.dataIndex,
            });
          });
        }
        if (this.needZrClick) {
          (this as any).instance.getZr().on('click', params => {
            const options = (this as any).instance.getOption();
            if (!options.series?.length) return;
            const pointInPixel = [params.offsetX, params.offsetY];
            const pointInGrid = (this as any).instance.convertFromPixel({ seriesIndex: 0 }, pointInPixel);
            if (!pointInGrid) return;
            const xAxisValue = this.curPoint.xAxis;
            const yAxisValue = pointInGrid[1];
            const dataIndex = this.curPoint.dataIndex;
            const data = options.series
              .map(s => ({
                v: s.data?.[dataIndex]?.value?.[1],
                s,
              }))
              .sort((a, b) => Math.abs(a.v - yAxisValue) - Math.abs(b.v - yAxisValue));
            this.$emit('zrClick', {
              xAxis: xAxisValue,
              yAxis: data[0].v,
              dimensions: data[0].s.dimensions,
            });
          });
        }
        this.$emit('loaded');
      }, 100);
    }
  }
  handleDataZoom(event) {
    const [batch] = event.batch;
    if (batch.startValue && batch.endValue) {
      const options: { series: { data: string[] }[] } = (this as any).instance?.getOption?.();
      if (options?.series?.length && options.series.every(item => item.data?.length < 2)) return;
      (this as any).instance.dispatchAction({
        type: 'restore',
      });
      const timeFrom = dayjs(+batch.startValue.toFixed(0)).format('YYYY-MM-DD HH:mm:ss');
      let timeTo = dayjs(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm:ss');
      if (!this.isMouseOver) {
        const seriesData = this.getMonitorEchartOptions()?.series?.[0]?.data || [];
        if (seriesData.length) {
          const maxX = (seriesData[seriesData.length - 1] as any)?.value?.[0] || 0;
          if (maxX === +batch.endValue.toFixed(0)) {
            timeTo = dayjs().format('YYYY-MM-DD HH:mm');
          }
        }
      }
      this.$emit('dataZoom', timeFrom, timeTo);
    }
    // if (this.isMouseOver) {
    //   const [batch] = event.batch;
    //   if (batch.startValue && batch.endValue) {
    //     (this as any).instance.dispatchAction({
    //       type: 'restore'
    //     });
    //     const timeFrom = dayjs(+batch.startValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
    //     const timeTo = dayjs(+batch.endValue.toFixed(0)).format('YYYY-MM-DD HH:mm');
    //     this.$emit('dataZoom', timeFrom, timeTo);
    //   }
    // } else {
    //   (this as any).instance.dispatchAction({
    //     type: 'restore'
    //   });
    // }
  }
  handleClickRestore(e: MouseEvent) {
    e.preventDefault();
    this.$emit('restore');
    // this.$emit('dataZoom');
  }
  // 初始化Props监听
  initPropsWatcher() {
    this.unwatchOptions = this.$watch(
      'options',
      () => {
        this.initChart();
        (this as any).instance.setOption(this.getMonitorEchartOptions(), {
          notMerge: this.notMerge,
          lazyUpdate: false,
          silent: true,
        });
        (this as any).curChartOption = (this as any).instance.getOption();
        this.initChartAction();
      },
      { deep: false }
    );
  }
  /**
   * @description: 设置echart的option
   * @param {MonitorEchartOptions} option
   */
  public setPartialOption(option: MonitorEchartOptions) {
    if ((this as any).instance) {
      (this as any).instance.setOption(option, { notMerge: false });
      (this as any).curChartOption = (this as any).instance.getOption();
    }
  }
  public handleTransformArea(isArea: boolean) {
    if ((this as any).instance) {
      const options = (this as any).instance.getOption();
      (this as any).instance.setOption({
        ...options,
        series: options.series.map((item, index) => ({
          ...item,
          areaStyle: {
            color: isArea ? hexToRgbA(options.color[index % options.color.length], 0.2) : 'transparent',
          },
        })),
      });
    }
  }
  public handleSetYAxisSetScale(needScale) {
    this.$emit('on-yaxis-set-scale', needScale);
    if ((this as any).instance) {
      const options = (this as any).instance.getOption();
      (this as any).instance.setOption({
        ...options,
        yAxis: {
          scale: needScale,
          min: needScale ? 'dataMin' : 0,
        },
      });
    }
  }
  isInViewPort() {
    const { top, bottom } = this.$el.getBoundingClientRect();
    return (top > 0 && top <= innerHeight) || (bottom >= 0 && bottom < innerHeight);
  }
  // 设置tooltip
  handleSetTooltip(params) {
    if (!this.needTooltips) {
      return undefined;
    }
    if (!this.isMouseOver && !this.hoverAllTooltips) return undefined;
    if (!params || params.length < 1 || params.every(item => item.value[1] === null)) {
      this.curPoint = {
        color: '',
        name: '',
        seriesIndex: -1,
        dataIndex: -1,
        xAxis: '',
        yAxis: '',
      };
      return;
    }
    if (!this.isInViewPort()) {
      return;
    }
    let liHtmlList = [];
    let ulStyle = '';
    let hasWrapText = true;
    let pointTime = '';
    try {
      pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
    } catch {}

    if (params[0]?.data?.tooltips) {
      liHtmlList.push(params[0].data.tooltips);
    } else {
      if (typeof this.customTooltips === 'function') {
        return this.customTooltips(params);
      }
      const data = params
        .map(item => ({ color: item.color, seriesName: item.seriesName, value: item.value[1] }))
        .sort((a, b) => Math.abs(a.value - +this.curPoint.yAxis) - Math.abs(b.value - +this.curPoint.yAxis));
      const list = params.filter(item => !item.seriesName.match(/-no-tips$/));
      liHtmlList = (this.sortTooltipsValue ? list.sort((a, b) => b.value[1] - a.value[1]) : list).map(item => {
        let markColor = 'color: #fafbfd;';
        if (data[0].value === item.value[1]) {
          markColor = 'color: #fff;font-weight: bold;';
          this.curPoint = {
            color: item.color,
            name: item.seriesName,
            seriesIndex: item.seriesIndex,
            dataIndex: item.dataIndex,
            xAxis: item.value[0],
            yAxis: item.value[1],
          };
        }
        if (item.value[1] === null) return undefined;
        let curSeries: any = (this as any).curChartOption.series[item.seriesIndex];
        if (curSeries?.stack?.includes('boundary-')) {
          curSeries = (this as any).curChartOption.series.find((item: any) => !item?.stack?.includes('boundary-'));
        }
        const unitFormatter = curSeries.unitFormatter || (v => ({ text: v }));
        const minBase = curSeries.minBase || 0;
        const precision =
          !['none', ''].some(val => val === curSeries.unit) && +curSeries.precision < 1 ? 2 : +curSeries.precision;
        const valueObj = unitFormatter(item.value[1] - minBase, precision);
        return `<li class="tooltips-content-item" style="--series-color: ${curSeries.lineStyle?.color || item.color}">
                  <span class="item-series is-${curSeries.lineStyle?.type}"
                   style="background-color:${curSeries.lineStyle?.color || item.color};">
                  </span>
                  <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                  <span class="item-value" style="${markColor}">
                  ${valueObj?.text} ${valueObj?.suffix || ''}</span>
                  </li>`;
      });
      if (liHtmlList?.length < 1) return undefined;
      // 如果超出屏幕高度，则分列展示
      const maxLen = Math.ceil((window.innerHeight - 100) / 20);
      if (list.length > maxLen && this.tooltipSize) {
        const cols = Math.ceil(list.length / maxLen);
        if (cols > 1) hasWrapText = false;
        this.tableToolSize = this.tableToolSize
          ? Math.min(this.tableToolSize, this.tooltipSize[0])
          : this.tooltipSize[0];
        ulStyle = `display:flex; flex-wrap:wrap; width: ${Math.min(5 + cols * this.tableToolSize, window.innerWidth / 2 - 20)}px;`;
      }
    }
    const lastItem = this.tooltipsContentLastItemFn?.(params);
    return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${pointTime}
            </p>
            <ul class="tooltips-content ${hasWrapText ? 'wrap-text' : ''}" style="${ulStyle}">
                ${liHtmlList?.join('')}
                ${lastItem || ''}
            </ul>
            </div>`;
  }
  render() {
    return (
      <div class='chart-base-wrap'>
        <div
          ref='chartInstance'
          style={{ minHeight: `${1}px` }}
          class='chart-base'
          onMouseleave={this.handleMouseleave}
          onMouseover={this.handleMouseover}
        />
        {this.showRestore && (
          <span
            class='chart-restore'
            onClick={this.handleClickRestore}
          >
            {this.$t('复位')}
          </span>
        )}
      </div>
    );
  }
}

export default ofType<IBaseProps, IBaseEvent>().convert(MonitorBaseEchart);
