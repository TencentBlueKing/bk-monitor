import { Component, Ref, Prop, Watch, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import TableSkeleton from '../../../../../../../../../../../components/skeleton/table-skeleton';
import EmptyStatus from '../../../../../../../../../../../components/empty-status/empty-status';
import CommonTable from '../../../../../../../../../../../pages/monitor-k8s/components/common-table';
import type { EmptyStatusType } from '../../../../../../../../../../../components/empty-status/types';
import type { IListItem } from '../result-preview';
import { Debounce } from 'monitor-common/utils';
import type { IGroupingRule, ICustomTsFields } from '../../../../../../../../../service';
import { NULL_LABEL, type RequestHandlerMap } from '../../../../../../../../type';

import './index.scss';

export type ITableRowData = ICustomTsFields['metrics'][number];

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

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

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
  /** 是否区分大小写搜索 */
  isCaseSensitiveSearch = false;
  /** 是否精确搜索 */
  isExactSearch = false;
  /** 是否正则搜索 */
  isRegexSearch = false;
  /** 搜索类型选项列表 */
  searchTypeList = [
    { id: 'fuzzy', name: this.$t('模糊搜索') },
    { id: 'regex', name: this.$t('正则匹配') },
  ];
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
        filterable: true,
        filter_list: [],
        showOverflowTooltip: false,
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
        const name = metric.name || '';
        const alias = metric.config?.alias || '';

        if (this.isRegexSearch) {
          // 使用正则表达式匹配
          searchMatch =
            this.safeRegexMatch(this.searchValue, name, this.isCaseSensitiveSearch) ||
            this.safeRegexMatch(this.searchValue, alias, this.isCaseSensitiveSearch);
        }

        if (this.isCaseSensitiveSearch || (!this.isCaseSensitiveSearch && !this.isExactSearch && !this.isRegexSearch)) {
          // 使用模糊搜索（包含匹配）
          searchMatch =
            this.fuzzyMatch(this.searchValue, name, this.isCaseSensitiveSearch) ||
            this.fuzzyMatch(this.searchValue, alias, this.isCaseSensitiveSearch);
        }

        if (this.isExactSearch) {
          // 使用精确匹配
          searchMatch =
            this.exactMatch(this.searchValue, name, this.isCaseSensitiveSearch) ||
            this.exactMatch(this.searchValue, alias, this.isCaseSensitiveSearch);
        }
      }

      return dimensionMatch && searchMatch;
    });
    this.tableData.data = filteredMetrics.slice(
      (this.tableData.pagination.current - 1) * this.tableData.pagination.limit,
      this.tableData.pagination.current * this.tableData.pagination.limit
    );
    this.tableData.pagination.count = filteredMetrics.length;
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
   * @description: 精确匹配函数
   * @param {string} searchValue - 搜索关键词
   * @param {string} target - 目标字符串
   * @param {boolean} caseSensitive - 是否区分大小写，默认不区分
   * @return {boolean} 匹配结果
   */
  exactMatch(searchValue: string, target: string, caseSensitive = false): boolean {
    if (!searchValue || !target) return false;
    if (caseSensitive) {
      return searchValue === target;
    }
    return searchValue.toLowerCase() === target.toLowerCase();
  }

  /**
   * @description: 模糊搜索匹配函数（包含匹配）
   * @param {string} searchValue - 搜索关键词
   * @param {string} target - 目标字符串
   * @param {boolean} caseSensitive - 是否区分大小写，默认不区分
   * @return {boolean} 匹配结果
   */
  fuzzyMatch(searchValue: string, target: string, caseSensitive = false): boolean {
    if (!searchValue || !target) return false;
    // 转义特殊字符，避免被当作正则表达式
    const escapedValue = searchValue.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const flags = caseSensitive ? '' : 'i';
    const searchRegex = new RegExp(escapedValue, flags);
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
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
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
    this.isSearchChange = true;
    this.tableData.pagination.current = 1;
    this.updateTableData();
  }

  /**
   * @description: 处理表格行选择变化，忽略分页操作触发的选择变化
   * @param {ITableRowData[]} selectList - 当前选中的行数据列表
   * @return {*}
   */
  handleSelectChange(selectList: ITableRowData[]) {
    if (this.isPageChange || this.isSearchChange) {
      this.isPageChange = false;
      this.isSearchChange = false;
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
          title={
            this.isEdit
              ? this.$t('手动选择或筛选后的结果作为分组对象。')
              : this.$t('手动选择指标作为分组对象，仅支持未分组指标。')
          }
        />
        <bk-input
          class='search-input-main'
          v-model={this.searchValue}
          clearable={false}
          placeholder={this.$t('搜索 指标名、别名')}
          onInput={this.handleSearchInput}
        >
          <div
            slot='append'
            class='search-append-main'
          >
            <div
              v-bk-tooltips={this.$t('大小写敏感')}
              class={['search-item-main', { 'is-active': this.isCaseSensitiveSearch }]}
              onClick={() => {
                this.isCaseSensitiveSearch = !this.isCaseSensitiveSearch;
                this.updateTableData();
              }}
            >
              <i class='icon-monitor icon-daxiaoxie' />
            </div>
            <div
              v-bk-tooltips={this.$t('精确搜索')}
              class={['search-item-main', { 'is-active': this.isExactSearch }]}
              onClick={() => {
                this.isExactSearch = !this.isExactSearch;
                this.updateTableData();
              }}
            >
              <i class='icon-monitor icon-ab' />
            </div>
            <div
              v-bk-tooltips={this.$t('正则匹配')}
              class={['search-item-main', { 'is-active': this.isRegexSearch }]}
              onClick={() => {
                this.isRegexSearch = !this.isRegexSearch;
                this.updateTableData();
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
                  collapse-tags
                  disabled
                  allow-create
                />
              ),
              // row.dimensions.map(dimension => <bk-tag key={dimension}>{dimension}</bk-tag>),
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
