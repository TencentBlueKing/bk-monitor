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
import { Component, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { toPng } from 'html-to-image';
import { deepClone, random } from 'monitor-common/utils';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import CollectionDialog from 'monitor-pc/pages/data-retrieval/components/collection-view-dialog';
// import ViewDetail from 'monitor-pc/pages/view-detail/view-detail-new';
import { downFile } from 'monitor-ui/chart-plugins/utils';

import CheckViewDetail from '../components/check-view';
import DrillAnalysisView from './drill-analysis-view';
import NewMetricChart from './metric-chart';

import type { IMetricAnalysisConfig } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { ILegendItem, IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './layout-chart-table.scss';
interface IDragInfo {
  height: number;
  maxHeight: number;
  minHeight: number;
}
interface ILayoutChartTableEvents {
  onDrillDown?: void;
  onResize?: number;
}
/** 图表 + 表格，支持拉伸 */
interface ILayoutChartTableProps {
  config?: IMetricAnalysisConfig;
  drag?: IDragInfo;
  groupId?: string;
  height?: number;
  isShowStatisticalValue?: boolean;
  isToolIconShow?: boolean;
  minHeight?: number;
  panel?: IPanelModel;
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
  /** groupId */
  @Prop({ default: '' }) groupId: string;
  // @Prop({ default: 600 }) height: number;
  @Prop({ default: 300 }) minHeight: number;
  @Ref('layoutMain') layoutMainRef: HTMLDivElement;
  @InjectReactive('filterOption') readonly filterOption!: IMetricAnalysisConfig;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @Ref('metricChart') metricChartRef: HTMLDivElement;
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
  currentMethod = '';
  selectLegendInd = -1;
  /** 收藏到仪表盘 */
  showCollection = false;
  checkList = [];

  @Watch('panel', { immediate: true })
  handleFilterOptionChange(val) {
    if (val) {
      const { query_configs = [] } = val.targets[0];
      this.currentMethod = query_configs[0]?.metrics[0]?.method;
    }
  }
  @Watch('isShowStatisticalValue')
  handleIsShowStatisticalValueChange() {
    this.selectLegendInd = -1;
  }

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
    /** 是否需要默认打开维度下钻 */
    setTimeout(() => {
      if (this.$route.query.isViewDrillDown) {
        const panel = JSON.parse(sessionStorage.getItem('BK_MONITOR_DRILL_PANEL'));
        panel && this.handelDrillDown(panel, 0);
        const { isViewDrillDown, ...rest } = this.$route.query;
        this.$router.replace({
          query: {
            ...rest,
            key: `${Date.now()}`,
          },
        });
      }
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
  /** 处理相关过滤条件的格式 */
  handleFilterData(filter) {
    const concatFilter = {};
    Object.keys(filter || {}).map(key => {
      concatFilter[`${key}__eq`] = [filter[key]];
    });
    return concatFilter;
  }
  /** 维度下钻 */
  handelDrillDown(chart: IPanelModel, ind: number) {
    this.showDrillDown = true;
    (chart.targets[ind]?.query_configs || []).map(item => {
      const { common_filter = {}, group_filter = {}, panel_filter = {} } = item.filter_dict;
      const concatFilter = this.handleFilterData(group_filter);
      const panelFilter = this.handleFilterData(panel_filter);
      item.filter_dict.concat_filter = { ...common_filter, ...concatFilter, ...panelFilter };
    });
    this.currentChart = {
      ...chart,
      groupId: null, // 去除当前的group_id
      targets: [chart.targets[ind]],
    };
  }
  /** 查看大图里面的右键维度下钻 */
  contextMenuClick(panel: IPanelModel) {
    sessionStorage.setItem('BK_MONITOR_DRILL_PANEL', JSON.stringify(panel));
    const routeData = this.$router.resolve({
      name: 'custom-escalation-view',
      query: { ...this.$route.query, isViewDrillDown: true, key: `${Date.now()}` },
    });
    window.open(routeData.href, '_blank');
  }
  handleLegendData(list: ILegendItem[], loading: boolean) {
    this.tableList = list;
    this.loading = loading;
  }

  deepCloneWithTargetProcessing(config: IPanelModel): IPanelModel {
    const clonedConfig = deepClone(config);
    clonedConfig.targets = clonedConfig.targets.map(target => {
      return {
        ...target,
        function: {
          ...target.function,
          time_compare: (target.function.time_compare || []).slice(0, 1),
        },
      };
    });
    return clonedConfig;
  }

  /**
   * @description: 查看大图
   * @param {boolean} loading
   */
  handleFullScreen(config: IPanelModel, compareValue?: any) {
    this.showViewDetail = true;
    let newFilterOption = deepClone(this.filterOption);
    if (this.filterOption.compare) {
      const { offset, type } = this.filterOption.compare;
      newFilterOption = {
        ...this.filterOption,
        compare: {
          ...this.filterOption.compare,
          offset: offset.slice(0, 1),
          type: type === 'metric' ? '' : type,
        },
      };
    }

    this.viewQueryConfig = {
      config: this.deepCloneWithTargetProcessing(config),
      compareValue: deepClone({ ...this.compareValue, ...compareValue }),
      filterOption: newFilterOption,
    };
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
  /** 下载图片到本地 */
  handleDownImage(title: string, targetEl?: HTMLElement, customSave = false) {
    let el = this.$el as HTMLElement;
    if (!this.isShowStatisticalValue) {
      el = targetEl || (this.$el as HTMLElement);
    } else {
      el = el.querySelector('.layout-chart-table-main') as HTMLElement;
    }
    return toPng(el)
      .then(dataUrl => {
        if (customSave) return dataUrl;
        downFile(dataUrl, `${title}.png`);
      })
      .catch(() => {});
  }

  isNullOrUndefined(value: any) {
    return value === undefined || value === null ? '--' : value;
  }
  /** 点击表格的图例，与图表联动 */
  handleRowClick(item, index) {
    this.selectLegendInd = this.selectLegendInd === index ? -1 : index;
    this.metricChartRef?.handleSelectLegend({ actionType: 'click', item });
  }
  /**
   * @description: 点击保存仪表盘
   * @param {PanelModel} panel 视图配置
   * @return {*}
   */
  handleCollectChart() {
    this.showCollection = true;
    const panel = deepClone(this.panel);
    panel.targets.map(item => {
      item.data = { ...item };
    });
    this.checkList = [panel];
  }

  handleShowCollectEmit(v: boolean) {
    this.showCollection = v;
  }

  // 收藏成功
  handleCollectSuccess() {
    // this.handleCheckClose();
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
            default: ({ row, $index }) => (
              <span
                class={`color-name ${this.selectLegendInd >= 0 && this.selectLegendInd !== $index ? 'disabled' : ''}`}
                onClick={() => this.handleRowClick(row, $index)}
              >
                <span
                  style={{ backgroundColor: row.color }}
                  class='color-box'
                  title={row.tipsName}
                />
                {row.tipsName}
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
                {this.isNullOrUndefined(row.max)}
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
                {this.isNullOrUndefined(row.min)}
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
                {this.isNullOrUndefined(row.latest)}
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
            default: ({ row }) => this.isNullOrUndefined(row.avg),
          }}
          label={this.$t('平均值')}
          prop='avg'
          show-overflow-tooltip
          sortable
        />
        <bk-table-column
          width={80}
          scopedSlots={{
            default: ({ row }) => this.isNullOrUndefined(row.total),
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
        ref='metricChart'
        style={{ height: `${this.drag.height}px` }}
        chartHeight={this.drag.height}
        currentMethod={this.currentMethod}
        // isShowLegend={true}
        groupId={this.groupId}
        isShowLegend={!this.isShowStatisticalValue}
        isToolIconShow={this.isToolIconShow}
        panel={this.panel}
        onCollectChart={this.handleCollectChart}
        onDownImage={this.handleDownImage}
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
              style={{ height: `${this.drag.height - 20}px` }}
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
          <div class='drag-btn' />
        </div>
        {this.showDrillDown && (
          <DrillAnalysisView
            currentMethod={this.currentMethod}
            panel={this.currentChart}
            timeRangeData={this.timeRange}
            onClose={() => (this.showDrillDown = false)}
          />
        )}
        {/* 全屏查看大图 */}
        {this.showViewDetail && (
          <CheckViewDetail
            currentMethod={this.currentMethod}
            panel={this.viewQueryConfig}
            timeRangeData={this.timeRange}
            onClose={() => (this.showViewDetail = false)}
            onContextMenuClick={this.contextMenuClick}
          />
        )}
        {/* 收藏到仪表盘 */}
        <CollectionDialog
          collectionList={this.checkList}
          isShow={this.showCollection}
          onOnCollectionSuccess={() => this.handleCollectSuccess}
          onShow={(v: boolean) => this.handleShowCollectEmit(v)}
        />
      </div>
    );
  }
}
