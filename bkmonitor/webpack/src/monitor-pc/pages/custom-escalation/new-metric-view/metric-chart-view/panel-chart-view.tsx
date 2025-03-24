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
import { Component, Watch, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import { getCustomTsGraphConfig } from 'monitor-api/modules/scene_view';
import { Debounce } from 'monitor-common/utils';
import { deepClone } from 'monitor-common/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';

import LayoutChartTable from './layout-chart-table';
import { chunkArray } from './utils';

import type { IMetricAnalysisConfig } from '../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './panel-chart-view.scss';

/** 图表 + 表格列表，支持拉伸 */
const DEFAULT_HEIGHT = 600;
interface IPanelChartViewProps {
  config?: IMetricAnalysisConfig;
  showStatisticalValue?: boolean;
  viewColumn?: number;
}

@Component
export default class PanelChartView extends tsc<IPanelChartViewProps> {
  // 相关配置
  @Prop({ default: () => ({}) }) config: IMetricAnalysisConfig;
  @Prop({ type: Boolean, default: false }) readonly showStatisticalValue: IPanelChartViewProps['showStatisticalValue'];
  @Prop({ type: Number, default: 3 }) readonly viewColumn: IPanelChartViewProps['viewColumn'];

  @ProvideReactive('handleUpdateQueryData') handleUpdateQueryData = undefined;
  @ProvideReactive('filterOption') filterOption: IMetricAnalysisConfig;
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {
    interval: 'auto',
  };
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-1h', 'now'];
  activeName = [];
  groupList = [];
  collapseRefsHeight: number[][] = [];
  /** 是否展示维度下钻view */
  showDrillDown = false;
  tableList = [];

  currentChart = {};

  loading = false;

  /** 过滤条件发生改变的时候重新拉取数据 */
  @Watch('config', { deep: true })
  handleConfigChange(val) {
    this.filterOption = deepClone(val);
    // this.timeRange = [val.start_time, val.end_time];
    val && this.getGroupList();
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
  /** 是否展示高亮峰谷值 */
  get isHighlightPeakValue() {
    return this.config?.highlight_peak_value || false;
  }
  get baseHeight() {
    return this.showStatisticalValue ? DEFAULT_HEIGHT : 300;
  }

  /** 重新获取对应的高度 */
  handleCollapseChange() {
    if (this.groupList.length === 0) return;
    this.collapseRefsHeight = [];
    this.groupList.map((item, ind) => {
      const len = item.panels.length;
      this.collapseRefsHeight[ind] = [];
      Array(len)
        .fill(0)
        .map((_, index) => (this.collapseRefsHeight[ind][Math.floor(index / this.viewColumn)] = this.baseHeight));
    });
  }
  /** 获取图表配置 */
  @Debounce(300)
  getGroupList() {
    if (this.config.metrics.length < 1) {
      this.loading = false;
      this.groupList = [];
      this.activeName = [];
      return;
    }

    this.loading = true;
    const [startTime, endTime] = customEscalationViewStore.timeRangTimestamp;
    const params = {
      ...this.config,
      time_series_group_id: Number(this.$route.params.id),
      start_time: startTime,
      end_time: endTime,
    };
    delete params.bk_biz_id;
    if (!params.compare?.type) {
      delete params.compare;
    }

    getCustomTsGraphConfig(params)
      .then(res => {
        this.loading = false;
        this.groupList = res.groups || [];
        this.activeName = this.groupList.map(item => item.name);
        this.handleCollapseChange();
      })
      .catch(() => {
        this.loading = false;
        this.groupList = [];
        this.activeName = this.groupList.map(item => item.name);
      });
  }
  /** 渲染panel的内容 */
  renderPanelMain(chart: IPanelModel, ind: number, chartInd: number) {
    return (
      <div class={`chart-view-item column-${this.viewColumn}`}>
        <LayoutChartTable
          height={this.collapseRefsHeight[ind][Math.floor(chartInd / this.viewColumn)]}
          config={this.config}
          isShowStatisticalValue={this.showStatisticalValue}
          panel={chart}
          onResize={height => this.handleResize(height, ind, chartInd)}
        ></LayoutChartTable>
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
            <div class='skeleton-loading-item'>
              <div
                key={index}
                class='skeleton-element'
              />
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
      <div class='panel-metric-chart-view'>
        {this.loading ? (
          this.renderSkeletonLoading()
        ) : this.groupList.length > 0 ? (
          <bk-collapse
            class='chart-view-collapse'
            v-model={this.activeName}
          >
            {this.groupList.map((item, ind) => (
              <bk-collapse-item
                key={item.name}
                class={['chart-view-collapse-item', { 'is-hide-header': !item.name }]}
                content-hidden-type='hidden'
                hide-arrow={true}
                name={item.name}
              >
                <span>
                  <span
                    class={`icon-monitor item-icon icon-mc-arrow-${this.activeName.includes(item.name) ? 'down' : 'right'}`}
                    slot='icon'
                  ></span>
                  {item.name}
                </span>
                <div
                  class='chart-view-collapse-item-content'
                  slot='content'
                >
                  {/* {item.panels.map((chart, chartInd) => this.renderPanelMain(chart, ind, chartInd))} */}
                  {chunkArray(item.panels, this.viewColumn).map((rowItem, rowIndex) => (
                    <div
                      key={rowIndex}
                      class='chart-view-row'
                    >
                      {rowItem.map((panelData, chartInd) => this.renderPanelMain(panelData, ind, chartInd))}
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
