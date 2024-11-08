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

import ListLegend from '../../components/chart-legend/common-legend';
import TableLegend from '../../components/chart-legend/table-legend';
import ChartHeader from '../../components/chart-title/chart-title';
import BaseEchart from '../monitor-base-echart';
import TimeSeries from '../time-series/time-series';

import './custom-chart.scss';

@Component
export default class CustomChart extends TimeSeries {
  methodList = ['SUM', 'AVG', 'MAX', 'MIN'];
  currentMethod = '';
  isDropdownShow = false;

  clickItem(method) {
    this.currentMethod = method;
  }
  dropdownShow() {
    this.currentMethod = 'more';
    this.isDropdownShow = true;
  }
  dropdownHide() {
    this.isDropdownShow = false;
  }
  render() {
    const { legend } = this.panel?.options || { legend: {} };
    return (
      <div class='apdex-chart'>
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
              class='bk-button-group'
              slot='custom'
              onClick={e => {
                e.stopPropagation();
              }}
            >
              {this.methodList.map(item => (
                <bk-button
                  key={item}
                  class={[{ 'is-selected': item === this.currentMethod }]}
                  size='small'
                  onClick={() => {
                    this.clickItem(item);
                  }}
                >
                  {item}
                </bk-button>
              ))}
              {this.methodList.length >= 5 ? (
                <div class='btn-more'>
                  <bk-dropdown-menu
                    ref='dropdown'
                    trigger='click'
                    onHide={this.dropdownHide}
                    onShow={this.dropdownShow}
                  >
                    <div slot='dropdown-trigger'>
                      <bk-button
                        class={[{ 'is-selected': this.currentMethod === 'more' }]}
                        size='small'
                      >
                        {this.$t('更多')}
                        <i class={['bk-icon icon-angle-down', { 'icon-flip': this.isDropdownShow }]} />
                      </bk-button>
                    </div>
                    <ul
                      class='bk-dropdown-list'
                      slot='dropdown-content'
                    >
                      {this.methodList.slice(4).map(item => (
                        <li key={item}>
                          <a
                            href='javascript:;'
                            // onClick={}
                          >
                            {item}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </bk-dropdown-menu>
                </div>
              ) : null}
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
