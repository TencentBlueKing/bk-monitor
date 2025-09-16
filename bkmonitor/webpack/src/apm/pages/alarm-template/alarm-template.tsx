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

import StatusTab from 'monitor-ui/chart-plugins/plugins/table-chart/status-tab';

import AlarmTemplateSearch from './components/alarm-templte-search/alarm-template-search';
import BatchOperations from './components/batch-operations/batch-operations';
import EditTemplateSlider from './components/template-form/edit-template-slider';
import { ALARM_TEMPLATE_QUICK_FILTER_LIST } from './constant';

import type { AlarmTemplateConditionParamItem, BatchOperationTypeEnumType } from './typeing';

import './alarm-template.scss';

@Component
export default class AlarmTemplate extends tsc<object> {
  /** 模板类型快速筛选tab */
  quickStatus = 'all';
  /** 搜索关键字 */
  searchKeyword: AlarmTemplateConditionParamItem[] = [];
  /** 表格已勾选的数据行id */
  selectedRowKeys: string[] = [];

  editTemplateId = null;
  editTemplateShow = false;

  /**
   * @description 模板类型快捷筛选值改变后回调
   */
  handleQuickStatusChange(status: string) {
    this.quickStatus = status;
  }
  /**
   * @description 批量操作按钮点击事件
   */
  handleBatchOperationClick(operationType: BatchOperationTypeEnumType) {
    console.log('================ operationType ================', operationType);
  }

  handleSearchChange(keyword: AlarmTemplateConditionParamItem[]) {
    this.searchKeyword = keyword;
    // this.setRouterParams();
  }

  handleEditTemplate(id: number) {
    this.editTemplateId = id;
    this.editTemplateShow = true;
  }

  render() {
    return (
      <div class='alarm-template'>
        <div class='alarm-template-header'>
          <div class='alarm-template-header-operations'>
            <BatchOperations
              disabled={!!this.selectedRowKeys?.length}
              onOperationClick={this.handleBatchOperationClick}
            />
            <StatusTab
              class='alarm-template-header-filter-tab'
              v-model={this.quickStatus}
              needAll={false}
              statusList={ALARM_TEMPLATE_QUICK_FILTER_LIST}
              onChange={this.handleQuickStatusChange}
            />
            <bk-button onClick={() => this.handleEditTemplate(1)}>编辑模板</bk-button>
          </div>
          <div class='alarm-template-header-search'>
            <AlarmTemplateSearch
              class='search-input'
              searchKeyword={this.searchKeyword}
              onChange={this.handleSearchChange}
            />
          </div>
        </div>
        <div class='alarm-template-main'>
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

        <EditTemplateSlider
          appName={'tilapia'}
          isShow={this.editTemplateShow}
          templateId={this.editTemplateId}
          onShowChange={show => {
            this.editTemplateShow = show;
          }}
        />
      </div>
    );
  }
}
