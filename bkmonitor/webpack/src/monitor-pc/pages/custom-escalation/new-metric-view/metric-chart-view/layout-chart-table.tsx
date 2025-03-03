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
import { Component, Ref, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import NewMetricChart from './metric-chart';

import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './layout-chart-table.scss';
interface IDragInfo {
  height: number;
  minHeight: number;
  maxHeight: number;
}
/** 图表 + 表格，支持拉伸 */
interface ILayoutChartTableProps {
  drag?: IDragInfo;
  isToolIconShow?: boolean;
  height?: number;
  minHeight?: number;
  panel?: PanelModel;
}
interface ILayoutChartTableEvents {
  onResize?: number;
  onDrillDown?: void;
}
@Component
export default class LayoutChartTable extends tsc<ILayoutChartTableProps, ILayoutChartTableEvents> {
  // 图表panel实例
  @Prop({ default: false }) readonly panel: PanelModel;
  /* 拖拽数据 */
  @Prop({ default: () => ({ height: 300, minHeight: 180, maxHeight: 400 }) }) drag: IDragInfo;
  @Prop({ default: true }) isToolIconShow: boolean;
  @Prop({ default: 600 }) height: number;
  @Prop({ default: 500 }) minHeight: number;
  @Ref('layoutMain') layoutMainRef: HTMLDivElement;
  /* 主动刷新图表 */
  chartKey = random(8);
  divHeight = 0;
  resizeObserver = null;
  isDragging = false;
  mouseDownY = 0;
  offset = 0;
  parentHeight = 600;

  mounted() {
    this.$nextTick(() => {
      if (this.layoutMainRef) {
        // 初始化 ResizeObserver
        this.resizeObserver = new ResizeObserver(entries => {
          for (const entry of entries) {
            this.divHeight = entry.contentRect.height;
          }
        });
        // 观察目标元素
        this.resizeObserver.observe(this.layoutMainRef);
      }
    });
    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.stopDragging);
  }
  beforeDestroy() {
    document.removeEventListener('mousemove', this.handleMouseMove);
    document.removeEventListener('mouseup', this.stopDragging);
  }

  beforeUnmount() {
    // 销毁观察器
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
  }
  //  支持上下拖拽
  handleResizing(height) {
    this.drag.height = height;
    this.chartKey = random(8);
  }
  startDragging(e) {
    this.isDragging = true;
    this.mouseDownY = e.clientY;
    this.offset = this.parentHeight;
  }
  handleMouseMove(e) {
    if (!this.isDragging) return;
    const newHeight = e.clientY - this.mouseDownY + this.offset;
    if (newHeight > 0 && newHeight > this.minHeight) {
      // 设置高度的最小值
      this.parentHeight = newHeight;
      this.$emit('resize', newHeight);
    }
  }
  /** 停止拉伸 */
  stopDragging() {
    this.isDragging = false;
  }
  /** 维度下钻 */
  handelDrillDown() {
    this.$emit('drillDown');
  }
  render() {
    return (
      <div
        ref='layoutMain'
        style={{ height: this.height + 'px' }}
        class='layout-chart-table'
      >
        <bk-resize-layout
          extCls='layout-chart-table-main'
          slot='aside'
          border={false}
          initial-divide={'50%'}
          max={this.drag.maxHeight}
          min={this.drag.minHeight}
          placement='top'
          onResizing={this.handleResizing}
        >
          <div
            class='main-chart'
            slot='aside'
          >
            <NewMetricChart
              key={this.chartKey}
              style={{ height: `${this.drag.height - 30}px` }}
              chartHeight={this.drag.height}
              isToolIconShow={this.isToolIconShow}
              panel={this.panel}
              onDrillDown={this.handelDrillDown}
            />
          </div>
          <div
            style={{ height: `${this.divHeight - this.drag.height}px` }}
            class='main-table'
            slot='main'
          >
            {this.$slots?.default}
          </div>
        </bk-resize-layout>
        <div
          class='layout-dragging'
          onMousedown={this.startDragging}
        >
          {/* <i
            style='margin-top: -2px; height: 5px;'
            class='resize-trigger'
          ></i>
          <i
            style='visibility: hidden; inset: 183px auto auto 0px;'
            class='resize-proxy top'
          ></i> */}
          <div class='drag-btn'></div>
        </div>
      </div>
    );
  }
}
