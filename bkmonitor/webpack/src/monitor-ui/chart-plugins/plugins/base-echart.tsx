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
import echarts from 'echarts';

import './base-echart.scss';

export interface IChartProps {
  // 视图高度
  height: number;
  // 视图宽度 默认撑满父级
  width?: number;
  // echart 配置
  options: echarts.EChartOption;
}
export interface IChartEvent {
  // mouseover 事件
  onMouseover: void;
  // mouseout 事件
  onMouseout: void;
  // dblclick 事件
  onDblClick: MouseEvent;
  /** mousemove事件  */
  onMousemove: MouseEvent;
  // click 事件
  onClick: MouseEvent;
}
const MOUSE_EVENTS = ['click', 'dblclick', 'mouseover', 'mousemove', 'mouseout', 'mousedown', 'mouseup', 'globalout'];
@Component
export default class BaseChart extends tsc<IChartProps, IChartEvent> {
  @Ref('chartInstance') chartRef: HTMLDivElement;
  // echart 配置
  @Prop({ required: true }) options: echarts.EChartOption;
  // 视图高度
  @Prop({ required: true }) height: number;
  // 视图宽度 默认撑满父级
  @Prop() width: number;
  // 当前图表配置
  // curChartOption: echarts.EChartOption = null;
  // // echarts 实例
  // instance: echarts.ECharts = null;
  // 当前图表配置取消监听函数
  unwatchOptions: () => void = null;
  // dblclick模拟 间隔
  clickTimer = null;
  // 当前视图是否hover
  isMouseOver = false;

  @Watch('height')
  handleHeightChange() {
    if (this.height < 200) {
      (this as any).instance?.setOption({
        yAxis: {
          splitNumber: 2,
          scale: false
        }
      });
    }
    (this as any).instance?.resize({
      silent: true
    });
  }
  @Watch('width')
  handleWidthChange() {
    (this as any).instance?.setOption({
      xAxis: {
        splitNumber: Math.ceil(this.width / 150),
        min: 'dataMin'
      }
    });
    (this as any).instance?.resize({
      silent: true
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
    }
  }
  // resize
  resize(options: echarts.EChartOption = null) {
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
        (this as any).instance.setOption(v, { notMerge: true, lazyUpdate: false, silent: true });
        (this as any).curChartOption = (this as any).instance.getOption();
      },
      { deep: false }
    );
  }
  // 初始化chart Action
  initChartAction() {
    this.dispatchAction({
      type: 'takeGlobalCursor',
      key: 'dataZoomSelect',
      dataZoomSelectActive: true
    });
  }
  initChartEvent() {
    MOUSE_EVENTS.forEach(event => {
      (this as any).instance.on(event, params => {
        this.$emit(event, params);
      });
    });
  }
  // echarts 实例销毁
  destroy() {
    this.delegateMethod('dispose');
    (this as any).instance = null;
    this.isMouseOver = false;
  }
  handleDblClick(e: MouseEvent) {
    e.preventDefault();
    clearTimeout(this.clickTimer);
    this.$emit('dblClick', e);
  }
  handleClick(e: MouseEvent) {
    clearTimeout(this.clickTimer);
    this.clickTimer = setTimeout(() => {
      this.$emit('click', e);
    }, 300);
  }
  handleMouseover() {
    this.isMouseOver = true;
  }
  handleMouseleave() {
    this.isMouseOver = false;
  }
  render() {
    return (
      <div
        class='chart-base'
        ref='chartInstance'
        style={{ minHeight: `${1}px` }}
        onMouseover={this.handleMouseover}
        onMouseleave={this.handleMouseleave}
        onClick={this.handleClick}
        onDblclick={this.handleDblClick}
      />
    );
  }
}
