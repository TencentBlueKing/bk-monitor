import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import TableSkeleton from '@/components/skeleton/table-skeleton';
import EmptyStatus from '@/components/empty-status/empty-status';
import { getCustomTsFields } from '@/pages/custom-escalation/service';
import CommonTable from '@/pages/monitor-k8s/components/common-table';
import type { EmptyStatusType } from '@/components/empty-status/types';
import type { IListItem } from '../result-preview';
import { Debounce } from 'monitor-common/utils';
import type { IGroupingRule } from '../../../../../../../../../service';
import { NULL_LABEL } from '../../../../../../../../type';

import './index.scss';

export type ITableRowData = ServiceReturnType<typeof getCustomTsFields>['metrics'][number];

@Component({
  name: 'ManualGroup',
})
export default class ManualGroup extends tsc<any> {
  /** 分组规则信息 */
  @Prop() groupInfo: IGroupingRule;
  /** 已手动选择的指标列表 */
  @Prop({ default: () => [] }) manualList: IListItem[];

  /** 表格组件引用 */
  @Ref('tableRef') readonly tableRef!: InstanceType<typeof CommonTable>;

  /** 空状态类型 */
  emptyType: EmptyStatusType = 'empty';
  /** 搜索类型：'fuzzy' 模糊搜索 | 'regex' 正则匹配 */
  searchType = 'fuzzy';
  /** 搜索关键词 */
  searchValue = '';
  /** 所有指标数据（已过滤后的完整列表） */
  totalMetrics: ITableRowData[] = [];
  /** 过滤条件对象，key 为列名，value 为选中的过滤值数组 */
  filtersObj: Record<string, string[]> = {};
  /** 搜索类型选项列表 */
  searchTypeList = [
    { id: 'fuzzy', name: this.$t('模糊搜索') },
    { id: 'regex', name: this.$t('正则匹配') },
  ];
  /** 标识是否正在执行分页操作，用于避免分页时的选择变化触发事件 */
  isPageChange: boolean = false;
  /** 表格配置数据 */
  tableData = {
    checkable: false,
    defaultSize: 'small',
    hasColumnSetting: true,
    paginationType: 'normal',
    maxHeight: window.innerHeight - 410,
    columns: [
      { id: 'field_id', name: '', type: 'scoped_slots', props: { type: 'selection', width: 50 } },
      { id: 'name', name: this.$t('指标名'), type: 'scoped_slots', props: { minWidth: 150 } },
      { id: 'alias', name: this.$t('别名'), type: 'scoped_slots', props: { minWidth: 150 } },
      {
        id: 'dimensions',
        name: this.$t('关联维度'),
        type: 'scoped_slots',
        filterable: true,
        filter_list: [],
        props: {
          minWidth: 200,
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

  /**
   * @description: 处理手动列表变化，同步已选中的行状态
   * @return {*}
   */
  @Watch('totalMetrics', { immediate: true })
  @Watch('manualList', { immediate: true })
  handleManualListChange() {
    if (this.manualList.length && this.totalMetrics.length) {
      // 延迟执行，更新已选中的行
      setTimeout(() => {
        const manualListId = this.manualList.map(item => item.id);
        const needSelectRows = this.totalMetrics.filter(item => manualListId.includes(item.id));
        for (const row of needSelectRows) {
          this.toggleRowSelection(row, true);
        }
      });
    }
  }

  /**
   * @description: 更新表格数据，根据搜索条件和过滤条件筛选数据并分页
   * @return {*}
   */
  updateTableData() {
    const { dimensions } = this.filtersObj;
    const filteredMetrics = this.totalMetrics.filter(metric => {
      // 维度过滤
      const dimensionMatch = dimensions?.length
        ? dimensions.some(dimension => metric.dimensions.includes(dimension))
        : true;

      // 搜索匹配
      let searchMatch = true;
      if (this.searchValue) {
        if (this.searchType === 'regex') {
          // 使用正则匹配
          searchMatch =
            this.safeRegexMatch(this.searchValue, metric.name) ||
            this.safeRegexMatch(this.searchValue, metric.config.alias);
        } else {
          // 使用模糊搜索
          searchMatch =
            this.fuzzyMatch(this.searchValue, metric.name) || this.fuzzyMatch(this.searchValue, metric.config.alias);
        }
      }

      return dimensionMatch && searchMatch;
    });
    this.tableData.data = filteredMetrics.slice(
      (this.tableData.pagination.current - 1) * this.tableData.pagination.limit,
      this.tableData.pagination.current * this.tableData.pagination.limit
    );
    this.$nextTick(() => {
      this.handleManualListChange();
    });
  }

  /**
   * @description: 安全的正则表达式匹配函数
   * @param {string} pattern - 用户输入的正则表达式字符串
   * @param {string} target - 目标字符串
   * @param {boolean} caseSensitive - 是否区分大小写，默认不区分
   * @return {boolean} 匹配结果，如果正则表达式无效则返回 false
   */
  safeRegexMatch(pattern: string, target: string, caseSensitive = false): boolean {
    if (!pattern || !target) return false;
    try {
      const flags = caseSensitive ? '' : 'i';
      const regex = new RegExp(pattern, flags);
      return regex.test(target);
    } catch (error) {
      // 正则表达式无效时，返回 false 或可以回退到模糊搜索
      console.warn('Invalid regex pattern:', pattern, error);
      return false;
    }
  }

  /**
   * @description: 模糊搜索匹配函数
   * @param {string} searchValue - 搜索关键词
   * @param {string} target - 目标字符串
   * @return {boolean} 匹配结果
   */
  fuzzyMatch(searchValue: string, target: string): boolean {
    if (!searchValue || !target) return false;
    const searchRegex = new RegExp(searchValue, 'i');
    return searchRegex.test(target);
  }

  /**
   * @description: 处理分页变化
   * @param {number} page - 当前页码
   * @return {*}
   */
  handlePageChange(page: number) {
    this.isPageChange = true;
    this.tableData.pagination.current = page;
    this.updateTableData();
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
      this.updateTableData();
    }
  }

  /**
   * @description: 初始化表格数据，从接口获取指标数据并设置过滤选项
   * @return {*}
   */
  initTableData() {
    this.tableData.loading = true;
    getCustomTsFields({
      time_series_group_id: Number(this.$route.params.id),
    })
      .then(res => {
        const filteredMetrics = res.metrics.filter(
          item => item.scope.name === NULL_LABEL || item.scope.id === this.groupInfo.scope_id
        );
        const dimensionFilterList = filteredMetrics.reduce<Set<string>>((dataSet, item) => {
          for (const dimension of item.dimensions) {
            dataSet.add(dimension);
          }
          return dataSet;
        }, new Set());
        this.tableData.columns[3].filter_list = Array.from(dimensionFilterList).map(dimension => ({
          text: dimension,
          value: dimension,
        }));
        this.totalMetrics = filteredMetrics;
        this.tableData.pagination.count = this.totalMetrics.length;
        this.$emit('totalMetricsChange', this.totalMetrics);
        this.updateTableData();
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
    this.tableData.pagination.current = 1;
    this.updateTableData();
  }

  /**
   * @description: 处理表格行选择变化，忽略分页操作触发的选择变化
   * @param {ITableRowData[]} selectList - 当前选中的行数据列表
   * @return {*}
   */
  handleSelectChange(selectList: ITableRowData[]) {
    if (this.isPageChange) {
      this.isPageChange = false;
      return;
    }

    this.$emit('selectChange', selectList);
  }

  /**
   * @description: 处理表格列过滤变化，重置到第一页并更新表格数据
   * @param {Record<string, string[]>} filters - 过滤条件对象，key 为列名，value 为选中的过滤值数组
   * @return {*}
   */
  handleFilterChange(filters: Record<string, string[]>) {
    this.filtersObj = filters;
    this.tableData.pagination.current = 1;
    this.updateTableData();
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

  created() {
    this.initTableData();
  }

  render() {
    return (
      <div class='manual-group-main'>
        <bk-alert
          type='info'
          title={this.$t('手动选择或筛选后的结果作为分组对象。')}
        />
        <bk-input
          class='search-input-main'
          v-model={this.searchValue}
          clearable
          right-icon='bk-icon icon-search'
          onInput={this.handleSearchInput}
        >
          <bk-select
            slot='prepend'
            clearable={false}
            v-model={this.searchType}
            ext-cls='search-type-select'
          >
            {this.searchTypeList.map(option => (
              <bk-option
                key={option.id}
                id={option.id}
                name={option.name}
              />
            ))}
          </bk-select>
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
              alias: (row: ITableRowData) => <span>{row.config.alias}</span>,
              dimensions: (row: ITableRowData) =>
                row.dimensions.map(dimension => <bk-tag key={dimension}>{dimension}</bk-tag>),
            }}
            onLimitChange={this.handlePageLimitChange}
            onPageChange={this.handlePageChange}
            onSelectChange={this.handleSelectChange}
            onFilterChange={this.handleFilterChange}
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
