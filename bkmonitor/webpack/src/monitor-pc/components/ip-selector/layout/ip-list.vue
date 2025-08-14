<!--
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
-->
<template>
  <div
    ref="ipListWrapper"
    v-bkloading="{ isLoading: isLoading && !disabledLoading }"
    class="ip-list"
  >
    <bk-input
      v-if="enableTableSearch"
      v-model="tableKeyword"
      clearable
      right-icon="bk-icon icon-search"
      :placeholder="ipListPlaceholder"
      @change="handleKeywordChange"
    />
    <slot name="tab" />
    <ip-selector-table
      ref="table"
      class="ip-list-table mt10"
      :data="tableData"
      :config="ipListTableConfig"
      :pagination="pagination"
      :max-height="maxHeight"
      :default-selections="defaultSelections"
      :show-selection-column="showSelectionColumn"
      :empty-text="emptyText"
      :table-keyword="tableKeyword"
      @page-change="handlePageChange"
      @check-change="handleCheckChange"
      @page-limit-change="handleLimitChange"
      @clear-filter="handleClearFilter"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { Debounce } from '../common/util';
import IpSelectorTable from '../components/ip-selector-table.vue';

import type {
  IipListParams,
  IPagination,
  ITableCheckData,
  ITableConfig,
  SearchDataFuncType,
} from '../types/selector-type';

// IP列表
@Component({
  name: 'ip-list',
  components: {
    IpSelectorTable,
  },
})
export default class IpList extends Vue {
  // 提交变更时调用该方法获取数据
  @Prop({ type: Function, required: true }) private readonly getSearchTableData!: SearchDataFuncType;
  @Prop({ type: Function }) private readonly getDefaultSelections!: Function;

  @Prop({ default: '', type: String }) private readonly ipListPlaceholder!: string;
  // 表格字段配置
  @Prop({ default: () => [], type: Array }) private readonly ipListTableConfig!: ITableConfig[];
  // 每页数
  @Prop({ default: 20, type: Number }) private readonly limit!: number;
  @Prop({ default: 0, type: Number }) private readonly slotHeight!: number;
  @Prop({ default: true, type: Boolean }) private readonly showSelectionColumn!: boolean;
  // 禁用组件的loading状态
  @Prop({ default: false, type: Boolean }) private readonly disabledLoading!: boolean;
  @Prop({ default: '', type: String }) private readonly emptyText!: string;
  @Prop({ default: true, type: Boolean }) private readonly enableTableSearch!: boolean;

  @Ref('ipListWrapper') private readonly ipListWrapperRef!: HTMLElement;
  @Ref('table') private readonly tableRef!: IpSelectorTable;

  private isLoading = false;
  // 前端分页时全量数据
  private fullData: any[] = [];
  private frontendPagination = false;
  private tableData: any[] = [];
  private tableKeyword = '';
  private pagination: IPagination = {
    current: 1,
    limit: 20,
    count: 0,
  };
  private maxHeight = 400;
  private defaultSelections: any[] = [];

  @Watch('slotHeight')
  private handleSlotHeightChange() {
    this.maxHeight = this.ipListWrapperRef.clientHeight - this.slotHeight - 42;
  }

  private created() {
    this.pagination.limit = this.limit;
    this.handleGetDefaultData();
  }

  private mounted() {
    this.maxHeight = this.ipListWrapperRef.clientHeight - this.slotHeight - 42;
  }

  public handleGetDefaultData(type = '') {
    this.pagination.current = 1;
    this.pagination.count = 0;
    this.tableRef?.resetCheckedStatus();
    this.handleGetSearchData(type);
  }

  public handleGetDefaultSelections() {
    // 获取默认勾选项
    this.defaultSelections = this.tableData.filter(
      row => this.getDefaultSelections && !!this.getDefaultSelections(row)
    );
  }

  public selectionAllData() {
    this.$nextTick(() => {
      !!this.tableData.length && this.tableRef && this.tableRef.handleSelectionChange({ value: 2, type: 'all' });
    });
  }

  private async handleGetSearchData(type = '') {
    try {
      this.isLoading = true;
      const params: IipListParams = {
        current: this.pagination.current,
        limit: this.limit,
        tableKeyword: this.tableKeyword,
      };
      const { total, data } = await this.getSearchTableData(params, type);
      if (data.length > this.pagination.limit) {
        this.frontendPagination = true;
        this.fullData = data;
        // 如果未分页，则前端自动分页
        const { limit, current } = this.pagination;
        this.tableData = data.slice(limit * (current - 1), limit * current);
      } else {
        this.frontendPagination = false;
        this.tableData = data || [];
      }
      this.pagination.count = total || 0;
      this.handleGetDefaultSelections();
    } catch (err) {
      console.log(err);
    } finally {
      this.isLoading = false;
    }
  }

  private handlePageChange(page: number) {
    if (page === this.pagination.current) return;

    this.pagination.current = page;
    this.handleGetSearchData('page-change');
  }

  private handleLimitChange(limit: number) {
    this.pagination.limit = limit;
    this.handleGetSearchData('limit-change');
  }

  @Debounce(300)
  private handleKeywordChange() {
    this.handleGetDefaultData('keyword-change');
  }

  @Emit('check-change')
  private handleCheckChange(data: ITableCheckData) {
    const { selections, excludeData, checkType, checkValue } = data;
    let tmpSelections = selections;
    let tmpExcludeData = excludeData;
    // 前端分页
    if (this.frontendPagination && checkType === 'all') {
      // 跨页全选
      if (checkValue === 2) {
        tmpSelections = this.fullData.filter(item => excludeData?.indexOf(item) === -1);
      } else if (checkValue === 0) {
        tmpExcludeData = this.fullData.filter(item => selections.indexOf(item) === -1);
      }
    }
    this.defaultSelections = tmpSelections;
    return {
      selections: tmpSelections,
      excludeData: tmpExcludeData,
      checkType,
    };
  }
  handleClearFilter() {
    this.tableKeyword = '';
    this.handleKeywordChange();
  }
}
</script>
<style lang="scss" scoped>
.ip-list {
  height: 100%;

  .table-tab {
    display: flex;
    background-image: linear-gradient(transparent 36px, #dcdee5 0);

    &-item {
      padding: 10px 0 8px 0;
      margin-right: 20px;
      cursor: pointer;

      &.active {
        color: #3a84ff;
        border-bottom: 2px solid #3a84ff;
      }
    }
  }
}
</style>
