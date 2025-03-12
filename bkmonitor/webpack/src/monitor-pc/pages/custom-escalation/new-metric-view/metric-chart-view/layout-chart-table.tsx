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
import { Component, Ref, Prop, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import ViewDetail from 'monitor-pc/pages/view-detail/view-detail-new';

import DrillAnalysisView from './drill-analysis-view';
import NewMetricChart from './metric-chart';

import type { IColumnItem, IDataItem, IMetricAnalysisConfig } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IPanelModel, ILegendItem } from 'monitor-ui/chart-plugins/typings';

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
  panel?: IPanelModel;
  config?: IMetricAnalysisConfig;
}
interface ILayoutChartTableEvents {
  onResize?: number;
  onDrillDown?: void;
}
@Component
export default class LayoutChartTable extends tsc<ILayoutChartTableProps, ILayoutChartTableEvents> {
  // 相关配置
  @Prop({ default: () => ({}) }) config: IMetricAnalysisConfig;
  // 图表panel实例
  @Prop({ default: () => ({}) }) panel: IPanelModel;
  /* 拖拽数据 */
  @Prop({ default: () => ({ height: 300, minHeight: 180, maxHeight: 400 }) }) drag: IDragInfo;
  @Prop({ default: true }) isToolIconShow: boolean;
  @Prop({ default: 600 }) height: number;
  @Prop({ default: 500 }) minHeight: number;
  @Ref('layoutMain') layoutMainRef: HTMLDivElement;
  @InjectReactive('filterOption') readonly filterOption!: IMetricAnalysisConfig;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  /* 主动刷新图表 */
  chartKey = random(8);
  divHeight = 0;
  resizeObserver = null;
  isDragging = false;
  mouseDownY = 0;
  offset = 0;
  parentHeight = 600;
  columnList = [
    { label: '', prop: 'max', renderFn: (row: IDataItem) => this.renderLegend(row) },
    { label: '最大值', prop: 'max' },
    { label: '最小值', prop: 'min' },
    { label: '最新值', prop: 'latest' },
    { label: '平均值', prop: 'avg' },
    { label: '累计值', prop: 'total' },
  ];
  tableList: ILegendItem[] = [];
  loading = true;
  /** 是否展示维度下钻view */
  showDrillDown = false;
  showViewDetail = false;
  /** 查看大图参数配置 */
  viewQueryConfig = {};
  currentChart = {};

  /** 对比工具栏数据 */
  get compareValue() {
    const { compare } = this.filterOption;
    return {
      compare: {
        type: compare.type,
        value: compare.offset,
      },
      tools: {
        timeRange: this.timeRange,
        searchValue: [],
      },
    };
  }
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
  renderLegend(row: IDataItem) {
    return (
      <span>
        <span
          style={{ backgroundColor: row.color }}
          class='color-box'
          title={row.name}
        />
        {row.name}
      </span>
    );
  }
  //  支持上下拖拽
  handleResizing(height: number) {
    this.drag.height = height;
    this.chartKey = random(8);
  }
  startDragging(e: MouseEvent) {
    this.isDragging = true;
    this.mouseDownY = e.clientY;
    this.offset = this.parentHeight;
  }
  handleMouseMove(e: MouseEvent) {
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
  handelDrillDown(chart: IPanelModel) {
    this.showDrillDown = true;
    this.currentChart = {
      ...chart,
      targets: [chart.targets[0]],
    };
  }
  handleLegendData(list: ILegendItem[], loading: boolean) {
    this.tableList = list;
    this.loading = loading;
  }

  /**
   * @description: 查看大图
   * @param {boolean} loading
   */
  handleFullScreen(config: IPanelModel, compareValue?: any) {
    this.viewQueryConfig = {
      config: JSON.parse(JSON.stringify(config)),
      compareValue: JSON.parse(JSON.stringify({ ...this.compareValue, ...compareValue })),
    };
    this.showViewDetail = true;
  }
  /**
   * @description: 关闭查看大图弹窗
   */
  handleCloseViewDetail() {
    this.showViewDetail = false;
    this.viewQueryConfig = {};
  }
  /** 表格渲染 */
  renderIndicatorTable() {
    if (this.loading) {
      return (
        <TableSkeleton
          class='table-view-empty-block'
          type={1}
        />
      );
    }
    return (
      <bk-table
        ext-cls='indicator-table'
        data={this.tableList}
        header-border={false}
        outer-border={false}
        stripe={true}
      >
        {this.columnList.map((item: IColumnItem, ind: number) => (
          <bk-table-column
            key={`${item.prop}_${ind}`}
            width={item.width}
            scopedSlots={{
              default: ({ row }) => {
                /** 自定义 */
                if (item?.renderFn) {
                  return item?.renderFn(row);
                }
                return <span title={row[item.prop]}>{row[item.prop] || '--'}</span>;
              },
            }}
            label={this.$t(item.label)}
            prop={item.prop}
            sortable={ind === 0 ? false : true}
          ></bk-table-column>
        ))}
      </bk-table>
    );
  }

  render() {
    return (
      <div
        ref='layoutMain'
        style={{ height: `${this.height}px` }}
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
              onFullScreen={this.handleFullScreen}
              onLegendData={this.handleLegendData}
            />
          </div>
          <div
            style={{ height: `${this.divHeight - this.drag.height}px` }}
            class='main-table'
            slot='main'
          >
            {this.renderIndicatorTable()}
          </div>
        </bk-resize-layout>
        <div
          class='layout-dragging'
          onMousedown={this.startDragging}
        >
          <div class='drag-btn'></div>
        </div>
        {this.showDrillDown && (
          <DrillAnalysisView
            panel={this.currentChart}
            onClose={() => (this.showDrillDown = false)}
          />
        )}
        {/* 全屏查看大图 */}
        {this.showViewDetail && (
          <ViewDetail
            show={this.showViewDetail}
            viewConfig={this.viewQueryConfig}
            on-close-modal={this.handleCloseViewDetail}
          />
        )}
      </div>
    );
  }
}
