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
import { Prop, Component, Emit, Watch, InjectReactive, Inject } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listK8sResources, resourceTrend } from 'monitor-api/modules/k8s';
import { Debounce, random } from 'monitor-common/utils/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';
import MiniTimeSeries from 'monitor-ui/chart-plugins/plugins/mini-time-series/mini-time-series';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { type IK8SMetricItem, K8sNewTabEnum, K8sTableColumnKeysEnum } from '../../typings/k8s-new';
import K8sDetailSlider from '../k8s-detail-slider/k8s-detail-slider';

import type { K8sGroupDimension } from '../../k8s-dimension';
import type { ITableItemMap } from '../../typings/table';
import type { TranslateResult } from 'vue-i18n';

import './k8s-table-new.scss';

type GetK8sColumnEnumValueType<T extends keyof typeof K8sTableColumnKeysEnum> = (typeof K8sTableColumnKeysEnum)[T];
/** k8s table column 图表字段类型 */
export type K8sTableColumnChartKey = GetK8sColumnEnumValueType<'CPU' | 'INTERNAL_MEMORY'>;
/** k8s table column 列资源字段类型 */
export type K8sTableColumnResourceKey = GetK8sColumnEnumValueType<
  keyof Omit<typeof K8sTableColumnKeysEnum, 'CPU' | 'INTERNAL_MEMORY'>
>;

/** k8s 表格列配置类型 */
export interface K8sTableColumn<T extends K8sTableColumnKeysEnum> {
  /** 字段类型 */
  type: K8sTableColumnTypeEnum;
  /** 字段id */
  id: T;
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
  /** label 是否可以点击 */
  canClick?: boolean;
  /** 是否需要异步加载 */
  asyncable?: boolean;
  /** 是否开启 添加/移除 筛选项 icon */
  k8s_filter?: boolean;
  /** 是否开启 下钻 icon */
  k8s_group?: boolean;
  /** 自定义获取值逻辑函数 */
  getValue?: (row: K8sTableRow) => string;
}

/** k8s table行数据数据类型 */
export type K8sTableRow = Partial<Record<K8sTableColumnResourceKey, string>> &
  Record<K8sTableColumnChartKey, Pick<ITableItemMap, 'datapoints'>['datapoints']>;

export interface K8sTableSort {
  prop: K8sTableColumnChartKey | null;
  order: 'ascending' | 'descending' | null;
}

export interface K8sTableClickEvent {
  column: K8sTableColumn<K8sTableColumnResourceKey>;
  row: K8sTableRow;
  index: number;
}

export interface DrillDownEvent {
  /** 点击下钻时数据所在维度 */
  id: K8sTableColumnResourceKey;
  /** 用户选择的需要下钻的维度 */
  dimension: K8sTableColumnResourceKey;
}

export type K8sTableGroupByEvent = DrillDownEvent & { filterById: string };

interface K8sTableNewProps {
  /** 当前选中的 tab 项 */
  activeTab: K8sNewTabEnum;
  /** GroupBy 选择器选中数据类实例 */
  groupInstance: K8sGroupDimension;
  /** 筛选 Filter By 过滤项 */
  filterBy: Record<string, string[]>;
  /** 获取资源列表公共请求参数 */
  filterCommonParams: Record<string, any>;
  metricList: IK8SMetricItem[];
  hideMetrics: string[];
}
interface K8sTableNewEvent {
  onSortChange: (sort: `-${K8sTableColumnChartKey}` | K8sTableColumnChartKey) => void;
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
/** 是否开启前端分页功能 */
const enabledFrontendLimit = false;

@Component
export default class K8sTableNew extends tsc<K8sTableNewProps, K8sTableNewEvent> {
  /** k8s table ResourcesText 类型列 获取值静态方法  */
  static getResourcesTextRowValue(row: K8sTableRow, column: K8sTableColumn<K8sTableColumnResourceKey>) {
    if (column?.getValue) {
      return column.getValue(row) || '--';
    }
    return row?.[column.id] || '--';
  }

  /** workload / workload_type 不同场景下的获取值逻辑  */
  static getWorkloadValue(columnKey: K8sTableColumnResourceKey, index: 0 | 1) {
    return row => (row?.[columnKey] as string)?.split(':')?.[index] || '--';
  }

  /** 当前页面 tab */
  @Prop({ type: String, default: K8sNewTabEnum.LIST }) activeTab: K8sNewTabEnum;
  /** GroupBy 选择器选中数据类实例 */
  @Prop({ type: Object }) groupInstance: K8sGroupDimension;
  /** FilterBy 选择器选中数据 */
  @Prop({ type: Object, default: () => ({}) }) filterBy: Record<string, string[]>;
  /** 获取资源列表公共请求参数 */
  @Prop({ type: Object, default: () => ({}) }) filterCommonParams: Record<string, any>;
  @Prop({ type: Array, default: () => [] }) metricList: IK8SMetricItem[];
  @Prop({ type: Array, default: () => [] }) hideMetrics: string[];
  // 刷新间隔 - monitor-k8s-new 传入
  @InjectReactive('refleshInterval') readonly refreshInterval!: number;
  // 是否立即刷新 - monitor-k8s-new 传入
  @InjectReactive('refleshImmediate') readonly refreshImmediate!: string;
  @Inject({ from: 'onFilterChange', default: () => null }) readonly onFilterChange: (
    id: string,
    groupId: K8sTableColumnResourceKey,
    isSelect: boolean
  ) => void;

  @Inject({ from: 'onGroupChange', default: () => null }) readonly onDrillDown: (
    item: K8sTableGroupByEvent,
    showCancelDrill?: boolean
  ) => void;

  tableLoading = {
    /** table 骨架屏 loading */
    loading: true,
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
  tableData: K8sTableRow[] = [];
  /** 表格数据总条数 */
  tableDataTotal = 0;
  /** 是否显示抽屉页 */
  sliderShow = false;
  /** 图表异步请求数据缓存 */
  asyncDataCache = new Map();
  resourceDetail: Partial<Record<K8sTableColumnKeysEnum, string>> = {};
  /** 浏览器空闲时期填充图表异步请求数据执行函数ID，重新请求时及时终止结束回调 */
  requestIdleCallbackId = null;
  /** 图表异步请求中止控制器 */
  abortControllerQueue: Set<AbortController> = new Set();

  get isListTab() {
    return this.activeTab === K8sNewTabEnum.LIST;
  }

  get tableRowKey() {
    if (this.isListTab) {
      return this.groupInstance.getResourceType();
    }
    const dimensions = this.groupInstance.dimensions;
    const len = dimensions.length;
    return dimensions[len - 1];
  }

  get tableColumns() {
    const map = this.getKeyToTableColumnsMap();
    const columns: K8sTableColumn<K8sTableColumnKeysEnum>[] = [];
    let iterationTarget = tabToTableDetailColumnDynamicKeys;
    if (this.isListTab) {
      iterationTarget = [...this.groupInstance.groupFilters].reverse();
    }
    const addColumn = (arr, targetArr = []) => {
      for (const key of targetArr) {
        const column = map[key];
        if (column) {
          arr.push(column);
        }
      }
    };
    addColumn(columns, iterationTarget);
    addColumn(columns, tabToTableDetailColumnFixedKeys);
    return columns;
  }

  /** table视图数据（由于后端返回全量数据，分页功能需前端自己处理） */
  get tableViewData() {
    if (enabledFrontendLimit) {
      /** 接口返回全量数据时执行方案 */
      const { page, pageSize } = this.pagination;
      return this.tableData.slice(0, page * pageSize);
    }
    return this.tableData;
  }

  /** 缩略图分组Id枚举 */
  get chartGroupIdsMap() {
    // 暂时不支持图表联动
    // return this.tableColumns.reduce((acc, cur, ind) => {
    //   if (cur.type === K8sTableColumnTypeEnum.DATA_CHART) {
    //     if (acc[cur.id]) disconnect(acc[cur.id]);
    //     acc[cur.id] = `${random(8)}_${ind}`;
    //     connect(acc[cur.id]);
    //   }
    //   return acc;
    // }, {});
    return {};
  }

  /** table 空数据时显示样式类型 'search-empty'/'empty' */
  get tableEmptyType() {
    for (const filtersArgs of Object.values(this.filterBy)) {
      if (filtersArgs?.length) {
        return 'search-empty';
      }
    }
    return 'empty';
  }

  @Watch('activeTab')
  onActiveTabChange(v) {
    if (v !== K8sNewTabEnum.CHART) {
      // 重新渲染，从而刷新 table sort 状态
      this.getK8sList({ needRefresh: true });
    }
  }

  @Watch('groupInstance', { deep: true })
  onGroupFiltersChange(newInstance, oldInstance) {
    if (!this.filterCommonParams.bcs_cluster_id) {
      return;
    }
    if (newInstance === oldInstance) {
      if (!this.isListTab) return;
      this.tableLoading.loading = true;
      this.debounceGetK8sList();
      return;
    }
    this.initSortContainer(this.groupInstance.defaultSortProp);
    this.sortChange(this.groupInstance.defaultSortProp);
    this.tableLoading.loading = true;
    this.debounceGetK8sList();
    this.refreshTable();
  }

  @Watch('filterCommonParams')
  onFilterCommonParamsChange() {
    this.debounceGetK8sList();
  }

  @Watch('refreshInterval')
  onRefreshImmediateChange() {
    this.getK8sList({ needRefresh: true });
  }

  @Watch('refreshImmediate')
  handleRefreshImmediateChange() {
    this.getK8sList({ needRefresh: true });
  }

  @Emit('sortChange')
  sortChange(sort: `-${K8sTableColumnChartKey}` | K8sTableColumnChartKey) {
    return sort;
  }

  @Emit('clearSearch')
  clearSearch() {
    return {};
  }

  created() {
    const orderBy = (this.$route.query?.tableSort as string) || this.groupInstance.defaultSortProp;
    this.initSortContainer(orderBy as `-${K8sTableColumnChartKey}` | K8sTableColumnChartKey);
    this.getK8sList();
  }
  beforeUnmount() {
    cancelIdleCallback(this.requestIdleCallbackId);
    this.requestIdleCallbackId = null;
  }

  getKeyToTableColumnsMap(): Record<K8sTableColumnKeysEnum, K8sTableColumn<K8sTableColumnKeysEnum>> {
    const { CLUSTER, POD, WORKLOAD_TYPE, WORKLOAD, NAMESPACE, CONTAINER, CPU, INTERNAL_MEMORY } =
      K8sTableColumnKeysEnum;

    return {
      [CLUSTER]: {
        id: CLUSTER,
        name: this.$t('cluster'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 90,
        canClick: true,
        getValue: () => this.filterCommonParams.bcs_cluster_id,
      },
      [POD]: {
        id: POD,
        name: this.$t('Pod'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 260,
        canClick: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [WORKLOAD_TYPE]: {
        id: WORKLOAD_TYPE,
        name: this.$t('workload_type'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        getValue: K8sTableNew.getWorkloadValue(WORKLOAD, 0),
      },
      [WORKLOAD]: {
        id: WORKLOAD,
        name: this.$t('workload'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        canClick: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
        getValue: !this.isListTab ? K8sTableNew.getWorkloadValue(WORKLOAD, 1) : null,
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
        canClick: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [CPU]: {
        id: CPU,
        name: this.$t('CPU使用量'),
        sortable: 'custom',
        type: K8sTableColumnTypeEnum.DATA_CHART,
        min_width: 180,
        asyncable: true,
      },
      [INTERNAL_MEMORY]: {
        id: INTERNAL_MEMORY,
        name: this.$t('内存使用量'),
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
   * @description 初始化排序
   * @param {string} orderBy 排序字段
   */
  initSortContainer(orderBy: `-${K8sTableColumnChartKey}` | K8sTableColumnChartKey) {
    const matchReg = orderBy?.match(/^(-?)(\w+)$/) || [];
    this.sortContainer.prop = (matchReg?.[2] || '') as K8sTableColumnChartKey;
    this.sortContainer.order = matchReg?.[1] === '-' ? 'descending' : 'ascending';
    this.sortContainer.initDone = false;
  }

  @Debounce(200)
  debounceGetK8sList() {
    this.getK8sList({ needRefresh: true });
  }
  /**
   * @description 获取k8s列表
   * @param {boolean} config.needRefresh 是否需要刷新表格状态
   * @param {boolean} config.needIncrement 是否需要增量加载（table 触底加载）
   */
  async getK8sList(config: { needRefresh?: boolean; needIncrement?: boolean } = {}) {
    if (!this.filterCommonParams.bcs_cluster_id || this.tableLoading.scrollLoading) {
      return;
    }
    this.abortAsyncData();
    let loadingKey = 'scrollLoading';
    const initPagination = () => {
      this.pagination.page = 1;
      loadingKey = 'loading';
    };
    let pageRequestParam = {};
    // 是否启用前端分页
    if (enabledFrontendLimit) {
      initPagination();
    } else {
      if (!config.needIncrement) {
        initPagination();
      }
      pageRequestParam = {
        page_size: this.pagination.pageSize,
        page: this.pagination.page,
      };
    }

    this.tableLoading[loadingKey] = true;
    if (config.needRefresh) {
      this.asyncDataCache.clear();
    }
    const order_by =
      this.sortContainer.order === 'descending' ? `-${this.sortContainer.prop}` : this.sortContainer.prop;
    const { dimensions } = this.groupInstance;
    const resourceType = this.isListTab
      ? this.groupInstance?.getResourceType()
      : (dimensions[dimensions.length - 1] as K8sTableColumnResourceKey);

    /** 获取资源列表请求接口参数 */
    const requestParam = {
      ...this.filterCommonParams,
      ...pageRequestParam,
      resource_type: resourceType,
      with_history: true,
      page_type: this.pagination.pageType,
      order_by,
    };

    const data: { count: number; items: K8sTableRow[] } = await listK8sResources(requestParam).catch(() => ({
      count: 0,
      items: [],
    }));
    const resourceParam = this.formatTableData(data.items, resourceType as K8sTableColumnResourceKey);
    this.tableData = data.items;
    this.tableDataTotal = data.count;
    this.tableLoading[loadingKey] = false;
    this.loadAsyncData(resourceType, resourceParam);
  }

  getResourceId(key: K8sTableColumnKeysEnum, data: Record<K8sTableColumnKeysEnum, string>) {
    if (key === K8sTableColumnKeysEnum.CONTAINER) {
      return `${data[K8sTableColumnKeysEnum.POD]}:${data[K8sTableColumnKeysEnum.CONTAINER]}`;
    }
    return data[key];
  }

  /**
   * @description 格式化接口数据结构为table需要的数据结构，并返回异步请求加载 图表数据 时需要数据
   */
  formatTableData(
    tableData: K8sTableRow[],
    resourceType: K8sTableColumnResourceKey
  ): { ids: Set<string>; tableDataMap: Record<string, number[]> } {
    console.info('tableData', tableData, resourceType);
    return tableData.reduce(
      (prev, curr, index) => {
        const id = this.getResourceId(resourceType, curr as any);
        const item = this.asyncDataCache.get(id);
        if (
          this.asyncDataCache.has(id) &&
          item[K8sTableColumnKeysEnum.CPU] &&
          item[K8sTableColumnKeysEnum.INTERNAL_MEMORY]
        ) {
          curr[K8sTableColumnKeysEnum.CPU] = item[K8sTableColumnKeysEnum.CPU];
          curr[K8sTableColumnKeysEnum.INTERNAL_MEMORY] = item[K8sTableColumnKeysEnum.INTERNAL_MEMORY];
          return prev;
        }
        curr[K8sTableColumnKeysEnum.CPU] = {
          datapoints: null,
          unit: '',
          unitDecimal: null,
          valueTitle: this.$tc('用量'),
        };
        curr[K8sTableColumnKeysEnum.INTERNAL_MEMORY] = {
          datapoints: null,
          unit: '',
          unitDecimal: null,
          valueTitle: this.$tc('用量'),
        };
        if (prev.tableDataMap[id]) {
          prev.tableDataMap[id].push(index);
        } else {
          prev.tableDataMap[id] = [index];
        }
        if (!prev.ids.has(id)) {
          prev.ids.add(id);
        }
        return prev;
      },
      { ids: new Set() as Set<string>, tableDataMap: {} }
    );
  }

  /**
   * @description 終止目前还在执行的异步列处理逻辑（请求与渲染）
   */
  abortAsyncData() {
    // 如请求资源列表时候，发现视图趋势接口未完成，则中断不请求
    if (this.abortControllerQueue.size) {
      for (const controller of this.abortControllerQueue) {
        controller.abort();
      }
      this.abortControllerQueue.clear();
    }
    // 如请求资源列表时候，发现异步渲染未全部完成，则中断
    if (this.requestIdleCallbackId) {
      cancelIdleCallback(this.requestIdleCallbackId);
      this.requestIdleCallbackId = null;
    }
  }

  /**
   * @description 异步加载获取k8s列表（cpu、内存使用率）的数据
   */
  loadAsyncData(resourceType: K8sTableColumnResourceKey, resourceParam) {
    const asyncColumns = (this.tableColumns || []).filter(column => 'asyncable' in column);
    for (const field of asyncColumns) {
      const controller = new AbortController();
      this.abortControllerQueue.add(controller);
      resourceTrend(
        {
          ...this.filterCommonParams,
          column: field.id,
          resource_type: resourceType,
          resource_list: Array.from(
            new Set(
              Array.from(resourceParam.ids).map((id: string) =>
                resourceType === K8sTableColumnKeysEnum.CONTAINER ? id.split(':')?.[1] || id : id
              )
            )
          ),
        },
        { signal: controller.signal }
      )
        .then(tableAsyncData => {
          this.renderTableBatchByBatch(
            field.id as K8sTableColumnResourceKey,
            tableAsyncData,
            resourceParam.tableDataMap
          );
        })
        .finally(() => {
          this.abortControllerQueue.delete(controller);
        });
    }
  }

  /**
   * @description 批量按需渲染表格数据（cpu、内存使用率）
   * @param field column 列id
   * @param tableAsyncData 异步数据
   * @param tableDataMap tableDataMap 异步数据id 对应 tableData 索引 映射数组
   */
  renderTableBatchByBatch(field: K8sTableColumnResourceKey, tableAsyncData, tableDataMap) {
    const setData = (currentIndex = 0, enableIdle = true, step = 5) => {
      const len = tableAsyncData.length;
      if (!tableAsyncData?.length) return;
      let endIndex = currentIndex + step;
      let shouldBreak = false;
      if (endIndex > len) {
        endIndex = len;
        shouldBreak = true;
      }
      for (let i = currentIndex; i < endIndex; i++) {
        const item = tableAsyncData[i];
        const resourceId = item.resource_name;
        const mapItem = this.asyncDataCache.get(resourceId);
        const chartData = item[field];
        if (!mapItem) {
          this.asyncDataCache.set(resourceId, { [field]: chartData });
        } else {
          mapItem[field] = chartData;
        }
        const rowIndexArr = tableDataMap[resourceId];
        if (rowIndexArr?.length) {
          for (const rowIndex of rowIndexArr) {
            const rowData = this.tableData[rowIndex];
            rowData[field] = chartData || [];
          }
        }
      }
      if (shouldBreak) {
        return { shouldBreak, endIndex: -1 };
      }
      if (enableIdle) {
        this.requestIdleCallbackId = requestIdleCallback(
          deadline => {
            /** 控制浏览器一帧内空闲时间足够的情况下最多应可渲染多少条数据
             * （step > canRenderMaxCount 时以step为准，但是一帧内只会执行 1 次）
             **/
            let canRenderMaxCount = 4;
            canRenderMaxCount -= step;
            while (deadline.timeRemaining() > 0 && !shouldBreak && canRenderMaxCount > 0 && !deadline.didTimeout) {
              const res = setData(endIndex, false, step);
              endIndex = res.endIndex;
              shouldBreak = res.shouldBreak;
              canRenderMaxCount -= step;
            }
            if (!shouldBreak) {
              requestAnimationFrame(() => {
                setData(endIndex, true, step);
              });
            }
          },
          { timeout: 360 }
        );
      } else {
        return { shouldBreak, endIndex };
      }
    };

    // 递归渲染入口
    this.requestIdleCallbackId = requestIdleCallback(
      () => {
        requestAnimationFrame(() => {
          setData(0, true, 2);
        });
      },
      { timeout: 360 }
    );
  }

  /**
   * @description table label 点击回调
   * @param {K8sTableClickEvent} item
   */
  handleLabelClick(item: K8sTableClickEvent) {
    const { row, column } = item;
    const detail: Partial<{ externalParam: { isCluster: boolean } } & Record<K8sTableColumnKeysEnum, string>> = {
      namespace: row[K8sTableColumnKeysEnum.NAMESPACE],
      cluster: this.filterCommonParams.bcs_cluster_id,
    };
    if (column.id === K8sTableColumnKeysEnum.CONTAINER) {
      detail[K8sTableColumnKeysEnum.POD] = row[K8sTableColumnKeysEnum.POD];
    }
    if (column.id !== K8sTableColumnKeysEnum.CLUSTER) {
      detail[column.id] = row[column.id];
    } else {
      // externalParam 接口请求传参时忽略属性，组件个性化逻辑传参处理
      detail.externalParam = { isCluster: true };
    }
    this.resourceDetail = detail;
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
    const orderBy: `-${K8sTableColumnChartKey}` | K8sTableColumnChartKey =
      this.sortContainer.order === 'descending' ? `-${this.sortContainer.prop}` : this.sortContainer.prop;
    this.sortChange(orderBy);
    this.getK8sList();
  }

  /**
   * @description 表格滚动到底部回调
   */
  handleTableScrollEnd() {
    if (this.tableViewData.length >= this.tableDataTotal) {
      return;
    }
    if (enabledFrontendLimit) {
      /** 接口返回全量数据时执行方案 */
      this.tableLoading.scrollLoading = true;
      setTimeout(() => {
        this.pagination.page++;
        this.tableLoading.scrollLoading = false;
      }, 600);
      return;
    }
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
      this.resourceDetail = {};
    }
  }

  /**
   * @description 表格列 filter icon 渲染配置方法
   * @param {K8sTableRow} row
   * @param {K8sTableColumn} column
   */
  filterIconFormatter(column: K8sTableColumn<K8sTableColumnResourceKey>, row: K8sTableRow) {
    if (!column.k8s_filter) {
      return null;
    }
    const resourceValue = K8sTableNew.getResourcesTextRowValue(row, column);
    if (resourceValue) {
      const groupItem = this.filterBy?.[column.id];
      const hasFilter = groupItem?.includes(resourceValue);
      const elAttr = hasFilter
        ? { className: ['icon-sousuo-', 'is-active'], text: '移除该筛选项' }
        : { className: ['icon-a-sousuo'], text: '添加为筛选项' };
      return (
        <i
          class={['icon-monitor', ...elAttr.className]}
          v-bk-tooltips={{ content: this.$t(elAttr.text), interactive: false }}
          onClick={() => this.onFilterChange(resourceValue, column.id, !hasFilter)}
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
  groupIconFormatter(column: K8sTableColumn<K8sTableColumnResourceKey>, row: K8sTableRow) {
    if (!column.k8s_group) {
      return null;
    }
    const filterById = K8sTableNew.getResourcesTextRowValue(row, column);
    return (
      <K8sDimensionDrillDown
        dimension={column.id}
        value={column.id}
        onHandleDrillDown={v => this.onDrillDown({ ...(v as DrillDownEvent), filterById })}
      />
    );
  }

  /**
   * @description K8sTableColumnTypeEnum.RESOURCES_TEXT 类型表格列文本渲染方法
   * @param {K8sTableColumn} column
   */
  resourcesTextFormatter(column: K8sTableColumn<K8sTableColumnResourceKey>) {
    return (row: K8sTableRow, tableInsideColumn, cellValue, index: number) => {
      const text = K8sTableNew.getResourcesTextRowValue(row, column);
      return (
        <div class='k8s-table-col-item'>
          {column.canClick ? (
            <span
              class='col-item-label can-click'
              v-bk-overflow-tips={{ interactive: false }}
              onClick={() => this.handleLabelClick({ column, row, index })}
            >
              {text}
            </span>
          ) : (
            <span
              class='col-item-label'
              v-bk-overflow-tips={{ interactive: false }}
            >
              {text}
            </span>
          )}
          <div class='col-item-operate'>
            {this.filterIconFormatter(column, row)}
            {this.groupIconFormatter(column, row)}
          </div>
        </div>
      );
    };
  }

  /**
   * @description K8sTableColumnTypeEnum.DATA_CHART 类型表格列图表渲染方法
   * @param {K8sTableColumn} column
   */
  datapointsFormatter(column: K8sTableColumn<K8sTableColumnChartKey>) {
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
      return chartData?.datapoints?.length ? (
        <MiniTimeSeries
          data={chartData?.datapoints}
          disableHover={true}
          groupId={this.chartGroupIdsMap[column.id]}
          lastValueWidth={80}
          unit={chartData.unit}
          unitDecimal={chartData?.unitDecimal || 4}
          valueTitle={chartData.valueTitle || this.$tc('用量')}
        />
      ) : (
        '--'
      );
    };
  }

  handleSetFormatter(column: K8sTableColumn<K8sTableColumnKeysEnum>) {
    switch (column.type) {
      case K8sTableColumnTypeEnum.RESOURCES_TEXT:
        return this.resourcesTextFormatter(column as K8sTableColumn<K8sTableColumnResourceKey>);
      default:
        return this.datapointsFormatter(column as K8sTableColumn<K8sTableColumnChartKey>);
    }
  }

  transformColumn(column: K8sTableColumn<K8sTableColumnKeysEnum>) {
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
            prop: this.sortContainer.prop,
            order: this.sortContainer.order,
          }}
          border={false}
          data={this.tableViewData}
          outer-border={false}
          // row-key={this.tableRowKey}
          size='small'
          on-scroll-end={this.handleTableScrollEnd}
          on-sort-change={val => this.handleSortChange(val as K8sTableSort)}
        >
          {this.tableColumns.map(column => this.transformColumn(column))}
          <div
            class='k8s-table-loading'
            slot='append'
          >
            <bk-spin
              style={{
                display: this.tableLoading.scrollLoading ? 'flex' : 'none',
              }}
              placement='right'
              size='mini'
            >
              {this.$t('加载中')}
            </bk-spin>
          </div>
          <EmptyStatus
            slot='empty'
            textMap={{
              empty: this.$t('暂无数据'),
            }}
            type={this.tableEmptyType}
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
          hideMetrics={this.hideMetrics}
          isShow={this.sliderShow}
          metricList={this.metricList}
          resourceDetail={this.resourceDetail}
          onShowChange={this.handleSliderChange}
        />
      </div>
    );
  }
}
