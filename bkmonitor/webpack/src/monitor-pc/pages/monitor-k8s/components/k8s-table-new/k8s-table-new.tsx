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
import { Prop, Component, Emit, Watch, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { connect, disconnect } from 'echarts/core';
import { random } from 'monitor-common/utils/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import MiniTimeSeries from 'monitor-ui/chart-plugins/plugins/mini-time-series/mini-time-series';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { K8sNewTabEnum, K8sTableColumnKeysEnum, type SceneType } from '../../typings/k8s-new';
import K8sDetailSlider, { type K8sDetailSliderActiveTitle } from '../k8s-detail-slider/k8s-detail-slider';
import K8sDimensionDrillDown from '../k8s-left-panel/k8s-dimension-drilldown';
import { getK8sTableAsyncDataMock, getK8sTableDataMock } from './utils';

import type { K8sGroupDimension } from '../../k8s-dimension';
import type { ITableItemMap } from '../../typings/table';
import type { IFilterByItem } from '../filter-by-condition/utils';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { TranslateResult } from 'vue-i18n';

import './k8s-table-new.scss';

/**
 * @description k8s 表格列配置类型
 */
export interface K8sTableColumn {
  /** 字段类型 */
  type: K8sTableColumnTypeEnum;
  /** 字段id */
  id: K8sTableColumnKeysEnum;
  /** 字段名称 */
  name: TranslateResult;
  /** 是否伸缩大小 */
  resizable?: boolean;
  /** 是否可以排序 */
  sortable?: 'custom' | boolean;
  /** 列宽 */
  width?: number;
  /** 最小列宽 */
  min_width?: number;
  /** 是否需要异步加载 */
  asyncable?: boolean;
  /** 是否开启 添加/移除 筛选项 icon */
  k8s_filter?: boolean;
  /** 是否开启 下钻 icon */
  k8s_group?: boolean;
  /** 自定义获取值逻辑函数 */
  getValue?: (row: K8sTableRow) => unknown;
}

export type K8sTableRow = Pick<ITableItemMap, 'datapoints'>['datapoints'] | Record<string, string>;

export interface K8sTableSort {
  prop: K8sTableColumnKeysEnum.CPU | K8sTableColumnKeysEnum.INTERNAL_MEMORY | null;
  order: 'ascending' | 'descending' | null;
}

export interface K8sTableClickEvent {
  column: K8sTableColumn;
  row: K8sTableRow;
  index: number;
}

export type K8sTableFilterByEvent = { groupId: K8sTableColumnKeysEnum; ids: Array<number | string> };
export type K8sTableGroupByEvent = { groupId: K8sTableColumnKeysEnum; checked: boolean };

interface K8sTableNewProps {
  /** 当前选中的 tab 项 */
  activeTab: K8sNewTabEnum;
  /** GroupBy 选择器选中数据类实例 */
  groupInstance: K8sGroupDimension;
  /** 筛选 Filter By 过滤项 */
  filterBy: IFilterByItem[];
  /** 场景 */
  scene: SceneType;
  /** 集群Id */
  clusterId: string;
}
interface K8sTableNewEvent {
  onFilterChange: (item: K8sTableFilterByEvent) => void;
  onGroupChange: (item: K8sTableGroupByEvent) => void;
  onClearSearch: () => void;
}

/**
 * @enum k8s 表格列类型枚举
 */
export enum K8sTableColumnTypeEnum {
  DATA_CHART = 'data_chart',
  RESOURCES_TEXT = 'resources_text',
}

/**
 * @description: k8s table 数据明细 table 动态列 keys
 */
const tabToTableDetailColumnDynamicKeys = [
  K8sTableColumnKeysEnum.CLUSTER,
  K8sTableColumnKeysEnum.NAMESPACE,
  K8sTableColumnKeysEnum.WORKLOAD,
  K8sTableColumnKeysEnum.WORKLOAD_TYPE,
  K8sTableColumnKeysEnum.POD,
  K8sTableColumnKeysEnum.CONTAINER,
];

/**
 * @description: k8s table 数据明细 table 静态列（必有） keys
 */
const tabToTableDetailColumnFixedKeys = [K8sTableColumnKeysEnum.CPU, K8sTableColumnKeysEnum.INTERNAL_MEMORY];

@Component
export default class K8sTableNew extends tsc<K8sTableNewProps, K8sTableNewEvent> {
  /** k8s table ResourcesText 类型列 获取值静态方法  */
  static getResourcesTextRowValue(row: K8sTableRow, column: K8sTableColumn) {
    if (column?.getValue) {
      return column.getValue(row) || '--';
    }
    return row?.[column.id] || '--';
  }

  /** workload / workload_type 不同场景下的获取值逻辑  */
  static getWorkloadValue(columnKey: K8sTableColumnKeysEnum, index: 0 | 1) {
    return row => (row?.[columnKey] as string)?.split(':')?.[index] || '--';
  }

  tableLoading = {
    /** table 骨架屏 loading */
    loading: false,
    /** 表格触底加载更多 loading  */
    scrollLoading: false,
  };

  /** 当切换 tab 时进行刷新以达到清楚table中 sort 的状态 */
  refreshKey = random(10);
  /** 表格滚动分页配置 */
  pagination = {
    page: 1,
    pageSize: 20,
    pageType: 'scrolling',
  };
  /** 表格列排序配置 */
  sortContainer = {
    prop: K8sTableColumnKeysEnum.CPU,
    order: 'descending',
    /** 处理 table 设置了 default-sort 时导致初始化时会自动走一遍sort-change事件问题 */
    initDone: false,
  };
  /** 接口返回表格数据 */
  tableData: { count: number; items: K8sTableRow[] } = {
    count: 0,
    items: [],
  };
  /** 是否显示抽屉页 */
  sliderShow = false;
  /** 当前点击的数据行索引 */
  activeRowIndex = -1;
  /** 当前点击的数据列 */
  activeTitle: K8sDetailSliderActiveTitle = { tag: '--', field: '--' };
  /** 图表异步请求数据缓存 */
  asyncDataCache = new Map();

  /** 当前页面 tab */
  @Prop({ type: String, default: K8sNewTabEnum.LIST }) activeTab: K8sNewTabEnum;
  /** GroupBy 选择器选中数据类实例 */
  @Prop({ type: Object }) groupInstance: K8sGroupDimension;
  /** FilterBy 选择器选中数据 */
  @Prop({ type: Array, default: () => [] }) filterBy: IFilterByItem[];
  /** 场景 */
  @Prop({ type: String }) scene: SceneType;
  /** 集群 */
  @Prop({ type: String }) clusterId: string;
  // 数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;

  get isListTab() {
    return this.activeTab === K8sNewTabEnum.LIST;
  }

  get tableRowKey() {
    if (this.isListTab) {
      return this.groupInstance.getLastGroupFilter();
    }
    const dimensions = this.groupInstance.dimensions;
    const len = dimensions.length;
    return dimensions[len - 1];
  }

  get tableColumns() {
    const map = this.getKeyToTableColumnsMap();
    const columns: K8sTableColumn[] = [];
    let iterationTarget = tabToTableDetailColumnDynamicKeys;
    if (this.isListTab) {
      iterationTarget = [...this.groupInstance.groupFilters].reverse();
    }
    const addColumn = (arr, targetArr = []) => {
      for (const key of targetArr) {
        const column = map[key];
        if (column) {
          const groupDimensions = this.groupInstance.dimensions;
          // 维度值不重复的维度不展示筛选 icon
          if (this.isListTab && column.id === groupDimensions[groupDimensions.length - 1]) {
            column.k8s_filter = false;
          }
          arr.push(column);
        }
      }
    };
    addColumn(columns, iterationTarget);
    addColumn(columns, tabToTableDetailColumnFixedKeys);
    return columns;
  }

  /** 缩略图分组Id枚举 */
  get chartGroupIdsMap() {
    return this.tableColumns.reduce((acc, cur, ind) => {
      if (cur.type === K8sTableColumnTypeEnum.DATA_CHART) {
        if (acc[cur.id]) disconnect(acc[cur.id]);
        acc[cur.id] = `${random(8)}_${ind}`;
        connect(acc[cur.id]);
      }
      return acc;
    }, {});
  }

  @Watch('activeTab')
  onActiveTabChange(v) {
    if (v !== K8sNewTabEnum.CHART) {
      // 重新渲染，从而刷新 table sort 状态
      this.getK8sList({ needRefresh: true });
    }
  }

  @Watch('groupInstance.groupFilters')
  onGroupFiltersChange() {
    this.getK8sList({ needRefresh: true });
  }

  @Watch('filterBy')
  onFilterByChange() {
    this.getK8sList({ needRefresh: true });
  }

  @Emit('filterChange')
  filterChange(groupId: K8sTableColumnKeysEnum, ids: Array<number | string>) {
    return { groupId, ids };
  }

  @Emit('groupChange')
  groupChange(groupId: K8sTableColumnKeysEnum) {
    return { groupId, checked: true };
  }

  @Emit('clearSearch')
  clearSearch() {
    return {};
  }

  created() {
    this.getK8sList();
  }

  getKeyToTableColumnsMap(): Record<K8sTableColumnKeysEnum, K8sTableColumn> {
    const { CLUSTER, POD, WORKLOAD_TYPE, WORKLOAD, NAMESPACE, CONTAINER, CPU, INTERNAL_MEMORY } =
      K8sTableColumnKeysEnum;

    return {
      [CLUSTER]: {
        id: CLUSTER,
        name: this.$t('cluster'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 90,
      },
      [POD]: {
        id: POD,
        name: this.$t('Pod'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 260,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [WORKLOAD_TYPE]: {
        id: WORKLOAD_TYPE,
        name: this.$t('workload_type'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        getValue: K8sTableNew.getWorkloadValue(K8sTableColumnKeysEnum.WORKLOAD, 1),
      },
      [WORKLOAD]: {
        id: WORKLOAD,
        name: this.$t('workload'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
        getValue: !this.isListTab ? K8sTableNew.getWorkloadValue(K8sTableColumnKeysEnum.WORKLOAD, 0) : null,
      },
      [NAMESPACE]: {
        id: NAMESPACE,
        name: this.$t('namespace'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 100,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [CONTAINER]: {
        id: CONTAINER,
        name: this.$t('container'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 120,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [CPU]: {
        id: CPU,
        name: this.$t('CPU使用率'),
        sortable: 'custom',
        type: K8sTableColumnTypeEnum.DATA_CHART,
        min_width: 180,
        asyncable: true,
      },
      [INTERNAL_MEMORY]: {
        id: INTERNAL_MEMORY,
        name: this.$t('内存使用率'),
        sortable: 'custom',
        type: K8sTableColumnTypeEnum.DATA_CHART,
        min_width: 180,
        asyncable: true,
      },
    };
  }

  /**
   * @description 重新渲染表格组件（主要是为了处理 table column 的 sort 状态）
   */
  refreshTable() {
    this.refreshKey = random(10);
  }

  /**
   * @description 获取k8s列表
   * @param {boolean} config.needRefresh 是否需要刷新表格状态
   * @param {boolean} config.needIncrement 是否需要增量加载（table 触底加载）
   */
  async getK8sList(config: { needRefresh?: boolean; needIncrement?: boolean } = {}) {
    let loadingKey = 'scrollLoading';
    if (!config.needIncrement) {
      this.pagination.page = 1;
      loadingKey = 'loading';
      this.asyncDataCache.clear();
    }

    this.tableLoading[loadingKey] = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const resourceType = this.groupInstance?.getLastGroupFilter();
    const filter_dict = this.filterBy.reduce((prev, curr) => {
      if (curr.value?.length) {
        prev[curr.key] = curr.value;
      }
      return prev;
    }, {});
    const requestParam = {
      bk_biz_id: 2,
      bcs_cluster_id: this.clusterId,
      resource_type: resourceType,
      filter_dict,
      start_time: startTime,
      end_time: endTime,
      sernario: this.scene,
      with_history: false,
      page_size: this.pagination.pageSize,
      page: this.pagination.page,
      page_type: this.pagination.pageType,
    };
    const data = await getK8sTableDataMock(requestParam);
    const resourceParam = this.formatTableData(data.items, resourceType);
    this.tableData = data;

    if (config.needRefresh) {
      this.sortContainer = {
        prop: K8sTableColumnKeysEnum.CPU,
        order: 'descending',
        /** 处理 table 设置了 default-sort 时导致初始化时会自动走一遍sort-change事件问题 */
        initDone: false,
      };
      this.refreshTable();
    }
    this.tableLoading[loadingKey] = false;
    this.loadAsyncData(startTime, endTime, resourceType, resourceParam);
  }

  /**
   * @description 格式化接口数据结构为table需要的数据结构，并返回异步请求加载 图表数据 时需要数据
   */
  formatTableData(
    tableData: K8sTableRow[],
    resourceType: K8sTableColumnKeysEnum
  ): { ids: string[]; tableDataMap: Record<string, number> } {
    return tableData.reduce(
      (prev, curr, index) => {
        const id = curr[resourceType] as string;
        if (this.asyncDataCache.has(id)) {
          const item = this.asyncDataCache.get(id);
          curr[K8sTableColumnKeysEnum.CPU] = item[K8sTableColumnKeysEnum.CPU];
          curr[K8sTableColumnKeysEnum.INTERNAL_MEMORY] = item[K8sTableColumnKeysEnum.INTERNAL_MEMORY];
          return prev;
        }
        curr[K8sTableColumnKeysEnum.CPU] = {
          datapoints: null,
          unit: '',
        };
        curr[K8sTableColumnKeysEnum.INTERNAL_MEMORY] = {
          datapoints: null,
          unit: '',
        };
        prev.tableDataMap[id] = index;
        prev.ids.push(id);
        return prev;
      },
      { ids: [], tableDataMap: {} }
    );
  }

  /**
   * @description 异步加载获取k8s列表（cpu、内存使用率）的数据
   */
  loadAsyncData(startTime: number, endTime: number, resourceType: K8sTableColumnKeysEnum, resourceParam) {
    const asyncColumns: K8sTableColumn[] = (this.tableColumns || []).filter(col =>
      // @ts-ignore
      Object.hasOwn(col, 'asyncable')
    );
    for (const field of asyncColumns) {
      getK8sTableAsyncDataMock({
        start_time: startTime,
        end_time: endTime,
        column: field.id,
        resourceType,
        [resourceType]: resourceParam.ids,
      }).then(tableAsyncData => {
        this.renderTableBatchByBatch(field.id, resourceType, tableAsyncData, resourceParam.tableDataMap);
      });
    }
  }

  /**
   * @description 批量按需渲染表格数据（cpu、内存使用率）
   * @param field column 列id
   * @param resourceType resourceType 维度
   * @param tableAsyncData 异步数据
   * @param tableDataMap tableDataMap 异步数据id 对应 tableData 索引 映射
   */
  renderTableBatchByBatch(
    field: K8sTableColumnKeysEnum,
    resourceType: K8sTableColumnKeysEnum,
    tableAsyncData,
    tableDataMap
  ) {
    const setData = (currentIndex = 0, enableIdle = true, step = 1) => {
      const len = tableAsyncData.length;
      let endIndex = currentIndex + step;
      let shouldBreak = false;
      if (endIndex > len) {
        endIndex = len;
        shouldBreak = true;
      }
      for (let i = currentIndex; i < endIndex; i++) {
        const item = tableAsyncData[i];
        const resourceId = item[resourceType];
        const mapItem = this.asyncDataCache.get(resourceId);
        const chartData = item[field];
        if (!mapItem) {
          this.asyncDataCache.set(resourceId, { [field]: chartData });
        } else {
          mapItem[field] = chartData;
        }
        const rowIndex = tableDataMap[resourceId];
        const rowData = this.tableData.items[rowIndex];
        rowData[field] = chartData;
      }
      if (shouldBreak) {
        return shouldBreak;
      }
      if (enableIdle) {
        requestIdleCallback(deadline => {
          while (deadline.timeRemaining() > 0 && !shouldBreak) {
            shouldBreak = setData(endIndex, false);
          }
          if (!shouldBreak) {
            setData(endIndex, true);
          }
        });
      } else {
        setData(endIndex, false);
      }
    };
    setData(0, true);
  }

  /**
   * @description table label 点击回调
   * @param {K8sTableClickEvent} item
   */
  handleLabelClick(item: K8sTableClickEvent) {
    this.activeRowIndex = item.index;
    this.activeTitle.tag = item.column.id;
    this.activeTitle.field = K8sTableNew.getResourcesTextRowValue(item.row, item.column);
    this.handleSliderChange(true);
  }

  /**
   * @description 表格排序
   * @param {K8sTableSort} { prop, order }
   */
  handleSortChange(sortItem: K8sTableSort) {
    if (!this.sortContainer.initDone) {
      this.sortContainer.initDone = true;
      return;
    }
    this.sortContainer.prop = sortItem.prop;
    this.sortContainer.order = sortItem.order;
    this.getK8sList();
  }

  /**
   * @description 表格滚动到底部回调
   */
  handleTableScrollEnd() {
    this.pagination.page++;
    this.getK8sList({ needIncrement: true });
  }

  /**
   * @description 抽屉页显示隐藏切换
   * @param v {boolean}
   */
  handleSliderChange(v: boolean) {
    this.sliderShow = v;
    if (!v) {
      this.activeRowIndex = -1;
      this.activeTitle.tag = '--';
      this.activeTitle.field = '--';
    }
  }

  /**
   * @description 抽屉页 下钻 按钮点击回调
   */
  handleSliderGroupChange(groupId: K8sTableColumnKeysEnum) {
    this.groupChange(groupId);
    this.handleSliderChange(false);
  }

  /**
   * @description 抽屉页 添加筛选/移除筛选 按钮点击回调
   * @param {K8sTableFilterByEvent} item
   */
  handleSliderFilterChange(item: K8sTableFilterByEvent) {
    this.filterChange(item.groupId, item.ids);
    this.handleSliderChange(false);
  }

  /**
   * @description 表格列 filter icon 渲染配置方法
   * @param {K8sTableRow} row
   * @param {K8sTableColumn} column
   */
  filterIconFormatter(column: K8sTableColumn, row: K8sTableRow) {
    if (!column.k8s_filter) {
      return null;
    }
    const id = K8sTableNew.getResourcesTextRowValue(row, column);
    if (id) {
      const groupItem = this.filterBy?.find?.(v => v.key === column.id);
      const filterIds = (groupItem?.value?.length && groupItem?.value.filter(v => v !== id)) || [];
      const hasFilter = groupItem?.value?.length && filterIds?.length !== groupItem?.value?.length;
      return hasFilter ? (
        <i
          class='icon-monitor icon-sousuo- is-active'
          v-bk-tooltips={{ content: this.$t('移除该筛选项'), interactive: false }}
          onClick={() => this.filterChange(column.id, filterIds)}
        />
      ) : (
        <i
          class='icon-monitor icon-a-sousuo'
          v-bk-tooltips={{ content: this.$t('添加为筛选项'), interactive: false }}
          onClick={() => this.filterChange(column.id, [...filterIds, id])}
        />
      );
    }
    return null;
  }

  /**
   * @description 表格列 group icon 渲染配置方法
   * @param {K8sTableRow} row
   * @param {K8sTableColumn} column
   */
  groupIconFormatter(column: K8sTableColumn) {
    if (!column.k8s_group) {
      return null;
    }
    return (
      <K8sDimensionDrillDown
        dimension={column.id}
        value={column.id}
        onHandleDrillDown={v => this.groupChange(v.dimension as K8sTableColumnKeysEnum)}
      />
    );
  }

  /**
   * @description K8sTableColumnTypeEnum.RESOURCES_TEXT 类型表格列文本渲染方法
   * @param {K8sTableColumnKeysEnum} columnKey
   */
  resourcesTextFormatter(column: K8sTableColumn) {
    return (row: K8sTableRow, tableInsideColumn, cellValue, index: number) => {
      const text = K8sTableNew.getResourcesTextRowValue(row, column);
      return (
        <div class='k8s-table-col-item'>
          <span
            class='col-item-label'
            v-bk-overflow-tips={{ interactive: false }}
            onClick={() => this.handleLabelClick({ column, row, index })}
          >
            {text}
          </span>
          <div class='col-item-operate'>
            {this.filterIconFormatter(column, row)}
            {this.groupIconFormatter(column)}
          </div>
        </div>
      );
    };
  }

  /**
   * @description K8sTableColumnTypeEnum.DATA_CHART 类型表格列图表渲染方法
   * @param {K8sTableColumnKeysEnum} columnKey
   */
  datapointsFormatter(column: K8sTableColumn) {
    return (row: K8sTableRow) => {
      const columnKey = column.id;
      const chartData = row[columnKey];
      if (!chartData?.datapoints) {
        return (
          <img
            class='loading-svg'
            alt=''
            src={loadingIcon}
          />
        );
      }
      return chartData?.datapoints.length ? (
        <MiniTimeSeries
          data={chartData?.datapoints || []}
          disableHover={true}
          groupId={this.chartGroupIdsMap[column.id]}
          lastValueWidth={80}
          unit={chartData.unit}
          unitDecimal={chartData?.unitDecimal}
          valueTitle={chartData.valueTitle}
        />
      ) : (
        '--'
      );
    };
  }

  handleSetFormatter(column: K8sTableColumn) {
    switch (column.type) {
      case K8sTableColumnTypeEnum.RESOURCES_TEXT:
        return this.resourcesTextFormatter(column);
      default:
        return this.datapointsFormatter(column);
    }
  }

  transformColumn(column: K8sTableColumn) {
    return (
      <bk-table-column
        key={`column_${column.id}`}
        width={column.width}
        asyncable={!!column.asyncable}
        column-key={column.id}
        formatter={this.handleSetFormatter(column)}
        label={column.name}
        minWidth={column.min_width}
        prop={column.id}
        resizable={typeof column.resizable === 'boolean' ? column.resizable : true}
        show-overflow-tooltip={false}
        sort-orders={['ascending', 'descending']}
        sortable={column.sortable}
      />
    );
  }

  render() {
    return (
      <div class='k8s-table-new'>
        <bk-table
          key={this.refreshKey}
          ref='table'
          style={{ display: !this.tableLoading.loading ? 'block' : 'none' }}
          height='100%'
          default-sort={{
            prop: K8sTableColumnKeysEnum.CPU,
            order: 'descending',
          }}
          scrollLoading={{
            isLoading: this.tableLoading.scrollLoading,
            size: 'mini',
            theme: 'info',
            icon: 'circle-2-1',
            placement: 'right',
          }}
          data={this.tableData.items}
          row-key={this.tableRowKey}
          size='small'
          on-scroll-end={this.handleTableScrollEnd}
          on-sort-change={val => this.handleSortChange(val as K8sTableSort)}
        >
          {this.tableColumns.map(column => this.transformColumn(column))}
          <EmptyStatus
            slot='empty'
            textMap={{
              empty: this.$t('暂无数据'),
            }}
            type={this.groupInstance?.groupFilters?.length || this.filterBy?.length ? 'search-empty' : 'empty'}
            onOperation={this.clearSearch}
          />
        </bk-table>
        {this.tableLoading.loading ? (
          <TableSkeleton
            class='table-skeleton'
            type={5}
          />
        ) : null}

        <K8sDetailSlider
          activeRowIndex={this.activeRowIndex}
          activeTitle={this.activeTitle}
          filterBy={this.filterBy}
          groupInstance={this.groupInstance}
          isShow={this.sliderShow}
          tableData={this.tableData}
          onFilterChange={this.handleSliderFilterChange}
          onGroupChange={this.handleSliderGroupChange}
          onShowChange={this.handleSliderChange}
        />
      </div>
    );
  }
}
