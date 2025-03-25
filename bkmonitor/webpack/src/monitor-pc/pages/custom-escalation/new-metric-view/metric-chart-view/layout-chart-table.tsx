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

import dayjs from 'dayjs';
import { random } from 'monitor-common/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import ViewDetail from 'monitor-pc/pages/view-detail/view-detail-new';

import DrillAnalysisView from './drill-analysis-view';
import NewMetricChart from './metric-chart';

import type { IMetricAnalysisConfig } from '../type';
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
  isShowStatisticalValue?: boolean;
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
  @Prop({ default: true }) isShowStatisticalValue: boolean;
  // @Prop({ default: 600 }) height: number;
  @Prop({ default: 372 }) minHeight: number;
  @Ref('layoutMain') layoutMainRef: HTMLDivElement;
  @InjectReactive('filterOption') readonly filterOption!: IMetricAnalysisConfig;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  /* 主动刷新图表 */
  chartKey = random(8);
  isDragging = false;
  mouseDownY = 0;
  offset = 0;
  tableList: ILegendItem[] = [];
  loading = true;
  /** 是否展示维度下钻view */
  showDrillDown = false;
  showViewDetail = false;
  /** 查看大图参数配置 */
  viewQueryConfig = {};
  currentChart = {};
  currentMethod = 'SUM';

  /** 对比工具栏数据 */
  get compareValue() {
    const { compare } = this.filterOption;
    return {
      compare: {
        type: compare?.type,
        value: compare?.offset,
      },
      tools: {
        timeRange: this.timeRange,
        searchValue: [],
      },
    };
  }
  mounted() {
    document.addEventListener('mousemove', this.handleMouseMove);
    document.addEventListener('mouseup', this.stopDragging);

    this.$once('hook:beforeDestroy', () => {
      document.removeEventListener('mousemove', this.handleMouseMove);
      document.removeEventListener('mouseup', this.stopDragging);
    });
  }

  //  支持上下拖拽
  handleResizing(height: number) {
    this.drag.height = height;
    // this.chartKey = random(8);
  }
  startDragging(e: MouseEvent) {
    this.isDragging = true;
    this.mouseDownY = e.clientY;
    this.offset = this.layoutMainRef.getBoundingClientRect().height;
  }
  handleMouseMove(e: MouseEvent) {
    if (!this.isDragging) return;
    const newHeight = Math.max(e.clientY - this.mouseDownY + this.offset, this.minHeight);

    Array.from(this.layoutMainRef.parentElement.parentElement.children).forEach((itemEl: HTMLElement) => {
      itemEl.style.height = `${newHeight}px`;
    });
  }
  /** 停止拉伸 */
  stopDragging() {
    this.isDragging = false;
  }
  /** 维度下钻 */
  handelDrillDown(chart: IPanelModel, ind: number) {
    this.showDrillDown = true;
    this.currentChart = {
      ...chart,
      targets: [chart.targets[ind]],
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

  handleMethodChange(method: string) {
    this.panel.targets.map(item => {
      (item.query_configs || []).map(config => {
        (config.metrics || []).map(metric => (metric.method = method));
      });
    });
    this.currentMethod = method;
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
        <bk-table-column
          scopedSlots={{
            default: ({ row }) => (
              <span class='color-name'>
                <span
                  style={{ backgroundColor: row.color }}
                  class='color-box'
                  title={row.name}
                />
                {row.name}
              </span>
            ),
          }}
          class-name='indicator-name-column'
          fixed='left'
          label=''
          min-width={150}
          prop='name'
          show-overflow-tooltip={true}
        />
        <bk-table-column
          scopedSlots={{
            default: ({ row }) => (
              <span class='num-cell'>
                {row.max || '--'}
                <span class='gray-text'>@{dayjs(row.maxTime).format('HH:mm')}</span>
              </span>
            ),
          }}
          label={this.$t('最大值')}
          min-width={120}
          prop='max'
          show-overflow-tooltip
          sortable
        />
        <bk-table-column
          scopedSlots={{
            default: ({ row }) => (
              <span class='num-cell'>
                {row.min || '--'}
                <span class='gray-text'>@{dayjs(row.minTime).format('HH:mm')}</span>
              </span>
            ),
          }}
          label={this.$t('最小值')}
          min-width={120}
          prop='min'
          show-overflow-tooltip
          sortable
        />
        <bk-table-column
          scopedSlots={{
            default: ({ row }) => (
              <span class='num-cell'>
                {row.latest || '--'}
                <span class='gray-text'>@{dayjs(row.latestTime).format('HH:mm')}</span>
              </span>
            ),
          }}
          label={this.$t('最新值')}
          min-width={120}
          prop='latest'
          show-overflow-tooltip
          sortable
        />
        <bk-table-column
          width={80}
          scopedSlots={{
            default: ({ row }) => row.avg || '--',
          }}
          label={this.$t('平均值')}
          prop='avg'
          show-overflow-tooltip
          sortable
        />
        <bk-table-column
          width={80}
          scopedSlots={{
            default: ({ row }) => row.total || '--',
          }}
          label={this.$t('累计值')}
          prop='total'
          show-overflow-tooltip
          sortable
        />
        <div slot='empty'>{this.$t('暂无数据')}</div>
      </bk-table>
    );
  }

  render() {
    const renderChart = () => (
      <NewMetricChart
        key={this.chartKey}
        style={{ height: `${this.drag.height}px` }}
        chartHeight={this.drag.height}
        currentMethod={this.currentMethod}
        isToolIconShow={this.isToolIconShow}
        panel={this.panel}
        onDrillDown={this.handelDrillDown}
        onFullScreen={this.handleFullScreen}
        onLegendData={this.handleLegendData}
        onMethodChange={this.handleMethodChange}
      />
    );
    return (
      <div
        ref='layoutMain'
        style={{ 'user-select': this.isDragging ? 'none' : 'auto' }}
        class='layout-chart-table'
      >
        {this.isShowStatisticalValue ? (
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
            <div slot='aside'>{renderChart()}</div>
            <div
              class='main-table'
              slot='main'
            >
              {this.renderIndicatorTable()}
            </div>
          </bk-resize-layout>
        ) : (
          <div class='main-chart'>{renderChart()}</div>
        )}

        <div
          class='layout-dragging'
          onMousedown={this.startDragging}
        >
          <div class='drag-btn'></div>
        </div>
        {this.showDrillDown && (
          <DrillAnalysisView
            currentMethod={this.currentMethod}
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
