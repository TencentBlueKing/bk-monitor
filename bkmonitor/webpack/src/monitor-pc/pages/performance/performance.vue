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
  <div>
    <div class="performance">
      <!-- 筛选面板 -->
      <overview-panel
        :active="tableInstance.panelKey"
        :panel-statistics="panelStatistics"
        :loading="tableInstance.loading"
        @click="handlePanelClick"
      />
      <!-- 筛选工具栏 -->
      <performance-tool
        ref="tool"
        :check-type="checkType"
        :selection-data="selectionData"
        :exclude-data-ids="excludeDataIds"
        :selections-count="selectionsCount"
        @search-change="handleSearchChange"
        @filter-update="({ search, panelKey }) => handleUpdateRouteQuery(panelKey, search)"
      />
      <!-- 表格区域 -->
      <table-skeleton
        v-if="isLoading"
        class="table-skeleton-border"
      />
      <performance-table
        v-else
        ref="table"
        :key="tableKey"
        :columns="columns"
        :data="pagingData"
        :page-config="pageConfig"
        :all-check-value="allCheckValue"
        :check-type="checkType"
        :selection-data="selectionData"
        :exclude-data-ids="excludeDataIds"
        :selections-count="selectionsCount"
        :empty-status-type="emptyStatusType"
        :instance-loading="tableInstance.loading"
        @sort-change="handleSortChange"
        @limit-change="handleLimitChange"
        @page-change="handlePageChange"
        @ip-mark="handleIpMark"
        @row-check="handleRowCheck"
        @check-change="handleCheckChange"
        @empty-status-operation="handleOperation"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { Component, InjectReactive, Prop, Provide, Ref, Vue, Watch } from 'vue-property-decorator';

import { commonPageSizeSet } from 'monitor-common/utils';
import { typeTools } from 'monitor-common/utils/utils';

import TableSkeleton from '../../components/skeleton/table-skeleton.tsx';
import commonPageSizeMixin from '../../mixins/commonPageSizeMixin';
import PerformanceModule from '../../store/modules/performance';
import OverviewPanel from './components/overview-panel.vue';
import PerformanceTable from './components/performance-table.vue';
import PerformanceTool from './components/performance-tool.vue';
import TableStore from './table-store';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
// import { Route } from 'vue-router';
import type { ICheck, IPageConfig, IPanelStatistics, ISearchItem, ISort, ITableRow } from './performance-type';

Component.registerHooks(['beforeRouteLeave', 'beforeRouteEnter']);
@Component({
  name: 'performance',
  components: {
    OverviewPanel,
    PerformanceTool,
    PerformanceTable,
    TableSkeleton,
  },
})
export default class Performance extends Vue {
  @Prop({ default: () => [], type: Array }) readonly search: ISearchItem[];
  @Ref('table') readonly tableRef: PerformanceTable;
  @Ref('tool') readonly toolRef: PerformanceTool;
  isLoading = false;
  tableInstance: TableStore = new TableStore([], {}, this.bizIdMap);
  // 置顶信息
  sticky = {
    key: 'userStikyNote',
    id: -1,
    value: {},
  };

  // 字段显示设置存储Key
  colStorageKey = `${this.$store.getters.userName}-${this.$store.getters.bizId}`;
  // 选中项
  // selections: ITableRow[] = []
  tableKey = +new Date();
  // 获取当前分页的数据
  pagingData: ITableRow[] = [];
  // 当前页选中项
  selectionData: ITableRow[] = [];
  // 跨页全选排除法数据ID集合
  excludeDataIds: string[] = [];
  panelKeyFieldMap = {
    cpuData: 'cpu_usage',
    menmoryData: 'mem_usage',
    diskData: 'disk_in_use',
    unresolveData: 'alarm_count',
  };
  // 无状态数据接口 | 全量数据接口 记录请求响应较快的接口
  fastInterface: 'getHostPerformance' | 'getMetricHostList' = 'getHostPerformance';
  refreshIntervalInstance = null;
  panelKey = '';
  emptyStatusType: EmptyStatusType = 'empty';
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  // 立即刷新图表
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;

  @Provide('tableInstance') readonly tableStore = this.tableInstance;

  // beforeRouteEnter(to, from, next) {
  //   next((vm) => {
  //     if (from.name !== 'performance-detail' && !vm.isLoading) {
  //       vm.fastInterface = 'getHostPerformance';
  //       vm.initCondition();
  //       vm.handleInitColChecked();
  //       vm.getHostList();
  //     }
  //   });
  // }
  @Watch('refreshInterval')
  // 数据刷新间隔
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!v || +v < 60 * 1000) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.initPerformance();
    }, v);
  }
  @Watch('refreshImmediate')
  // 立刻刷新
  handleRefreshImmediateChange(v: string) {
    if (v) this.initPerformance();
  }
  get bizList() {
    return this.$store.getters.bizList;
  }
  get bizIdMap() {
    return this.$store.getters.bizIdMap;
  }
  get checkType() {
    return this.tableInstance.checkType;
  }

  // 0: 取消全选 1: 半选 2: 全选
  get allCheckValue() {
    if (this.checkType === 'current') {
      if (this.selectionData.length === 0) {
        return 0;
      }
      if (this.selectionData.length === this.pagingData.length) {
        return 2;
      }
      return 1;
    }
    if (this.excludeDataIds.length === 0) {
      return 2;
    }
    if (this.excludeDataIds.length === this.tableInstance.total) {
      return 0;
    }
    return 1;
  }

  // 筛选面板统计信息
  get panelStatistics(): IPanelStatistics {
    return {
      unresolveData: this.tableInstance.unresolveData.length,
      cpuData: this.tableInstance.cpuData.length,
      menmoryData: this.tableInstance.menmoryData.length,
      diskData: this.tableInstance.diskData.length,
    };
  }

  // 字段显示设置
  get fieldData() {
    return this.tableInstance.fieldData;
  }

  // 表格列配置
  get columns() {
    return this.tableInstance.columns;
  }
  // 当前选中条数统计
  get selectionsCount() {
    if (this.checkType === 'current') {
      return this.selectionData.length;
    }
    return this.pageConfig.total - this.excludeDataIds.length;
  }
  // 分页配置
  get pageConfig(): IPageConfig {
    return {
      page: this.tableInstance.page,
      pageSize: this.tableInstance.pageSize,
      pageList: this.tableInstance.pageList,
      total: this.tableInstance.total,
    };
  }

  created() {
    this.initPerformance();
  }
  deactivated() {
    this.tableInstance.panelKey = '';
    this.tableInstance.fieldData.forEach(item => {
      item.value = Array.isArray(item.value) ? [] : '';
    });
  }
  initPerformance() {
    this.fastInterface = 'getHostPerformance';
    this.initCondition();
    this.handleInitColChecked();
    this.getHostList();
  }
  // 初始化回显条件
  initCondition() {
    // 优先级：props > url > store
    let conditions: ISearchItem[] = [];
    const { search, panelKey } = this.getRouteSearchQuery();
    this.panelKey = panelKey;
    if (this.search?.length) {
      conditions = this.search;
    } else if (search) {
      conditions = search;
    }
    conditions.forEach(item => {
      const data = this.tableInstance.fieldData.find(data => data.id === item.id);
      if (data && !typeTools.isNull(item.value)) {
        data.value = item.value;
        data.filterChecked = true;
      }
    });
  }

  // 解析路由的query
  getRouteSearchQuery(): {
    panelKey: string;
    search: ISearchItem[];
  } {
    const searchStr = this.$route.query.search as string;
    let arr = null;
    searchStr && (arr = JSON.parse(decodeURIComponent(searchStr)));
    return {
      search: arr,
      panelKey: this.$route.query.panelKey as string,
    };
  }
  // 无状态数据
  async getHostPerformance() {
    this.isLoading = true;
    const hostData = await PerformanceModule.getHostPerformance();
    await this.$nextTick();
    if (this.fastInterface === 'getHostPerformance') {
      // 更新tableInstance
      this.tableInstance.updateData(hostData, {
        stickyValue: this.sticky.value,
        panelKey: this.panelKey,
      });
      this.getTableData();
    }
    this.isLoading = false;
    return hostData;
  }
  // 获取主机信息
  async getHostList() {
    this.isLoading = true;
    const stickyList = await PerformanceModule.getUserConfigList({
      key: this.sticky.key,
    });
    if (!stickyList.length) {
      // 如果用户配置不存在就创建配置
      PerformanceModule.createUserConfig({
        key: this.sticky.key,
        value: JSON.stringify({}),
      }).then(data => {
        this.sticky.id = data.id || -1;
      });
    } else {
      // 获取当前用户的置顶配置
      try {
        this.sticky.id = stickyList[0].id;
        this.sticky.value = JSON.parse(stickyList[0].value);
      } catch (_) {
        console.error('parse user stiky note error');
      }
    }
    const raceRes = await Promise.race([this.getHostPerformance(), this.getMetricHostList()]);
    this.fastInterface = typeTools.isObject(raceRes) ? 'getMetricHostList' : 'getHostPerformance';
    this.isLoading = false;

    // 默默的加载带有指标信息的全量数据
    // this.getMetricHostList()
  }

  // 获取全部主机信息（性能问题，异步获取）
  async getMetricHostList() {
    this.tableInstance.loading = true;
    const hostData = await PerformanceModule.getHostPerformanceMetric();
    this.tableInstance.updateData(hostData.hosts, {
      stickyValue: this.sticky.value,
      panelKey: this.panelKey,
    });
    this.handleInitColChecked();
    this.getTableData();
    this.tableInstance.loading = false;
    return hostData;
  }

  // 根据 localStorage 初始化字段显示配置
  handleInitColChecked() {
    try {
      const storeCol = JSON.parse(localStorage.getItem(this.colStorageKey)) || {};

      Object.keys(storeCol).forEach(key => {
        const index = this.tableInstance.fieldData.findIndex(item => item.id === key);
        if (index > -1) {
          this.tableInstance.fieldData[index].checked = true;
        }
      });
    } catch {
      console.error('init col checked failed');
    }
  }

  // 筛选面板点击事件
  handlePanelClick(key: string) {
    this.tableInstance.page = 1;
    this.tableInstance.panelKey = key;

    const fieldKey = this.panelKeyFieldMap[key];
    this.tableRef?.clearSort();
    if (fieldKey) {
      const fieldData = this.tableInstance.fieldData.find(item => item.id === fieldKey);
      // 默认展示筛选的列
      fieldData.checked = true;
      this.tableRef?.sort({ prop: fieldKey, order: 'descending' });
    }
    // 切换panel无需更新分类数据
    this.handleSearchChange();
    this.handleUpdateRouteQuery(key);
  }

  /** 更新路由query */
  handleUpdateRouteQuery(panelKey = this.$route.query.panelKey, search = this.$route.query.search) {
    panelKey = panelKey === '' ? undefined : panelKey;
    search = Array.isArray(search ?? [])
      ? search?.length
        ? search
        : undefined
      : JSON.parse(decodeURIComponent(search as string));
    this.$router.replace({
      name: this.$route.name,
      query: {
        panelKey,
        search: search ? encodeURIComponent(JSON.stringify(search)) : undefined,
      },
    });
  }

  // 排序
  handleSortChange({ prop, order }: ISort) {
    this.tableInstance.sortKey = prop;
    this.tableInstance.order = order;
    this.reOrderData();
  }

  // 每页条数
  handleLimitChange(limit: number) {
    this.tableInstance.page = 1;
    this.tableInstance.pageSize = limit;
    commonPageSizeSet(limit);
    this.handleResetCheck();
    this.reLimitData();
  }

  // 分页
  handlePageChange(page: number) {
    this.tableInstance.page = page;
    this.checkType === 'current' && this.handleResetCheck();
    this.reLimitData();
  }

  // 搜索表更事项
  handleSearchChange() {
    this.emptyStatusType = this.tableInstance.keyWord ? 'search-empty' : 'empty';
    this.handleResetCheck();
    this.getTableData();
  }

  // 重置勾选项
  handleResetCheck() {
    this.selectionData = [];
    this.excludeDataIds = [];
  }

  async handleIpMark(row: ITableRow) {
    this.isLoading = true;
    if (this.sticky.value[row.rowId]) {
      delete this.sticky.value[row.rowId];
    } else {
      this.sticky.value[row.rowId] = 1;
    }
    const result = await PerformanceModule.updateUserConfig({
      id: this.sticky.id,
      value: JSON.stringify(this.sticky.value),
    });
    if (result) {
      const data = this.pagingData.find(item => item.rowId === row.rowId);
      this.tableInstance.stickyValue = this.sticky.value;
      this.tableInstance.setState(row.rowId, 'mark', !data.mark);
      this.tableKey = +new Date();
      this.$nextTick(() => {
        this.handleSearchChange();
      });
    }
    this.isLoading = false;
  }

  // 行勾选事件
  handleRowCheck({ value, row }: { row: ITableRow; value: boolean }) {
    const { checkType } = this.tableInstance;
    if (checkType === 'current') {
      if (value) {
        this.selectionData.push(row);
      } else {
        const index = this.selectionData.findIndex(item => item.rowId === row.rowId);
        index > -1 && this.selectionData.splice(index, 1);
      }
    } else {
      if (value) {
        const index = this.excludeDataIds.findIndex(id => id === row.rowId);
        index > -1 && this.excludeDataIds.splice(index, 1);
      } else {
        this.excludeDataIds.push(row.rowId);
      }
    }
  }

  // 全选或者取消全选
  handleCheckChange({ value, type }: ICheck) {
    this.tableInstance.checkType = type;
    this.selectionData = type === 'current' && value === 2 ? [...this.pagingData] : [];
    this.excludeDataIds = [];
    this.$nextTick(() => {
      this.tableRef.updateDataSelection();
    });
  }
  // 重新获取表格数据（耗时操作）
  getTableData() {
    this.pagingData = this.tableInstance.getTableData();
  }
  // 重新分页数据
  reLimitData() {
    this.pagingData = this.tableInstance.reLimitData();
  }
  // 重新排序缓存数据
  reOrderData() {
    this.pagingData = this.tableInstance.reOrderData();
  }

  private handleOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.tableInstance.keyWord = '';
      this.toolRef.handleChangeKeyword('');
      this.handleSearchChange();
      return;
    }
    if (type === 'refresh') {
      this.getHostList();
      return;
    }
  }
}
</script>

<style lang="scss" scoped>
.performance {
  // margin: 24px;
  width: 100%;
  background: #fff;

  :deep(.progress-bar) {
    box-shadow: none;
  }

  &.performance-laoding {
    min-height: calc(100vh - 80px);
  }

  .table-skeleton-border {
    padding: 16px;
    border: 1px solid #dcdee5;
  }
}
</style>
