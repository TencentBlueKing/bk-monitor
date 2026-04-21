/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { connect, disconnect } from 'echarts/core';
import { Debounce, random } from 'monitor-common/utils';
import { deepClone } from 'monitor-common/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

// import { getCustomTsGraphConfig } from '../../../../../service';
import { chunkArray } from '../../../../utils';
import LayoutChartTable from './components/layout-chart-table';

import type { ChartSettingsParams, IMetricAnalysisConfig, RequestHandlerMap } from '../../../../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './index.scss';

/** 图表 + 表格列表，支持拉伸 */
const DEFAULT_HEIGHT = 600;
interface IGroups {
  name: string;
  panels: IPanelModel[];
}
interface IPanelChartViewEvents {
  onLoadGraphConfigMetricIds?: (payload: { init: boolean; metricIds: (number | string)[] }) => void;
  onMetricManage?: (tab: 'dimension' | 'metric') => 'dimension' | 'metric';
}
interface IPanelChartViewProps {
  chartSettingParams?: ChartSettingsParams;
  config?: IMetricAnalysisConfig;
  showStatisticalValue?: boolean;
  viewColumn?: number;
}

@Component
export default class PanelChartView extends tsc<IPanelChartViewProps, IPanelChartViewEvents> {
  // 相关配置
  @Prop({ default: () => ({}) }) config: IMetricAnalysisConfig;

  @ProvideReactive('chartSettingParams')
  @Prop({
    default: () => ({
      autoYAxis: true,
      decimal: 0,
    }),
  })
  chartSettingParams: ChartSettingsParams;
  @Prop({ type: Boolean, default: false }) readonly showStatisticalValue: IPanelChartViewProps['showStatisticalValue'];
  @Prop({ type: Number, default: 2 }) readonly viewColumn: IPanelChartViewProps['viewColumn'];

  @ProvideReactive('handleUpdateQueryData') handleUpdateQueryData = undefined;
  // 刷新间隔
  // @ProvideReactive('refreshInterval') refreshInterval = -1;
  @ProvideReactive('filterOption') filterOption: IMetricAnalysisConfig;
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {
    interval: 'auto',
  };
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isApm') readonly isApm: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap!: RequestHandlerMap;

  @Ref('panelChartViewRef') readonly panelChartViewRef;

  activeName = [];
  /** 分组数据 */
  groupList: IGroups[] = [];
  /** connectId set 列表 */
  connectIdSet = new Set();
  /** 折叠面板的高度 */
  collapseRefsHeight: number[][] = [];
  /** 是否展示维度下钻view */
  showDrillDown = false;
  tableList = [];

  currentChart = {};

  loading = false;
  defaultGroupId = 'group-chart';
  metricIdsBatch: (number | string)[][] = [];
  currentBatchIndex = 0;
  allGroupList: IGroups[] = [];

  /** 过滤条件发生改变的时候重新拉取数据 */
  @Watch('config', { deep: true })
  handleConfigChange(val) {
    // 后端返回'$interval'，interval的赋值生效
    this.viewOptions.interval = Number.isNaN(+val.interval) ? val.interval || 'auto' : +val.interval;
    this.filterOption = deepClone(val);
    // this.timeRange = [val.start_time, val.end_time];
    val && this.getGroupList();
  }

  /** 监听滚动事件 */
  @Debounce(300)
  handleScroll() {
    const { scrollTop, scrollHeight, clientHeight } = this.panelChartViewRef;
    if (scrollHeight - scrollTop - clientHeight < 10) {
      this.handleLoadMore();
    }
  }

  /** 加载更多数据 */
  handleLoadMore() {
    if (this.currentBatchIndex >= this.metricIdsBatch.length - 1) {
      return;
    }
    this.currentBatchIndex++;
    const currentBatch = this.metricIdsBatch[this.currentBatchIndex];
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const config = {
      ...this.config,
      metric_ids: currentBatch,
    };
    delete config.metrics;
    const params = {
      ...config,
      time_series_group_id: Number(this.timeSeriesGroupId),
      start_time: startTime,
      end_time: endTime,
    };
    if (this.isApm) {
      delete params.time_series_group_id;
      Object.assign(params, {
        apm_app_name: this.appName,
        apm_service_name: this.serviceName,
      });
    }
    delete params.bk_biz_id;
    if (!params.compare?.type) {
      delete params.compare;
    }
    this.requestHandlerMap.getCustomTsGraphConfig(params).then(res => {
      const newGroups = res.groups || [];
      this.allGroupList = [...this.allGroupList, ...newGroups];
      this.handleGroup(newGroups);
      const len = this.allGroupList.length;
      const max = Math.ceil(len / this.viewColumn);
      this.groupList = this.allGroupList;
      this.activeName = this.groupList.map(item => item.name).slice(0, max > 3 ? 1 : max);
      this.handleCollapseChange();
      this.loadGraphConfigMetricIds(currentBatch);
    });
  }

  destroyed() {
    for (const id of this.connectIdSet) {
      disconnect(id as string);
    }
    if (this.panelChartViewRef) {
      this.panelChartViewRef.removeEventListener('scroll', this.handleScroll, { passive: true });
    }
  }

  /** 展示的个数发生变化时 */
  @Watch('viewColumn')
  handleColumnNumChange() {
    this.handleCollapseChange();
  }
  /** 是否需要展示统计值 */
  @Watch('showStatisticalValue', { immediate: true })
  handleShowStatisticalValueChange() {
    this.handleCollapseChange();
  }

  @Watch('loading')
  loadingChange(newLoadingState) {
    this.panelChartViewRef?.removeEventListener('scroll', this.handleScroll, { passive: true });
    if (!newLoadingState && this.panelChartViewRef) {
      this.panelChartViewRef.addEventListener('scroll', this.handleScroll, { passive: true });
    }
  }

  /** 是否展示高亮峰谷值 */
  get isHighlightPeakValue() {
    return this.config?.highlight_peak_value || false;
  }
  get baseHeight() {
    return this.showStatisticalValue ? DEFAULT_HEIGHT : 300;
  }

  @Emit('metricManage')
  handleMetricManage(tab) {
    return tab;
  }

  @Emit('loadGraphConfigMetricIds')
  loadGraphConfigMetricIds(metricIds: (number | string)[], init = false) {
    return { init, metricIds };
  }

  /** 重新获取对应的高度 */
  handleCollapseChange() {
    if (this.groupList.length === 0) return;
    const newHeight: number[][] = [];
    this.groupList.forEach((item, ind) => {
      const len = item.panels.length;
      newHeight[ind] = [];
      for (let i = 0; i < len; i++) {
        newHeight[ind][Math.floor(i / this.viewColumn)] = this.baseHeight;
      }
    });
    this.collapseRefsHeight = newHeight;
  }

  /**
   *  处理group数据
   * @param groups 分组数据
   * @returns 处理后的group数据
   */
  handleGroup(groups: IGroups[]) {
    const timeSeriesOptions = {
      time_series: {
        hoverAllTooltips: true,
      },
    };
    groups.forEach(group => {
      const groupId = group.name || random(10);
      group.groupId = groupId;
      // 多图表链接
      if (!this.connectIdSet.has(groupId)) {
        this.connectIdSet.add(groupId);
        connect(groupId);
      } else {
        disconnect(groupId);
        connect(groupId);
      }
      group.panels.forEach(chart => {
        chart.groupId = groupId;
        if (!chart.options?.time_series) {
          chart.options = {
            ...chart.options,
            ...timeSeriesOptions,
          };
        }
      });
    });
    return groups;
  }

  /** 获取图表配置 */
  @Debounce(300)
  getGroupList() {
    if (!this.timeSeriesGroupId && !this.isApm) {
      return;
    }
    if (this.config.metrics.length < 1) {
      this.loading = false;
      this.groupList = [];
      this.activeName = [];
      return;
    }
    this.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const metricIds = this.config.metrics.map(({ field_id }) => field_id);
    this.metricIdsBatch = chunkArray(metricIds, 24);
    this.currentBatchIndex = 0;
    this.allGroupList = [];
    const currentBatch = this.metricIdsBatch[0];
    const config = {
      ...this.config,
      metric_ids: currentBatch,
    };
    delete config.metrics;
    const params = {
      ...config,
      time_series_group_id: Number(this.timeSeriesGroupId), // apm不需要
      start_time: startTime,
      end_time: endTime,
    };
    // apm不需要time_series_group_id，改为apm_app_name和apm_service_name
    if (this.isApm) {
      delete params.time_series_group_id;
      Object.assign(params, {
        apm_app_name: this.appName,
        apm_service_name: this.serviceName,
      });
    }
    delete params.bk_biz_id;
    if (!params.compare?.type) {
      delete params.compare;
    }
    this.requestHandlerMap
      .getCustomTsGraphConfig(params)
      .then(res => {
        this.allGroupList = res.groups || [];
        this.handleGroup(this.allGroupList);
        this.loading = false;
        const len = this.allGroupList.length;
        const max = Math.ceil(len / this.viewColumn);
        this.groupList = this.allGroupList;
        this.activeName = this.groupList.map(item => item.name).slice(0, max > 3 ? 1 : max);
        this.handleCollapseChange();
        this.loadGraphConfigMetricIds(currentBatch, true);
      })
      .catch(() => {
        this.loading = false;
        this.allGroupList = [];
        this.groupList = [];
        this.activeName = [];
      });
  }
  /** 渲染panel的内容 */
  renderPanelMain(chart: IPanelModel, ind: number, chartInd: number, name: string) {
    return (
      <div class={['chart-view-item', `column-${this.viewColumn}`, { 'is-statistical': this.showStatisticalValue }]}>
        <LayoutChartTable
          height={this.collapseRefsHeight[ind][Math.floor(chartInd / this.viewColumn)]}
          config={this.config}
          groupId={name || this.defaultGroupId}
          isShowStatisticalValue={this.showStatisticalValue}
          panel={chart}
          onMetricManage={this.handleMetricManage}
          onResize={height => this.handleResize(height, ind, chartInd)}
        />
      </div>
    );
  }
  /** 骨架屏loading */
  renderSkeletonLoading() {
    return (
      <div class='view-skeleton-loading'>
        {Array(2)
          .fill(null)
          .map((_, index) => (
            <div
              key={index}
              class='skeleton-loading-item'
            >
              <div class='skeleton-element' />
              <div class='skeleton-element-row'>
                {Array(3)
                  .fill(null)
                  .map((_, index) => (
                    <div
                      key={index}
                      class='skeleton-element-row-item'
                    >
                      <i class='icon-monitor icon-mc-line skeleton-icon' />
                    </div>
                  ))}
              </div>
            </div>
          ))}
      </div>
    );
  }
  /** 拉伸 */
  handleResize(height: number, ind: number, chartInd: number) {
    this.collapseRefsHeight[ind][Math.floor(chartInd / this.viewColumn)] = height;
    this.collapseRefsHeight = [...this.collapseRefsHeight];
  }

  render() {
    if (this.config.metrics?.length < 1) {
      return (
        <bk-exception
          class='panel-metric-chart-view-empty'
          scene='part'
          type='empty'
        >
          {this.$t('没有选择任务指标')}
        </bk-exception>
      );
    }
    return (
      <div
        ref='panelChartViewRef'
        class='panel-metric-chart-view'
      >
        {this.loading ? (
          this.renderSkeletonLoading()
        ) : this.groupList.length > 0 ? (
          <bk-collapse
            class='chart-view-collapse'
            v-model={this.activeName}
          >
            {this.groupList.map((item, ind) => (
              <bk-collapse-item
                key={item.groupId || item.name || ind}
                class={['chart-view-collapse-item', { 'is-hide-header': !item.name }]}
                content-hidden-type='hidden'
                hide-arrow={true}
                name={item.name}
              >
                <span>
                  <span
                    class={`icon-monitor item-icon icon-mc-arrow-${this.activeName.includes(item.name) ? 'down' : 'right'}`}
                    slot='icon'
                  />
                  {item.name}
                </span>
                <div
                  class='chart-view-collapse-item-content'
                  slot='content'
                >
                  {/* {item.panels.map((chart, chartInd) => this.renderPanelMain(chart, ind, chartInd))} */}
                  {this.activeName.includes(item.name) &&
                    chunkArray(item.panels, this.viewColumn).map((rowItem, rowIndex) => (
                      <div
                        key={rowIndex}
                        class='chart-view-row'
                      >
                        {rowItem.map((panelData, chartInd) =>
                          this.renderPanelMain(panelData, ind, chartInd, item.name)
                        )}
                      </div>
                    ))}
                </div>
              </bk-collapse-item>
            ))}
          </bk-collapse>
        ) : (
          <EmptyStatus
            class='panel-metric-chart-view-empty'
            textMap={{ empty: this.$t('暂无数据') }}
            type={'empty'}
          />
        )}
      </div>
    );
  }
}
