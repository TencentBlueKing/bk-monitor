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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import BaseEchart from '../monitor-base-echart';
import TimeSeries from '../time-series/time-series';
import ExploreChartSkeleton from './components/explore-chart-skeleton';
import ExploreCollapseWrapper from './components/explore-collapse-wrapper';
import ExploreIntervalSelect from './components/explore-interval-select';

import './explore-custom-graph.scss';

export type IntervalType = 'auto' | number;

interface IExploreCustomChartEvents {
  /** 图表汇聚周期 */
  onIntervalChange: (interval: IntervalType) => void;
}

interface IExploreCustomChartProps {
  /** 图表汇聚周期 */
  chartInterval: IntervalType;
  preparing?: boolean;
  queryKey?: string;
  /** 数据总数 */
  total?: number;
  totalLoading?: boolean;
}

@Component
export class ExploreCustomChart extends TimeSeries {
  @Prop({ type: Boolean, default: false }) totalLoading: boolean;
  @Prop({ type: Boolean, default: false }) preparing: boolean;
  @Prop({ type: String, default: '' }) queryKey: string;
  /** 图表汇聚周期 */
  @Prop({ type: [Number, String], default: 'auto' }) chartInterval: IntervalType;
  /** 数据总数 */
  @Prop({ type: Number, default: 0 }) total: number;

  containerHeight = 0;
  duration = 0;
  requestId = 0;
  requestDisposed = false;
  loadedQueryKey: string = null;
  chartError = false;

  get showSkeleton() {
    return this.preparing || (this.requestConfig.loading && (this.loadedQueryKey !== this.queryKey || this.empty));
  }

  createRequestGuard() {
    const requestId = ++this.requestId;
    const panel = this.panel;
    return () => !this.requestDisposed && requestId === this.requestId && panel === this.panel && !this.preparing;
  }

  @Debounce(0)
  async getPanelData(startTime?: string, endTime?: string) {
    if (this.requestDisposed) return;
    if (this.preparing || !this.panel.targets.length) {
      this.requestId += 1;
      this.cancelTokens.forEach(cancel => cancel?.());
      this.cancelTokens = [];
      this.requestConfig.loading = false;
      this.loadedQueryKey = null;
      this.empty = true;
      this.emptyText = this.$tc('暂无数据');
      return;
    }
    await this.queryPanelData(startTime, endTime);
  }

  beforeDestroy() {
    clearTimeout(this.getPanelData_debounceFn);
    this.requestDisposed = true;
    this.requestId += 1;
    this.cancelTokens.forEach(cancel => cancel?.());
  }
  requestConfig = {
    /** 图表loading */
    loading: false,
    /** 图表数据接口请求耗时 */
    duration: 0,
    lastTime: Date.now(),
  };

  get showLegendTags() {
    return this.legendData?.filter?.(e => e.show) || [];
  }

  panelChange() {
    this.getPanelData();
  }

  @Emit('intervalChange')
  handleIntervalChange(interval: IntervalType) {
    return interval;
  }

  handleLoadingChange(loading: boolean) {
    const now = Date.now();
    this.requestConfig.duration = loading ? 0 : now - this.requestConfig.lastTime;
    this.requestConfig.lastTime = now;
    this.requestConfig.loading = loading;
    if (!loading) this.loadedQueryKey = this.queryKey;
    return loading;
  }

  handleBeforeRequestLoadingChange() {
    this.chartError = false;
    this.handleLoadingChange(true);
  }

  handleErrorMsgChange(message: string) {
    this.chartError = true;
    this.$emit('errorMsg', message);
    return message;
  }

  /**
   * @description: 改变图例方法
   */
  selectLegendChange(legendName: string, shouldShow = true) {
    const showLegends = this.legendData?.filter?.(e => e.show) || [];
    if (!shouldShow && showLegends.length === 1) {
      return;
    }
    const legendItem = this.legendData?.find?.(v => v.name === legendName);
    if (!legendItem) {
      return;
    }
    legendItem.show = shouldShow;
    const showNames = [];
    const copyOptions = { ...this.options };
    for (const item of this.legendData) {
      item.show && showNames.push(item.name);
    }
    copyOptions.series = this.seriesList?.filter(s => showNames.includes(s.name));
    this.options = Object.freeze({ ...copyOptions });
    this.$emit('selectLegend', this.legendData);
  }

  /**
   * @description 图表头部右侧区域渲染
   */
  wrapperHeaderCustomSlotRender() {
    return (
      <div class='graph-header-custom'>
        <div class='graph-header-custom-tags'>
          {/* 快速筛选标签 暂时先不需要展示
          {this.showLegendTags?.map(item => (
            <div
              key={item.name}
              style={{
                '--tag-color': item.color || '',
                '--tag-bg-color': hexToRgba(item.color, 0.2) || '',
              }}
              class='chart-tags-item'
            >
              <i class='icon-monitor icon-filter-fill' />
              <span class='tag-label'>{item.name}</span>
              <i
                class='icon-monitor icon-mc-close'
                onClick={() => {
                  this.selectLegendChange(item.name, false);
                }}
              />
            </div>
          ))} */}
        </div>
        <div class='graph-header-custom-interval'>
          <ExploreIntervalSelect
            interval={this.chartInterval}
            selectLabel={`${this.$t('汇聚周期')} :`}
            onChange={this.handleIntervalChange}
          />
        </div>
      </div>
    );
  }

  /**
   * @description 图表头部左侧描述区域渲染
   */
  wrapperHeaderDescriptionSlotRender() {
    return (
      <i18n
        class='chart-header-description'
        path='(找到 {0} 条结果，用时 {1} 毫秒)'
      >
        {this.totalLoading ? (
          <span class='skeleton-element event-count-skeleton' />
        ) : (
          <span class='query-count'>{this.total ?? '--'}</span>
        )}
        {this.requestConfig.loading || this.preparing ? (
          <span class='skeleton-element event-duration-skeleton' />
        ) : (
          <span class='query-time'>{this.requestConfig.duration || 0}</span>
        )}
      </i18n>
    );
  }

  /**
   * @description 请求完成后 content 区域内容的渲染
   */
  requestSuccessContentRender() {
    const { legend } = this.panel?.options || { legend: {} };

    if (this.chartError && !this.requestConfig.loading) {
      return (
        <div
          class='event-load-error'
          role='status'
        >
          {this.$t('数据加载失败，请重试')}
          <bk-button
            text
            onClick={() => this.getPanelData()}
          >
            {this.$t('重试')}
          </bk-button>
        </div>
      );
    }

    if (this.empty) {
      return <div class='empty-chart'>{this.emptyText}</div>;
    }
    return (
      <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
        <div
          ref='chart'
          class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
        >
          {this.initialized && (
            <BaseEchart
              ref='baseChart'
              width={this.width}
              height={this.height}
              groupId={this.panel.dashboardId}
              hoverAllTooltips={this.hoverAllTooltips}
              needZrClick={this.panel.options?.need_zr_click_event}
              options={this.options}
              showRestore={this.showRestore}
              onDataZoom={this.dataZoom}
              onDblClick={this.handleDblClick}
              onRestore={this.handleRestore}
              onZrClick={this.handleZrClick}
            />
          )}
        </div>
        {legend?.displayMode !== 'hidden' && (
          <div class={`chart-legend ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            {legend?.displayMode === 'table' ? (
              <TableLegend
                legendData={this.legendData}
                onSelectLegend={this.handleSelectLegend}
              />
            ) : (
              <ListLegend
                legendData={this.legendData}
                onSelectLegend={this.handleSelectLegend}
              />
            )}
          </div>
        )}
      </div>
    );
  }

  render() {
    return (
      <div
        class='time-series explore-custom-graph'
        aria-busy={this.requestConfig.loading || this.preparing}
      >
        <ExploreCollapseWrapper
          scopedSlots={{
            triggerDescription: this.wrapperHeaderDescriptionSlotRender,
            headerCustom: this.wrapperHeaderCustomSlotRender,
          }}
          description={this.panel?.description}
          title={this.panel?.title}
        >
          <div class='event-chart-content'>
            {this.requestSuccessContentRender()}
            {this.showSkeleton && <ExploreChartSkeleton />}
            {this.requestConfig.loading && !this.showSkeleton && (
              <div
                class='event-chart-refreshing'
                role='status'
              >
                <bk-spin
                  placement='right'
                  size='mini'
                >
                  {this.$t('加载中')}
                </bk-spin>
              </div>
            )}
          </div>
        </ExploreCollapseWrapper>
      </div>
    );
  }
}

export default ofType<IExploreCustomChartProps, IExploreCustomChartEvents>().convert(ExploreCustomChart);
