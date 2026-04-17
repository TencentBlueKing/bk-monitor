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
import { Component, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Debounce } from 'monitor-common/utils';

import EmptyStatus from '../../../../../../../../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../../../../../../../../components/skeleton/table-skeleton';
import CommonTable from '../../../../../../../../../../../pages/monitor-k8s/components/common-table';
import type { RequestHandlerMap } from '../../../../../../../../type';

import type { EmptyStatusType } from '../../../../../../../../../../../components/empty-status/types';
import type { ICustomTsFields, IGroupingRule } from '../../../../../../../../../service';
import type { IListItem } from '../result-preview';

import './index.scss';

/** 指标表格行数据类型 */
export type ITableRowData = ICustomTsFields['list'][number];

/**
 * 手动分组组件
 * 以表格形式展示所有指标，支持搜索、分页、多选，用于手动选择指标加入分组
 */
@Component({
  name: 'ManualGroup',
})
export default class ManualGroup extends tsc<any> {
  /** 是否为编辑模式 */
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  /** 分组规则信息 */
  @Prop() groupInfo: IGroupingRule;
  /** 已手动选择的指标列表 */
  @Prop({ default: () => [] }) manualList: IListItem[];
  /** 默认分组信息 */
  @Prop({ default: () => {} }) defaultGroupInfo: { id: number; name: string };

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 表格组件引用 */
  @Ref('tableRef') readonly tableRef!: InstanceType<typeof CommonTable>;

  /** 指标筛选条件对象 */
  metricSearchObj: ServiceParameters<typeof this.requestHandlerMap.getCustomTsFields>['conditions'] = [
    {
      key: 'name',
      values: [],
      search_type: 'fuzzy',
    },
    {
      key: 'field_config_alias',
      values: [],
      search_type: 'fuzzy',
    },
  ];

  /** 空状态类型 */
  emptyType: EmptyStatusType = 'empty';
  /** 搜索关键词 */
  searchValue = '';
  /** 过滤条件对象，key 为列名，value 为选中的过滤值数组 */
  filtersObj: Record<string, string[]> = {};
  /** 是否区分大小写搜索 */
  isCaseSensitiveSearch = false;
  /** 是否精确搜索 */
  isExactSearch = false;
  /** 是否正则搜索 */
  isRegexSearch = false;
  /** 标识是否正在执行分页操作，用于避免分页时的选择变化触发事件 */
  isPageChange = false;
  /** 标识是否正在执行搜索操作 */
  isSearchChange = false;
  /** 表格配置数据 */
  tableData = {
    checkable: false,
    defaultSize: 'small',
    hasColumnSetting: true,
    paginationType: 'normal',
    maxHeight: window.innerHeight - 410,
    columns: [
      { id: 'field_id', name: '', type: 'scoped_slots', props: { type: 'selection', width: 50 } },
      { id: 'name', name: this.$t('指标名'), type: 'scoped_slots', props: { minWidth: 150 }, disabled: true },
      { id: 'alias', name: this.$t('别名'), type: 'scoped_slots', props: { minWidth: 150 } },
      {
        id: 'dimensions',
        name: this.$t('关联维度'),
        type: 'scoped_slots',
        filter_list: [],
        showOverflowTooltip: false,
        props: {
          minWidth: 200,
          filterSearchable: true,
        },
      },
    ],
    pagination: {
      count: 0,
      current: 1,
      limit: 20,
      showTotalCount: true,
    },
    loading: false,
    data: [] as ITableRowData[],
  };
  isUpdateResults = true;

  get manualListIdSet() {
    return new Set(this.manualList.map(item => item.id));
  }

  get currentTablePageDataIdSet() {
    return new Set(this.tableData.data.map(item => item.id));
  }

  /**
   * @description: 处理手动列表变化，同步已选中的行状态
   * @return {*}
   */
  @Watch('manualList', { immediate: true })
  handleManualListChange() {
    if (this.manualList.length) {
      // 延迟执行，更新已选中的行
      this.isUpdateResults = false;
      setTimeout(() => {
        const manualListId = this.manualList.map(item => item.id);
        const needSelectRows = this.tableData.data.filter(item => manualListId.includes(item.id));
        for (const row of needSelectRows) {
          this.toggleRowSelection(row, true);
        }
        this.isUpdateResults = true;
      });
    }
  }

  @Watch('isCaseSensitiveSearch')
  @Watch('isExactSearch')
  @Watch('isRegexSearch')
  handleSearchTypeChange() {
    this.$nextTick(() => {
      if (this.isCaseSensitiveSearch && !this.isExactSearch && !this.isRegexSearch) {
        for (const item of this.metricSearchObj) {
          item.search_type = 'fuzzy_case_sensitive';
        }
      } else if (this.isExactSearch && !this.isCaseSensitiveSearch && !this.isRegexSearch) {
        for (const item of this.metricSearchObj) {
          item.search_type = 'exact';
        }
      } else if (this.isRegexSearch && !this.isCaseSensitiveSearch && !this.isExactSearch) {
        for (const item of this.metricSearchObj) {
          item.search_type = 'regex';
        }
      } else if (this.isCaseSensitiveSearch && this.isExactSearch && !this.isRegexSearch) {
        for (const item of this.metricSearchObj) {
          item.search_type = 'exact_case_sensitive';
        }
      } else if (this.isCaseSensitiveSearch && this.isRegexSearch && !this.isExactSearch) {
        for (const item of this.metricSearchObj) {
          item.search_type = 'regex_case_sensitive';
        }
      } else {
        for (const item of this.metricSearchObj) {
          item.search_type = 'fuzzy';
        }
      }
    });
  }


  /**
   * @description: 处理分页变化
   * @param {number} page - 当前页码
   * @return {*}
   */
  handlePageChange(page: number) {
    this.isPageChange = true;
    this.tableData.pagination.current = page;
    this.isUpdateResults = false;
    this.fetchTableData();
  }

  /**
   * @description: 处理每页显示数量变化
   * @param {number} size - 每页显示数量
   * @return {*}
   */
  handlePageLimitChange(size: number) {
    this.isPageChange = true;
    if (size !== this.tableData.pagination.limit) {
      this.tableData.pagination.limit = size;
      this.tableData.pagination.current = 1;
      this.isUpdateResults = false;
      this.fetchTableData();
    }
  }

  /**
   * @description: 获取指标表格数据
   * @return {*}
   */
  fetchTableData() {
    this.tableData.loading = true;
    const scopeIds = [this.defaultGroupInfo.id];
    if (this.groupInfo.id) {
      scopeIds.push(this.groupInfo.id);
    }
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
      page: this.tableData.pagination.current,
      page_size: this.tableData.pagination.limit,
      mandatory_conditions: [
        {
          key: 'scope_id',
          values: scopeIds,
          search_type: 'exact' as const,
        },
      ],
      conditions: this.metricSearchObj,
      condition_connector: 'or' as const,
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    this.requestHandlerMap
      .getCustomTsFields(params)
      .then(res => {
        this.tableData.pagination.count = res.total;
        this.tableData.data = res.list;
        this.$emit('metricListChange', res.list);
        this.$nextTick(() => {
          this.handleManualListChange();
          // 搜索或者切换每页条数后首次选择失效问题
          this.isSearchChange = false;
          this.isPageChange = false;
        });
      })
      .finally(() => {
        this.tableData.loading = false;
      });
  }

  /**
   * @description: 处理搜索输入，防抖处理，重置到第一页并更新表格数据
   * @return {*}
   */
  @Debounce(500)
  handleSearchInput() {
    this.isSearchChange = true;
    for (const item of this.metricSearchObj) {
      item.values = this.searchValue ? [this.searchValue] : [];
    }
    this.tableData.pagination.current = 1;
    this.fetchTableData();
  }

  /**
   * @description: 处理表格行选择变化，忽略分页操作触发的选择变化
   * @param {ITableRowData[]} selectList - 当前选中的行数据列表
   * @return {*}
   */
  handleSelectChange(selectList: ITableRowData[]) {
    if (!this.isUpdateResults) {
      return;
    }

    if (this.isPageChange || this.isSearchChange) {
      this.isPageChange = false;
      this.isSearchChange = false;
      return;
    }

    const selectListIdSet = new Set(selectList.map(item => item.id));
    const deleteIdSet = new Set();
    const addList = [];
    for (const item of selectList) {
      if (!this.manualListIdSet.has(item.id)) {
        addList.push(item);
      }
    }
    for (const item of this.tableData.data) {
      if (!selectListIdSet.has(item.id)) {
        deleteIdSet.add(item.id);
      }
    }
    const finalList = [...addList, ...this.manualList].filter(item => !deleteIdSet.has(item.id));
    this.$emit('selectChange', finalList);
  }

  /**
   * @description: 处理表格列过滤变化，重置到第一页并更新表格数据
   * @param {Record<string, string[]>} filters - 过滤条件对象，key 为列名，value 为选中的过滤值数组
   * @return {*}
   */
  handleFilterChange(filters: Record<string, string[]>) {
    this.filtersObj = filters;
    this.tableData.pagination.current = 1;
    this.fetchTableData();
  }

  /**
   * @description: 清除表格中所有选中的行
   * @return {*}
   */
  clearSelect() {
    this.tableRef?.handleClearSelected();
  }

  /**
   * @description: 切换表格行的选中状态
   * @param {ITableRowData} row - 要切换的行数据
   * @param {boolean} checked - 是否选中
   * @return {*}
   */
  toggleRowSelection(row: ITableRowData, checked: boolean) {
    this.tableRef?.$refs.table.toggleRowSelection(row, checked);
  }

  // /** 组件创建时获取初始表格数据 */
  created() {
    this.fetchTableData();
  }

  render() {
    return (
      <div class='manual-group-main'>
        <bk-alert
          title={
            this.isEdit
              ? this.$t('手动选择或筛选后的结果作为分组对象。')
              : this.$t('手动选择指标作为分组对象，仅支持未分组指标。')
          }
          type='info'
        />
        <bk-input
          class='search-input-main'
          v-model={this.searchValue}
          clearable={false}
          placeholder={this.$t('搜索 指标名、别名')}
          onInput={this.handleSearchInput}
        >
          <div
            class='search-append-main'
            slot='append'
          >
            <div
              class={['search-item-main', { 'is-active': this.isCaseSensitiveSearch }]}
              v-bk-tooltips={this.$t('大小写敏感')}
              onClick={() => {
                this.isCaseSensitiveSearch = !this.isCaseSensitiveSearch;
                this.fetchTableData();
              }}
            >
              <i class='icon-monitor icon-daxiaoxie' />
            </div>
            <div
              class={['search-item-main', { 'is-active': this.isExactSearch }]}
              v-bk-tooltips={this.$t('精确搜索')}
              onClick={() => {
                this.isExactSearch = !this.isExactSearch;
                this.fetchTableData();
              }}
            >
              <i class='icon-monitor icon-ab' />
            </div>
            <div
              class={['search-item-main', { 'is-active': this.isRegexSearch }]}
              v-bk-tooltips={this.$t('正则匹配')}
              onClick={() => {
                this.isRegexSearch = !this.isRegexSearch;
                this.fetchTableData();
              }}
            >
              <i class='icon-monitor icon-tongpeifu' />
            </div>
          </div>
        </bk-input>
        {this.tableData.loading ? (
          <TableSkeleton
            class='mt-16'
            type={2}
          />
        ) : (
          <CommonTable
            ref='tableRef'
            {...{ props: this.tableData }}
            scopedSlots={{
              name: (row: ITableRowData) => <span>{row.name}</span>,
              alias: (row: ITableRowData) => <span>{row.config.alias || '--'}</span>,
              dimensions: (row: ITableRowData) => (
                <bk-tag-input
                  class='dimension-display'
                  v-model={row.dimensions}
                  allow-create
                  collapse-tags
                  disabled
                />
              ),
              // row.dimensions.map(dimension => <bk-tag key={dimension}>{dimension}</bk-tag>),
            }}
            onFilterChange={this.handleFilterChange}
            onLimitChange={this.handlePageLimitChange}
            onPageChange={this.handlePageChange}
            onSelectChange={this.handleSelectChange}
          >
            <div slot='empty'>
              <EmptyStatus type={this.emptyType} />
            </div>
          </CommonTable>
        )}
      </div>
    );
  }
}
