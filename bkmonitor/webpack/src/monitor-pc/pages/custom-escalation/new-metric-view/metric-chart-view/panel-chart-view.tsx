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
import { Component, Watch, Provide } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IPanelModel } from 'monitor-ui/chart-plugins/typings';

import { api } from './api';
import DrillAnalysisView from './drill-analysis-view';
import LayoutChartTable from './layout-chart-table';
import NewMetricChart from './metric-chart';
import { tableData, panelData } from './mock-data';

import type { IColumnItem, IDataItem } from '../type';

import './panel-chart-view.scss';

/** 图表 + 表格列表，支持拉伸 */
const DEFAULT_HEIGHT = 600;

@Component
export default class PanelChartView extends tsc<object> {
  @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  activeName = ['12.31.342.12', '2', '0'];
  groupList = api.data.groups;
  collapseRefsHeight: number[][] = [];
  columnList = [
    { label: '', prop: 'max', renderFn: (row: IDataItem) => this.renderLegend(row) },
    { label: '最大值', prop: 'environment' },
    { label: '最小值', prop: 'version' },
    { label: '最新值', prop: 'proportion' },
    { label: '平均值', prop: 'value' },
    { label: '累计值', prop: 'fluctuation' },
  ];
  /** 是否展示维度下钻view */
  showDrillDown = false;
  tableList = tableData;

  currentChart = {};
  /** 拉伸的时候图表重新渲染 */
  @Watch('groupList', { immediate: true })
  handlePanelChange(val) {
    if (val.length === 0) return;
    this.collapseRefsHeight = [];
    val.map((item, ind) => {
      const len = item.panels.length;
      this.collapseRefsHeight[ind] = [];
      Array(len)
        .fill(0)
        .map((_, index) => (this.collapseRefsHeight[ind][Math.floor(index / 2)] = DEFAULT_HEIGHT));
    });
  }
  renderLegend(row: IDataItem) {
    return (
      <span>
        <span
          style={{ backgroundColor: row.color }}
          class='color-box'
        />
        {row.environment}
      </span>
    );
  }
  renderIndicatorTable() {
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
                return row[item.prop];
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
  /** 渲染panel的内容 */
  renderPanelMain(item, chart, ind, chartInd) {
    if (item.panels.length === 1) {
      return (
        <div class='chart-view-item single-item'>
          <div class='indicator-chart-view'>
            <NewMetricChart panel={chart} />
          </div>
          <div class='indicator-table-view'>{this.renderIndicatorTable()}</div>
        </div>
      );
    }
    return (
      <div class='chart-view-item'>
        <LayoutChartTable
          height={this.collapseRefsHeight[ind][Math.floor(chartInd / 2)]}
          panel={chart}
          onDrillDown={() => this.handelDrillDown(chart)}
          onResize={height => this.handleResize(height, ind, chartInd)}
        >
          {this.renderIndicatorTable()}
        </LayoutChartTable>
      </div>
    );
  }
  /** 拉伸 */
  handleResize(height: number, ind: number, chartInd: number) {
    this.collapseRefsHeight[ind][Math.floor(chartInd / 2)] = height;
    this.collapseRefsHeight = [...this.collapseRefsHeight];
  }
  /** 维度下钻 */
  handelDrillDown(chart: IPanelModel) {
    this.showDrillDown = true;
    this.currentChart = chart;
  }

  render() {
    return (
      <div class='panel-metric-chart-view'>
        <bk-collapse
          class='chart-view-collapse'
          v-model={this.activeName}
        >
          {this.groupList.map((item, ind) => (
            <bk-collapse-item
              key={item.name}
              class='chart-view-collapse-item'
              content-hidden-type='hidden'
              hide-arrow={true}
              name={item.name}
            >
              <span
                class={`icon-monitor item-icon icon-mc-arrow-${this.activeName.includes(item.name) ? 'down' : 'right'}`}
                slot='icon'
              ></span>
              {item.name}
              <div
                class='chart-view-collapse-item-content'
                slot='content'
              >
                {item.panels.map((chart, chartInd) => this.renderPanelMain(item, chart, ind, chartInd))}
              </div>
            </bk-collapse-item>
          ))}
        </bk-collapse>
        {this.showDrillDown && (
          <DrillAnalysisView
            panel={this.currentChart}
            onClose={() => (this.showDrillDown = false)}
          />
        )}
      </div>
    );
  }
}
