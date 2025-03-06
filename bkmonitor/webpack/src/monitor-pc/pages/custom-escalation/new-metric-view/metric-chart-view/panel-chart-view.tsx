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
import { Component, Watch, Provide, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getCustomTsGraphConfig } from 'monitor-api/modules/scene_view';
import ViewDetail from 'monitor-pc/pages/view-detail/view-detail-new';
import { type IPanelModel } from 'monitor-ui/chart-plugins/typings';

import { api, mockParam } from './api';
import DrillAnalysisView from './drill-analysis-view';
import LayoutChartTable from './layout-chart-table';

import type { IMetricAnalysisConfig } from '../type';

import './panel-chart-view.scss';

/** 图表 + 表格列表，支持拉伸 */
const DEFAULT_HEIGHT = 600;
interface IPanelChartViewProps {
  config?: IMetricAnalysisConfig;
  isShowStatisticalValue?: boolean;
  isHighlightPeakValue?: boolean;
}

@Component
export default class PanelChartView extends tsc<IPanelChartViewProps> {
  // 图表panel实例
  @Prop({ default: () => mockParam }) config: IMetricAnalysisConfig;
  /** 展示统计值 */
  @Prop({ default: false }) isShowStatisticalValue: boolean;
  /** 高亮峰谷值 */
  @Prop({ default: false }) isHighlightPeakValue: boolean;
  /** 每列展示的个数 */
  @Prop({ default: 3 }) columnNum: number;

  @Provide('handleUpdateQueryData')
  handleUpdateQueryData = undefined;
  activeName = [];
  groupList = [];
  collapseRefsHeight: number[][] = [];
  /** 是否展示维度下钻view */
  showDrillDown = false;
  tableList = [];

  currentChart = {};

  loading = false;
  showViewDetail = false;
  /** 查看大图参数配置 */
  viewQueryConfig = {};

  /** 拉伸的时候图表重新渲染 */
  @Watch('groupList')
  handlePanelChange() {
    this.handleCollapseChange();
  }
  /** 过滤条件发生改变的时候重新拉取数据 */
  @Watch('config', { immediate: true })
  handleConfigChange(val) {
    val && this.getGroupList();
  }
  /** 展示的个数发生变化时 */
  @Watch('columnNum')
  handleColumnNumChange() {
    this.handleCollapseChange();
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
        .map((_, index) => (this.collapseRefsHeight[ind][Math.floor(index / this.columnNum)] = DEFAULT_HEIGHT));
    });
  }
  /** 获取图表配置 */
  getGroupList() {
    this.loading = true;
    getCustomTsGraphConfig(this.config)
      .then(res => {
        this.loading = false;
        this.groupList = res.groups || [];
        this.activeName = this.groupList.map(item => item.name);
      })
      .catch(() => {
        this.loading = false;
        this.groupList = api.data.groups; // mock数据
        this.activeName = this.groupList.map(item => item.name);
      });
  }
  /** 渲染panel的内容 */
  renderPanelMain(item, chart, ind, chartInd) {
    return (
      <div class={`chart-view-item column-${this.columnNum}`}>
        <LayoutChartTable
          height={this.collapseRefsHeight[ind][Math.floor(chartInd / this.columnNum)]}
          config={this.config}
          panel={chart}
          onDrillDown={() => this.handelDrillDown(chart)}
          onFullscreen={() => this.handleFullScreen(chart)}
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
    this.collapseRefsHeight[ind][Math.floor(chartInd / this.columnNum)] = height;
    this.collapseRefsHeight = [...this.collapseRefsHeight];
  }
  /** 维度下钻 */
  handelDrillDown(chart: IPanelModel) {
    this.showDrillDown = true;
    this.currentChart = chart;
  }
  /**
   * @description: 关闭查看大图弹窗
   */
  handleCloseViewDetail() {
    this.showViewDetail = false;
    this.viewQueryConfig = {};
  }

  handleFullScreen(panel) {
    console.log(panel, '====');
  }

  render() {
    return (
      <div class='panel-metric-chart-view'>
        {this.loading ? (
          this.renderSkeletonLoading()
        ) : (
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
                  {item.panels.map((chart, chartInd) => this.renderPanelMain(item, chart, ind, chartInd))}
                </div>
              </bk-collapse-item>
            ))}
          </bk-collapse>
        )}

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
