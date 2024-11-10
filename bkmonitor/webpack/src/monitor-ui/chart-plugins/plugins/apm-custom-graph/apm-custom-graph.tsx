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
import { Component, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { handleTimeRange } from 'monitor-pc/utils';

import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import { isShadowEqual } from '../../utils/utils';
import BaseEchart from '../monitor-base-echart';
import StatusTab from '../table-chart/status-tab';
import TimeSeries from '../time-series/time-series';

import type { IViewOptions } from '../../typings';

import './apm-custom-graph.scss';
const APM_CUSTOM_METHODS = ['SUM', 'AVG', 'MAX', 'MIN'] as const;
@Component
export default class CustomChart extends TimeSeries {
  methodList = APM_CUSTOM_METHODS.map(method => ({
    id: method,
    name: method,
  }));
  method = this.viewOptions?.method || 'AVG';

  @Watch('viewOptions')
  // 用于配置后台图表数据的特殊设置
  handleFieldDictChange(v: IViewOptions, o: IViewOptions) {
    if (JSON.stringify(v) === JSON.stringify(o)) return;
    if (isShadowEqual(v, o)) return;
    this.superGetPanelData();
  }
  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.superGetPanelData();
  }
  @Watch('refleshInterval')
  // 数据刷新间隔
  handleRefleshIntervalChange(v: number) {
    if (this.refleshIntervalInstance) {
      window.clearInterval(this.refleshIntervalInstance);
    }
    if (v <= 0) return;
    this.refleshIntervalInstance = window.setInterval(() => {
      this.inited && this.superGetPanelData();
    }, this.refleshInterval);
  }
  @Watch('refleshImmediate')
  // 立刻刷新
  handleRefleshImmediateChange(v: string) {
    if (v) this.superGetPanelData();
  }
  @Watch('timezone')
  // 时区变更刷新图表
  handleTimezoneChange(v: string) {
    if (v) this.superGetPanelData();
  }
  @Watch('timeOffset')
  handleTimeOffsetChange(v: string[], o: string[]) {
    if (JSON.stringify(v) === JSON.stringify(o)) return;
    this.superGetPanelData();
  }

  @Watch('customTimeRange')
  customTimeRangeChange(val: [string, string]) {
    if (!val) {
      const { startTime, endTime } = handleTimeRange(this.timeRange);
      this.superGetPanelData(
        dayjs(startTime * 1000).format('YYYY-MM-DD HH:mm:ss'),
        dayjs(endTime * 1000).format('YYYY-MM-DD HH:mm:ss')
      );
    } else {
      this.superGetPanelData(val[0], val[1]);
    }
  }
  /* 粒度 */
  @Watch('downSampleRange')
  handleDownSampleRangeChange() {
    this.superGetPanelData();
  }
  @Watch('panel')
  panelChange(val, old) {
    if (isShadowEqual(val, old)) return;
    this.superGetPanelData();
  }
  async superGetPanelData(start_time?: string, end_time?: string) {
    this.getPanelData(start_time, end_time, {
      method: this.method,
    });
  }
  handleMethodChange(method: (typeof APM_CUSTOM_METHODS)[number]) {
    this.method = method;
    this.getPanelData(undefined, undefined, {
      method,
    });
  }
  render() {
    const { legend } = this.panel?.options || ({ legend: {} } as any);
    return (
      <div class='time-series apm-custom-graph'>
        {this.showChartHeader && (
          <ChartHeader
            class='draggable-handle'
            collectIntervalDisplay={this.collectIntervalDisplay}
            descrition={this.panel.options?.header?.tips || ''}
            draging={this.panel.draging}
            drillDownOption={this.drillDownOptions}
            inited={this.inited}
            isInstant={this.panel.instant}
            menuList={this.menuList}
            metrics={this.metrics}
            showAddMetric={this.showAddMetric}
            showMore={this.showHeaderMoreTool}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleAllMetricClick}
            onMenuClick={this.handleMenuToolsSelect}
            onMetricClick={this.handleMetricClick}
            onSelectChild={this.handleSelectChildMenu}
            onUpdateDragging={() => this.panel.updateDraging(false)}
          >
            <div
              class='custom-method-list'
              onClick={e => e.stopPropagation()}
            >
              <StatusTab
                needAll={false}
                statusList={this.methodList}
                value={this.method}
                onChange={this.handleMethodChange}
              />
            </div>
          </ChartHeader>
        )}
        {!this.empty ? (
          <div class={`time-series-content ${legend?.placement === 'right' ? 'right-legend' : ''}`}>
            <div
              ref='chart'
              class={`chart-instance ${legend?.displayMode === 'table' ? 'is-table-legend' : ''}`}
            >
              {this.inited && (
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
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
