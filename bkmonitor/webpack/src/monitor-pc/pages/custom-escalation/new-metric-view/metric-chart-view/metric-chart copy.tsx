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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ChartHeader from 'monitor-ui/chart-plugins/components/chart-title/chart-title';
import BaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';

import { mockChart } from './data';

import './metric-chart.scss';

@Component
export default class NewMetricChart extends tsc<object> {
  width = '100%';
  height = '400px';
  inited = true;
  metrics = [];
  options = {
    tooltip: {
      className: 'new-metric-chart-tooltips',
      trigger: 'axis',
    },
    grid: {
      top: '6%',
      left: '1%',
      right: '1%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'time',
      axisTick: {
        show: false,
      },
      boundaryGap: false,
      axisLabel: {
        fontSize: 12,
        color: '#979BA5',
        showMinLabel: false,
        showMaxLabel: false,
      },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: {
        show: true,
        lineStyle: {
          color: '#F0F1F5',
          type: 'solid',
        },
      },
    },
    series: mockChart.series,
  };
  empty = false;
  emptyText = window.i18n.tc('暂无数据');
  menuList = [];
  panel = {
    title: '磁盘空间使用率',
    descrition: '2',
    draging: false,
    instant: false,
    subTitle: 'system.mem.pct_used',
    dashboardId: '111',
  };
  render() {
    return (
      <div class='new-metric-chart'>
        <ChartHeader
          //   collectIntervalDisplay={this.collectIntervalDisplay}
          customArea={true}
          descrition={this.panel.descrition}
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          menuList={this.menuList as any}
          //   metrics={this.metrics}
          needMoreMenu={true}
          showMore={true}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
          //   onAlarmClick={this.handleAlarmClick}
          //   onAllMetricClick={this.handleAllMetricClick}
          //   onMenuClick={this.handleMenuToolsSelect}
          //   onMetricClick={this.handleMetricClick}
          //   onSelectChild={this.handleSelectChildMenu}
        ></ChartHeader>
        {!this.empty ? (
          <div class='new-metric-chart-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  groupId={this.panel.dashboardId}
                  //   hoverAllTooltips={this.hoverAllTooltips}
                  //   needZrClick={this.panel?.options?.need_zr_click_event}
                  options={this.options}
                  //   showRestore={this.showRestore}
                  //   onDataZoom={this.dataZoom}
                  //   onRestore={this.handleRestore}
                  //   onZrClick={this.handleZrClick}
                />
              )}
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
