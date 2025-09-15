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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import StatusTab from '../table-chart/status-tab';
import BatchOperations from './components/batch-operations/batch-operations';
import { ALARM_TEMPLATE_QUICK_FILTER_LIST } from './constant';

@Component
export default class ApmAlarmTemplate extends tsc<object> {
  /** 模板类型快速筛选tab */
  quickStatus = 'all';
  /** 表格已勾选的数据行id */
  selectedRowKeys: string[] = [];

  /**
   * @description 模板类型快捷筛选值改变后回调
   */
  handleQuickStatusChange(status: string) {
    this.quickStatus = status;
  }
  render() {
    return (
      <div class='apm-alarm-template'>
        <div class='apm-alarm-template-header'>
          <div class='alarm-template-header-operations'>
            <BatchOperations disabled={!this.selectedRowKeys?.length} />
            <StatusTab
              class='filter-tab'
              v-model={this.quickStatus}
              needAll={false}
              statusList={ALARM_TEMPLATE_QUICK_FILTER_LIST}
              onChange={this.handleQuickStatusChange}
            />
          </div>
          <div class='alarm-template-header-search'>
            {/* <QueryTemplateSearch
              class='search-input'
              searchKeyword={this.searchKeyword}
              onChange={this.handleSearchChange}
            /> */}
          </div>
        </div>
        <div class='apm-alarm-template-main'>
          {/* <QueryTemplateTable
            current={this.current}
            emptyType={this.searchKeyword?.length ? 'search-empty' : 'empty'}
            loading={this.tableLoading}
            pageSize={this.pageSize}
            sort={this.sort}
            tableData={this.tableData}
            total={this.total}
            onClearSearch={() => this.handleSearchChange([])}
            onCurrentPageChange={this.handleCurrentPageChange}
            onDeleteTemplate={this.deleteTemplateById}
            onPageSizeChange={this.handlePageSizeChange}
            onSortChange={this.handleSortChange}
          /> */}
        </div>
      </div>
    );
  }
}
