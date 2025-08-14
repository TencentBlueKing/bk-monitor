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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type MonitorEchartOptions, type ZrClickEvent, echarts } from '../typings/index';
import { getTimeSeriesXInterval } from '../utils/axis';

import type { IDataItem } from './apm-service-caller-callee/type';

import './base-echart.scss';

export interface IChartEvent {
  // click 事件
  onClick: MouseEvent;
  // dblclick 事件
  onDblClick: MouseEvent;
  /** mousemove事件  */
  onMousemove: MouseEvent;
  onBrush?: (v: any) => void;
  onBrushEnd?: (v: any) => void;
  // contextmenu 事件
  onContextmenu?: (v: any) => void;
  onLoaded?: () => void;
  /** 图表鼠标右击事件的回调方法 */
  onMenuClick?: (data: IDataItem) => void;
  // mouseout 事件
  onMouseout: () => void;
  // mouseover 事件
  onMouseover: () => void;
  onUpdateAxisPointer?: (v: any) => void;
  onZrClick: (p: ZrClickEvent) => void;
}
export interface IChartProps {
  // 视图高度
  height: number;
  // hover是显示所有图标tooltips
  hoverAllTooltips?: boolean;
  // 禁用右键菜单默认事件
  isContextmenuPreventDefault?: boolean;
  notMerge?: boolean;
  // echart 配置
  options: MonitorEchartOptions;
  toolbox?: string[];
  // 视图宽度 默认撑满父级
  width?: number;
}
const MOUSE_EVENTS = [
  'click',
  'dblclick',
  'mouseover',
  'mousemove',
  'mouseout',
  'mousedown',
  'mouseup',
  'globalout',
  'contextmenu',
  'updateAxisPointer',
  'showTip',
  'hideTip',
  'brushEnd',
  'brush',
  'brushselected',
];
@Component
export default class BaseChart extends tsc<IChartProps, IChartEvent> {
  @Ref('chartInstance') chartRef: HTMLDivElement;
  // echart 配置
  @Prop({ required: true }) options: MonitorEchartOptions;
  // 视图高度
  @Prop({ required: true }) height: number;
  // 视图宽度 默认撑满父级
  @Prop() width: number;
  // 禁用右键菜单默认事件
  @Prop({ default: false }) isContextmenuPreventDefault: boolean;
  @Prop({ default: true }) notMerge: boolean;
  @Prop({ default: () => ['dataZoom'] }) toolbox: string[];
  // 当前图表配置
  // curChartOption: MonitorEchartOptions = null;
  // // echarts 实例
  // instance: echarts.ECharts = null;
  // 当前图表配置取消监听函数
  unwatchOptions: () => void = null;
  // dblclick模拟 间隔
  clickTimer = null;
  // 当前视图是否hover
  isMouseOver = false;

  @Watch('height')
  handleHeightChange(h: number) {
    const instance = (this as any).instance;
    const height = instance?.getHeight() || 0;
    if (!height || Math.abs(height - h) < 1) return;
    if (this.height < 200) {
      instance?.setOption({
        yAxis: {
          splitNumber: 2,
          scale: false,
        },
      });
    }
    instance?.resize({
      silent: true,
    });
  }
  @Watch('width')
  handleWidthChange(v: number) {
    const instance = (this as any).instance;
    const width = instance?.getWidth() || 0;
    if (!width || Math.abs(width - v) < 1) return;
    const instanceOptions = instance.getOption();
    const { maxXInterval, maxSeriesCount } = instanceOptions?.customData || {};
    const xInterval = getTimeSeriesXInterval(maxXInterval, v, maxSeriesCount);
    if (instanceOptions.series?.[0]?.type !== 'pie') {
      instance?.setOption({
        xAxis: {
          ...xInterval,
        },
      });
    }
    instance?.resize({
      silent: true,
    });
  }
  mounted() {
    this.initChart();
  }
  activated() {
    this.resize();
  }
  beforeDestroy() {
    this.destroy();
  }

  // 初始化视图
  initChart() {
    if (!(this as any).instance) {
      (this as any).instance = echarts.init(this.chartRef);
      (this as any).instance.setOption(this.options);
      this.initPropsWatcher();
      this.initChartAction();
      this.$emit('loaded');
    }
  }
  // resize
  resize(options: MonitorEchartOptions = null) {
    this.chartRef && this.delegateMethod('resize', options);
  }
  // 派发action
  dispatchAction(payload) {
    this.delegateMethod('dispatchAction', payload);
  }
  // 派发method
  delegateMethod(name: string, ...args) {
    return (this as any).instance?.[name]?.(...args);
  }
  // 派发get
  delegateGet(methodName: string) {
    return (this as any).instance[methodName]();
  }
  // 初始化Props监听
  initPropsWatcher() {
    this.unwatchOptions = this.$watch(
      'options',
      v => {
        this.initChart();
        (this as any).instance.setOption(v, { notMerge: this.notMerge, lazyUpdate: false, silent: true });
        (this as any).curChartOption = (this as any).instance.getOption();
      },
      { deep: false }
    );
  }
  // 初始化chart Action
  initChartAction() {
    if (this.toolbox.includes('dataZoom')) {
      this.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true,
      });
    }
    if (this.toolbox.includes('brush')) {
      this.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'brush',
        brushOption: {
          brushType: 'lineX', // 指定选框类型
        },
      });
    }
  }
  initChartEvent() {
    this.chartRef.addEventListener('contextmenu', this.handleContextmenu);
    for (const event of MOUSE_EVENTS) {
      (this as any).instance.on(event, params => {
        if ('updateAxisPointer' === event) {
          if (this.isMouseOver) {
            this.$emit(event, params);
          }
        } else {
          this.$emit(event, params);
        }
      });
    }
  }
  // echarts 实例销毁
  destroy() {
    this.delegateMethod('dispose');
    (this as any).instance = null;
    this.isMouseOver = false;
  }
  handleMouseover() {
    this.isMouseOver = true;
  }
  handleMouseleave() {
    this.isMouseOver = false;
  }
  handleContextmenu(event) {
    if (this.isContextmenuPreventDefault) {
      event.preventDefault();
      this.dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: false,
      });
    }
  }
  render() {
    return (
      <div
        ref='chartInstance'
        style={{ minHeight: `${1}px` }}
        class='chart-base'
        onMouseleave={this.handleMouseleave}
        onMouseover={this.handleMouseover}
      />
    );
  }
}
