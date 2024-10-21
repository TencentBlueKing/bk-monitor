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

import { DEFAULT_FILTER } from './baseFIlterList';
import CallerCalleeContrast from './components/caller-callee-contrast';
import CallerCalleeFilter from './components/caller-callee-filter';
import CallerCalleeTableChart from './components/caller-callee-table-chart';
import ChartView from './components/chart-view';
import TabBtnGroup from './components/common-comp/tab-btn-group';
import { SEARCH_KEY_LIST } from './SEARCH_KEY_LIST';
import { dashboardPanels } from './testData';
import { CALLER_CALLEE_TYPE } from './utils';

import './apm-service-caller-callee.scss';

@Component({
  name: 'ApmServiceCallerCallee',
  components: {},
})
export default class ApmServiceCallerCallee extends tsc<object> {
  // 筛选具体的key list
  searchListData = SEARCH_KEY_LIST;
  /* 已选的对比日期 */
  contrastDates = [];
  /* 已选的groupBy */
  groupBy = [];
  filterData = {
    // 主调筛选值
    caller: JSON.parse(JSON.stringify(DEFAULT_FILTER)),
    // 被调筛选值
    callee: JSON.parse(JSON.stringify(DEFAULT_FILTER)),
  };
  panelsData = dashboardPanels;
  testData = [
    {
      caller_service: 'caller.collector.Unknown',
      formal: 'formal',
      now: 33,
      yesterday: 23,
    },
    {
      caller_service: 'caller.collector.UnknownHTTP',
      formal: 'formal1',
      now: 33,
      yesterday: 23,
    },
  ];
  tableListData = this.testData;
  tableTabData = this.testData;
  tabList = CALLER_CALLEE_TYPE;
  activeKey = 'caller';
  filterDataList = [];
  dateData = [];
  diffTypeData = [];
  tableColData = [];
  changeTab(id: string) {
    this.activeKey = id;
  }
  // 筛选查询
  searchFilterData(data) {
    this.filterDataList = JSON.parse(JSON.stringify(data));
    this.initData();
  }
  // 重置
  resetFilterData(data) {
    this.filterData[this.activeKey] = data;
  }
  // 获取表格数据
  handleGetTableData() {}
  // 获取图表数据
  handleGetChartData() {}

  initData() {
    this.handleGetTableData();
    this.handleGetChartData();
  }
  // 关闭表格中的筛选tag
  handleCloseTag(data) {
    this.filterDataList.find(item => item.label === data.label).values = [];
    this.initData();
  }
  // 查看详情 - 选中的字段回填到左侧筛选栏
  handleDetail({ row, key }) {
    this.filterData[this.activeKey].find(item => item.label === key).values = [row[key]];
  }

  /**
   * @description 对比日期选择
   * @param val
   */
  handleContrastDatesChange(val: string[]) {
    this.contrastDates = val;
  }

  changeFilterData({ val, item }) {
    console.log(val, item);
  }

  changeDate(date) {
    this.dateData = date;
    this.handleTableColData();
  }

  handleCheck(data) {
    this.diffTypeData = data;
    this.handleTableColData();
  }
  handleTableColData() {
    this.tableColData = [...this.dateData, ...this.diffTypeData];
  }
  handleGroupFilter() {}
  /**
   * @description groupBy 数据
   * @param val
   */
  handleGroupChange(val: string[]) {
    this.groupBy = val;
  }

  handleChoosePoint(date) {
    if (this.filterDataList.findIndex(item => item.label === 'time') !== -1) {
      this.filterDataList.find(item => item.label === 'time').values = [date];
      return;
    }
    this.filterDataList.push({
      label: 'time',
      operate: 1,
      values: [date],
    });
  }

  render() {
    return (
      <div class='apm-service-caller-callee'>
        <div class='caller-callee-head'>
          <div class='caller-callee-left'>
            <TabBtnGroup
              activeKey={this.activeKey}
              list={this.tabList}
              onChange={this.changeTab}
            />
          </div>
          <div class='caller-callee-right'>
            <CallerCalleeContrast
              contrastDates={this.contrastDates}
              groupBy={this.groupBy}
              searchList={this.searchListData}
              // onChangeDate={this.changeDate}
              // onCheck={this.handleCheck}
              onContrastDatesChange={this.handleContrastDatesChange}
              onGroupByChange={this.handleGroupChange}
              onGroupFilter={this.handleGroupFilter}
            />
          </div>
        </div>
        <div class='caller-callee-main'>
          <bk-resize-layout
            class='caller-callee-layout'
            initial-divide={320}
            max={500}
            min={320}
            placement='left'
            collapsible
          >
            <div
              class='layout-aside'
              slot='aside'
            >
              <CallerCalleeFilter
                filterData={this.filterData[this.activeKey]}
                searchList={this.searchListData}
                onChange={this.changeFilterData}
                onReset={this.resetFilterData}
                onSearch={this.searchFilterData}
              />
            </div>
            <div
              class='layout-main'
              slot='main'
            >
              <ChartView
                panelsData={this.panelsData}
                onChoosePoint={this.handleChoosePoint}
              />
              <CallerCalleeTableChart
                filterData={this.filterDataList}
                searchList={this.searchListData}
                tableColData={this.tableColData}
                tableListData={this.tableListData}
                tableTabData={this.tableTabData}
                onCloseTag={this.handleCloseTag}
                onHandleDetail={this.handleDetail}
              />
            </div>
          </bk-resize-layout>
        </div>
      </div>
    );
  }
}
