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
import { Component, Emit, Inject, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listK8sResources, resourceTrend } from 'monitor-api/modules/k8s';
import { bkMessage, makeMessage } from 'monitor-api/utils';
import { Debounce, random } from 'monitor-common/utils/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import {
  type IK8SMetricItem,
  type K8sSortType,
  type K8sTableMetricKeys,
  K8sConvergeTypeEnum,
  K8sNewTabEnum,
  K8sTableColumnKeysEnum,
} from '../../typings/k8s-new';
import K8sDetailSlider from '../k8s-detail-slider/k8s-detail-slider';
import K8sConvergeSelect from './k8s-converge-select';

import type { K8sGroupDimension } from '../../k8s-dimension';
import type { ITableItemMap } from '../../typings/table';
import type { TranslateResult } from 'vue-i18n';

import './k8s-table-new.scss';

/**
 * @enum k8s 表格列类型枚举
 */
export enum K8sTableColumnTypeEnum {
  DATA_CHART = 'data_chart',
  RESOURCES_TEXT = 'resources_text',
}
export interface DrillDownEvent {
  /** 用户选择的需要下钻的维度 */
  dimension: K8sTableColumnResourceKey;
  /** 点击下钻时数据所在维度 */
  id: K8sTableColumnResourceKey;
}
export interface K8sTableClickEvent {
  column: K8sTableColumn<K8sTableColumnResourceKey>;
  index: number;
  row: K8sTableRow;
}

/** k8s 表格列配置类型 */
export interface K8sTableColumn<T extends K8sTableColumnKeysEnum> {
  /** 是否需要异步加载 */
  asyncable?: boolean;
  /** label 是否可以点击 */
  can_click?: boolean;
  /** 小类目名称（选择指标列时使用） */
  category_name?: string;
  /** 是否固定列 */
  fixed?: boolean;
  /** 表头对齐方式 */
  header_align?: 'center' | 'left' | 'right';
  /** 字段id */
  id: T;
  /** 是否开启 添加/移除 筛选项 icon */
  k8s_filter?: boolean;
  /** 是否开启 下钻 icon */
  k8s_group?: boolean;
  /** 最小列宽 */
  min_width?: number;
  /** 字段名称（渲染指标列时为指标名称） */
  name: TranslateResult;
  /** 是否伸缩大小 */
  resizable?: boolean;
  /** 是否可以排序 */
  sortable?: 'custom' | boolean;
  /** 字段类型 */
  type: K8sTableColumnTypeEnum;
  /** 列宽 */
  width?: number;
  /** 自定义获取值逻辑函数 */
  getValue?: (row: K8sTableRow) => string;
  /** 表格列自定义渲染方法 */
  renderHeader?: (column: K8sTableColumn<K8sTableColumnKeysEnum>) => any;
}

/** k8s table column 图表字段类型 */
export type K8sTableColumnChartKey = GetK8sColumnEnumValueType<K8sTableMetricKeys>;

/** k8s table column 列资源字段类型 */
export type K8sTableColumnResourceKey = GetK8sColumnEnumValueType<
  keyof Omit<typeof K8sTableColumnKeysEnum, K8sTableMetricKeys>
>;

export type K8sTableGroupByEvent = DrillDownEvent & { filterById: string };

/** k8s table行数据数据类型 */
export type K8sTableRow = Partial<Record<K8sTableColumnResourceKey, string>> &
  Record<K8sTableColumnChartKey, Pick<ITableItemMap, 'datapoints'>['datapoints']>;

export interface K8sTableSortContainer extends Pick<TableSort, 'prop'> {
  /** 处理 table 设置了 default-sort 时导致初始化时会自动走一遍sort-change事件问题 */
  initDone: boolean;
  orderBy: K8sSortType;
}

export interface TableSort {
  order: 'ascending' | 'descending' | null;
  prop: K8sTableColumnChartKey | null;
}

type GetK8sColumnEnumValueType<T extends keyof typeof K8sTableColumnKeysEnum> = (typeof K8sTableColumnKeysEnum)[T];
interface K8sTableNewEvent {
  onClearSearch: () => void;
  onRouterParamChange: (sort: Omit<K8sTableSortContainer, 'initDone'>) => void;
}

interface K8sTableNewProps {
  /** 当前选中的 tab 项 */
  activeTab: K8sNewTabEnum;
  /** 筛选 Filter By 过滤项 */
  filterBy: Record<string, string[]>;
  /** 获取资源列表公共请求参数 */
  filterCommonParams: Record<string, any>;
  /** GroupBy 选择器选中数据类实例 */
  groupInstance: K8sGroupDimension;
  hideMetrics: string[];
  metricList: IK8SMetricItem[];
}

/** 是否开启前端分页功能 */
const enabledFrontendLimit = false;
const SCROLL_CONTAINER_DOM = '.bk-table-body-wrapper';
const DISABLE_TARGET_DOM = '.bk-table-body';
const TABLE_ROW_MIN_HEIGHT = 42;

@Component
export default class K8sTableNew extends tsc<K8sTableNewProps, K8sTableNewEvent> {
  /** k8s table ResourcesText 类型列 获取值静态方法  */
  static getResourcesTextRowValue(row: K8sTableRow, column: K8sTableColumn<K8sTableColumnResourceKey>) {
    if (column?.getValue) {
      return column.getValue(row) || '--';
    }
    return row?.[column.id] || '--';
  }

  /** workload / workload_kind 不同场景下的获取值逻辑  */
  static getWorkloadValue(columnKey: K8sTableColumnResourceKey, index: 0 | 1) {
    return row => (row?.[columnKey] as string)?.split(':')?.[index] || '--';
  }

  @Ref('tableViewportContainer') tableViewportContainer: HTMLElement;

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
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  // 是否立即刷新 - monitor-k8s-new 传入
  @InjectReactive('refreshImmediate') readonly refreshImmediate!: string;
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
  sortContainer: K8sTableSortContainer = {
    prop: K8sTableColumnKeysEnum.CPU_USAGE,
    orderBy: 'desc',
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
  /** 指标异步请求中止控制器 */
  abortControllerQueue: Set<AbortController> = new Set();
  /** 各指标汇聚类型map（默认为 sum） */
  metricsForConvergeMap: Partial<Record<K8sTableColumnChartKey, K8sConvergeTypeEnum>> = {};
  /** 滚动容器Dom实例 */
  scrollContainer: HTMLElement = null;
  /** 滚动结束后回调逻辑执行计时器  */
  scrollTimer = null;

  get isListTab() {
    return this.activeTab === K8sNewTabEnum.LIST;
  }

  /** 资源类型 */
  get resourceType() {
    const { groupByDimensions: dimensions } = this.groupInstance;
    return this.isListTab
      ? this.groupInstance?.getResourceType()
      : (dimensions[dimensions.length - 1] as K8sTableColumnResourceKey);
  }

  get tableChartColumns() {
    const ids: K8sTableColumnChartKey[] = [];
    const columns: K8sTableColumn<K8sTableColumnKeysEnum>[] = [];
    // 处理表格指标展示列
    const hideMetricsSet = new Set(this.hideMetrics);
    for (const item of this.metricList) {
      if (item?.children?.length) {
        for (const child of item.children) {
          if (!hideMetricsSet.has(child.id)) {
            const regex = /(^[A-Za-z]*\b)(.*)/;
            const founds = child.name.match(regex);
            let name = '';
            let categoryName = '';
            if (founds?.length && founds?.length === 3) {
              name = founds[2]?.trim?.();
              categoryName = founds[1]?.trim?.();
            } else {
              categoryName = child.name?.slice?.(0, 2)?.trim?.();
              name = child.name?.slice?.(2)?.trim?.();
            }
            ids.push(child.id as K8sTableColumnChartKey);
            columns.push({
              id: child.id as K8sTableColumnKeysEnum,
              name: name,
              category_name: categoryName,
              sortable: 'custom',
              type: K8sTableColumnTypeEnum.DATA_CHART,
              min_width: 140,
              asyncable: true,
              header_align: 'right',
              renderHeader: this.metricsColumnHeaderRender,
            });
          }
        }
      }
    }
    return {
      ids,
      columns,
      activeTab: this.activeTab,
    };
  }

  get tableColumns() {
    const columns: K8sTableColumn<K8sTableColumnKeysEnum>[] = [];
    // 处理表格维度展示列
    const resourceMap = this.getKeyToTableResourceColumnsMap();
    let iterationTarget = this.groupInstance.dimensions;
    let resourceColumnFixed = false;
    if (this.isListTab) {
      iterationTarget = this.groupInstance.groupFilters?.length
        ? [...this.groupInstance.groupFilters].reverse()
        : [K8sTableColumnKeysEnum.CLUSTER];
      resourceColumnFixed = true;
    }
    for (const key of iterationTarget) {
      const column = resourceMap[key];
      column.fixed = resourceColumnFixed;
      if (column) {
        columns.push(column);
      }
      if (!this.isListTab && key === K8sTableColumnKeysEnum.WORKLOAD) {
        columns.push(resourceMap[K8sTableColumnKeysEnum.WORKLOAD_KIND]);
      }
    }

    // 处理表格指标展示列
    columns.push(...this.tableChartColumns.columns);
    return columns;
  }

  /** table视图数据（由于后端返回全量数据，分页功能需前端自己处理） */
  get tableViewData() {
    if (enabledFrontendLimit) {
      /** 接口返回全量数据时执行方案 */
      const { page, pageSize } = this.pagination;
      return this.tableData.slice(0, page * pageSize) || [];
    }
    return this.tableData || [];
  }

  get tableHasScrollLoading() {
    return this.tableViewData?.length !== this.tableDataTotal;
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

  @Watch('tableChartColumns')
  onTableChartColumnsChange() {
    this.tableLoading.loading = true;
    this.initSortContainer(this.sortContainer);
    if (!this.tableChartColumns.ids?.length) {
      this.debounceGetK8sList();
      return;
    }
    this.debounceGetK8sList();
    this.refreshTable();
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
    this.initSortContainer(this.groupInstance.defaultSortContainer);
    this.routerParamChange();
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

  @Emit('routerParamChange')
  routerParamChange() {
    const { prop, orderBy } = this.sortContainer;
    return {
      tableSort: prop,
      tableOrder: orderBy,
      tableMethod: this.metricsForConvergeMap[prop] || K8sConvergeTypeEnum.SUM,
    };
  }

  @Emit('clearSearch')
  clearSearch() {
    return {};
  }

  created() {
    let sort: Partial<Omit<K8sTableSortContainer, 'initDone'>> = this.groupInstance.defaultSortContainer;
    if (this.$route.query?.tableSort) {
      const { tableSort, tableOrder, tableMethod } = this.$route.query;
      sort = {
        prop: tableSort as K8sTableColumnChartKey,
        orderBy: (tableOrder || 'desc') as K8sSortType,
      };
      this.$set(
        this.metricsForConvergeMap,
        tableSort as K8sTableColumnChartKey,
        tableMethod || K8sConvergeTypeEnum.SUM
      );
    }
    this.initSortContainer(sort);
    this.getK8sList();
  }
  mounted() {
    this.addScrollListener();
  }
  beforeDestroy() {
    this.removeScrollListener();
  }

  getKeyToTableResourceColumnsMap(): Record<K8sTableColumnResourceKey, K8sTableColumn<K8sTableColumnResourceKey>> {
    const { CLUSTER, POD, WORKLOAD_KIND, WORKLOAD, NAMESPACE, CONTAINER, INGRESS, SERVICE, NODE } =
      K8sTableColumnKeysEnum;

    return {
      [CLUSTER]: {
        id: CLUSTER,
        name: this.$t('cluster'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 120,
        can_click: true,
        getValue: () => this.filterCommonParams.bcs_cluster_id,
      },
      [POD]: {
        id: POD,
        name: this.$t('pod'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 260,
        can_click: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [WORKLOAD_KIND]: {
        id: WORKLOAD_KIND,
        name: this.$t('workload_kind'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 140,
        getValue: K8sTableNew.getWorkloadValue(WORKLOAD, 0),
      },
      [WORKLOAD]: {
        id: WORKLOAD,
        name: this.$t('workload'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 240,
        can_click: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
        getValue: !this.isListTab ? K8sTableNew.getWorkloadValue(WORKLOAD, 1) : null,
      },
      [NAMESPACE]: {
        id: NAMESPACE,
        name: this.$t('namespace'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 160,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [CONTAINER]: {
        id: CONTAINER,
        name: this.$t('container'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 150,
        can_click: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [INGRESS]: {
        id: INGRESS,
        name: this.$t('ingress'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 150,
        can_click: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [SERVICE]: {
        id: SERVICE,
        name: this.$t('service'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 150,
        can_click: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
      [NODE]: {
        id: NODE,
        name: this.$t('node'),
        sortable: false,
        type: K8sTableColumnTypeEnum.RESOURCES_TEXT,
        min_width: 150,
        can_click: true,
        k8s_filter: this.isListTab,
        k8s_group: this.isListTab,
      },
    };
  }

  /**
   * @description 重新渲染表格组件（主要是为了处理 table column 的 sort 状态）
   */
  refreshTable() {
    this.removeScrollListener();
    this.refreshKey = random(10);
    this.$nextTick(() => {
      this.addScrollListener();
    });
  }

  /**
   * @description 初始化排序
   * @param {string} orderBy 排序字段
   */
  initSortContainer(sort: Partial<Omit<K8sTableSortContainer, 'initDone'>> = {}) {
    let sortProp: K8sTableColumnChartKey | null = sort.prop;
    if (!this.tableChartColumns.ids?.includes(sortProp)) {
      if (this.tableChartColumns.ids.length) {
        sortProp = this.tableChartColumns.ids[0];
      } else {
        sortProp = null;
      }
    }
    this.sortContainer = {
      ...this.sortContainer,
      ...sort,
      prop: sortProp,
    };
    this.routerParamChange();
    this.sortContainer.initDone = false;
  }
  /**
   * @description 添加滚动监听
   */
  addScrollListener() {
    this.removeScrollListener();
    this.scrollContainer = this.$el.querySelector(SCROLL_CONTAINER_DOM);
    this.scrollContainer.addEventListener('scroll', this.handleScroll);
  }
  /**
   * @description 移除滚动监听
   */
  removeScrollListener() {
    if (!this.scrollContainer) return;
    this.scrollContainer.removeEventListener('scroll', this.handleScroll);
    this.scrollTimer && clearTimeout(this.scrollTimer);
    this.scrollContainer = null;
  }

  /**
   * @description 处理滚动事件
   */
  handleScroll() {
    const childrenArr = this.$el.querySelectorAll(DISABLE_TARGET_DOM);
    if (!childrenArr?.length) {
      return;
    }
    const setDomPointerEvents = (val: 'auto' | 'none') => {
      // @ts-ignore
      for (const children of childrenArr) {
        children.style.pointerEvents = val;
      }
    };
    setDomPointerEvents('none');
    this.scrollTimer && clearTimeout(this.scrollTimer);
    this.scrollTimer = setTimeout(() => {
      setDomPointerEvents('auto');
    }, 600);
  }

  @Debounce(200)
  debounceGetK8sList() {
    this.getK8sList({ needRefresh: true });
  }

  /**
   * @description 计算滚动边界（兼容屏幕过大，或dpr过小，显示记录条数不足以显示滚动条从而无法触发触底滚动逻辑的场景）
   * @returns {number} page 保证能够触发触底加载逻辑的最低页数
   */
  calculateRollingBoundary() {
    if (!this.tableViewportContainer) {
      return 1;
    }
    const wrapperContainer = this.tableViewportContainer;
    const wrapperRect = wrapperContainer?.getBoundingClientRect?.();
    const wrapperStyle = window.getComputedStyle(wrapperContainer);
    const wrapperPaddingHeight =
      Number.parseInt(wrapperStyle?.paddingTop) + Number.parseInt(wrapperStyle?.paddingBottom);
    const scrollHeight = wrapperRect?.height - (wrapperPaddingHeight || 0) - TABLE_ROW_MIN_HEIGHT;
    return Math.ceil(scrollHeight / TABLE_ROW_MIN_HEIGHT / this.pagination.pageSize) + 1 || 1;
  }

  /**
   * @description 获取k8s列表
   * @param {boolean} config.needRefresh 是否需要刷新表格状态
   * @param {boolean} config.needIncrement 是否需要增量加载（table 触底加载）
   */
  async getK8sList(config: { needIncrement?: boolean; needRefresh?: boolean } = {}) {
    if (!this.filterCommonParams.bcs_cluster_id || this.tableLoading.scrollLoading || !this.metricList?.length) {
      return;
    }

    this.abortAsyncData();
    let loadingKey = 'scrollLoading';
    const initPagination = () => {
      this.pagination.page = this.calculateRollingBoundary() || 1;
      loadingKey = 'loading';
    };
    let pageRequestParam = {};
    // 是否启用前端分页
    if (enabledFrontendLimit) {
      await this.$nextTick();
      initPagination();
    } else {
      if (!config.needIncrement) {
        await this.$nextTick();
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
    // 汇聚类型
    const method = this.metricsForConvergeMap[this.sortContainer.prop] || K8sConvergeTypeEnum.SUM;
    // 资源类型
    const resourceType = this.resourceType;

    const { timeRange, ...filterCommonParams } = this.filterCommonParams;
    const formatTimeRange = handleTransformToTimestamp(timeRange);
    const sortParams = this.sortContainer.prop
      ? {
          column: this.sortContainer.prop,
          order_by: this.sortContainer.orderBy,
        }
      : {};

    /** 获取资源列表请求接口参数 */
    const requestParam = {
      ...filterCommonParams,
      ...sortParams,
      ...pageRequestParam,
      start_time: formatTimeRange[0],
      end_time: formatTimeRange[1],
      resource_type: resourceType,
      with_history: true,
      page_type: this.pagination.pageType,
      method,
    };

    const abortController = new AbortController();
    this.abortControllerQueue.add(abortController);
    let isAborted = false;
    const data: { count: number; items: K8sTableRow[] } = await listK8sResources(requestParam, {
      signal: abortController.signal,
      needMessage: false,
    }).catch(err => {
      if (err?.message === 'canceled') {
        isAborted = true;
      } else {
        const message = makeMessage(err.error_details || err.message);
        bkMessage(message);
      }
      return {
        count: 0,
        items: [],
      };
    });
    this.abortControllerQueue.delete(abortController);
    if (isAborted) {
      return;
    }
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
    if (key === K8sTableColumnKeysEnum.WORKLOAD) {
      return `${data[K8sTableColumnKeysEnum.NAMESPACE]}|${data[key]}`;
    }
    return data[key];
  }

  /**
   * @description 格式化接口数据结构为table需要的数据结构，并返回异步请求加载 图表数据 时需要数据
   */
  formatTableData(
    tableData: K8sTableRow[],
    resourceType: K8sTableColumnResourceKey,
    requestColumns?: K8sTableColumnChartKey[]
  ): Map<K8sTableColumnChartKey, { ids: Set<string>; indexForId: Record<string, number[]> }> {
    let asyncColumns = requestColumns;
    if (!requestColumns) {
      asyncColumns = this.tableChartColumns.ids;
    }
    return tableData.reduce((prev, curr, index) => {
      const id = this.getResourceId(resourceType, curr as any);
      for (const columnKey of asyncColumns) {
        const item = this.asyncDataCache.get(columnKey);
        // 缓存数据中是否已经存在当前id的当前指标数据
        if (item?.[id]?.datapoints) {
          curr[columnKey] = item[id];
        } else {
          // 缓存中不存在则需要是初始化一个空数据，保证响应式功能
          curr[columnKey] = {
            datapoints: null,
            unit: '',
            unitDecimal: null,
            valueTitle: this.$tc('用量'),
          };

          if (!prev.has(columnKey)) {
            prev.set(columnKey, { ids: new Set(), indexForId: {} });
          }
          const { ids, indexForId } = prev.get(columnKey);
          // 获取需要请求指标数据后需要更新数据的数据行索引，
          if (indexForId[id]) {
            indexForId[id].push(index);
          } else {
            indexForId[id] = [index];
          }
          // 获取需要请求指标数据的行id，
          if (!ids.has(id)) {
            ids.add(id);
          }
        }
      }
      return prev;
    }, new Map());
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
  }

  /**
   * @description 异步加载获取k8s列表（cpu、内存使用率）的数据
   */
  loadAsyncData(
    resourceType: K8sTableColumnResourceKey,
    resourceParam: Map<K8sTableColumnChartKey, { ids: Set<string>; indexForId: Record<string, number[]> }>,
    requestColumns?: K8sTableColumnChartKey[]
  ) {
    let asyncColumns = requestColumns;
    if (!requestColumns) {
      asyncColumns = this.tableChartColumns.ids;
    }
    for (const field of asyncColumns) {
      const { ids, indexForId } = resourceParam.get(field as K8sTableColumnChartKey) || {};
      if (!ids?.size) {
        continue;
      }
      const controller = new AbortController();
      this.abortControllerQueue.add(controller);
      const { timeRange, ...filterCommonParams } = this.filterCommonParams;
      const formatTimeRange = handleTransformToTimestamp(timeRange);
      resourceTrend(
        {
          ...filterCommonParams,
          start_time: formatTimeRange[0],
          end_time: formatTimeRange[1],
          column: field,
          method: this.metricsForConvergeMap[field] || K8sConvergeTypeEnum.SUM,
          resource_type: resourceType,
          resource_list: Array.from(
            new Set(
              Array.from(ids).map((id: string) =>
                resourceType === K8sTableColumnKeysEnum.CONTAINER ? id.split(':')?.[1] || id : id
              )
            )
          ),
        },
        { signal: controller.signal, needMessage: false }
      )
        .then(tableAsyncData => {
          this.renderTableBatchByBatch(field, tableAsyncData, indexForId);
        })
        .catch(() => {
          // 接口请求失败，渲染空数据
          this.renderTableBatchByBatch(field, [], indexForId);
        })
        .finally(() => {
          this.abortControllerQueue.delete(controller);
        });
    }
  }

  /**
   * @description 批量按需渲染表格数据（cpu、内存使用率）
   * @param columnKey column 列id
   * @param tableAsyncData 异步数据
   * @param tableDataMap tableDataMap 异步数据id 对应 tableData 索引 映射数组
   */
  renderTableBatchByBatch(columnKey: K8sTableColumnChartKey, tableAsyncData, tableDataMap: Record<string, number[]>) {
    let chartDataForResourceIdMap = this.asyncDataCache.get(columnKey);
    if (!chartDataForResourceIdMap) {
      chartDataForResourceIdMap = {};
      this.asyncDataCache.set(columnKey, chartDataForResourceIdMap);
    }

    for (const data of tableAsyncData) {
      const resourceId = data.resource_name;
      const chartData = data[columnKey];
      // 动态转化单位(自动转化为合适的单位)
      this.chartDataFormatterByUnit(chartData, columnKey);

      chartDataForResourceIdMap[resourceId] = chartData;
      const rowIndexArr = tableDataMap[resourceId];
      if (rowIndexArr?.length) {
        for (const rowIndex of rowIndexArr) {
          const rowData = this.tableData[rowIndex];
          rowData[columnKey] = chartData || [];
        }
        delete tableDataMap[resourceId];
      }
    }
    // 查看是否有剩余后端未返回的数据，如果有则赋值空数组消除loading状态
    const indexArr = Object.values(tableDataMap);
    for (const rowIndexArr of indexArr) {
      for (const rowIndex of rowIndexArr) {
        this.tableData[rowIndex][columnKey] = {
          datapoints: [],
          unit: '',
          unitDecimal: null,
          valueTitle: this.$tc('用量'),
        };
      }
    }
  }

  /**
   * @description 自动格式化指标数据
   * @param chartData
   * @param columnKey
   */
  chartDataFormatterByUnit(chartData, columnKey: K8sTableColumnChartKey, unitDecimal = 2) {
    if (this.metricsForConvergeMap?.[columnKey] === K8sConvergeTypeEnum.COUNT) {
      chartData.unit = '';
      return;
    }
    // 动态转化单位
    const chartVal = chartData?.datapoints?.[0]?.[0];
    if (!chartData?.datapoints) {
      chartData.datapoints = [];
    } else if (![undefined, null].includes(chartVal)) {
      const unitFormatter = (value, decimal) => {
        let set = { text: value };
        if (!['', 'none', undefined, null].includes(chartData.unit)) {
          const valueFormatter = getValueFormat(chartData.unit || '');
          set = valueFormatter(value, decimal);
          if (Number(set.text) !== 0) {
            set.text = Number.parseFloat(set.text).toFixed(decimal);
          }
        }
        return set;
      };

      const set = unitFormatter(chartVal, chartData.unitDecimal || unitDecimal);
      chartData.datapoints[0][0] = set.text;
      // @ts-ignore
      chartData.unit = set.suffix;
    }
  }

  /**
   * @description table label 点击回调
   * @param {K8sTableClickEvent} item
   */
  handleLabelClick(item: K8sTableClickEvent) {
    const { row, column } = item;
    const detail: Partial<Record<K8sTableColumnKeysEnum, string> & { externalParam: { isCluster: boolean } }> = {
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
   * @param {TableSort} sortItem { prop, order }
   */
  handleSortChange(sortItem: TableSort) {
    if (!this.sortContainer.initDone) {
      this.sortContainer.initDone = true;
      return;
    }

    this.sortContainer.prop = sortItem.prop;
    this.sortContainer.orderBy = sortItem.order === 'descending' ? 'desc' : 'asc';
    this.routerParamChange();
    this.getK8sList({
      needRefresh: true,
    });
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
   * @description 表格指标列 汇聚类型改变后回调
   * @param {K8sTableColumnChartKey} columnKey 需要改变的指标列
   * @param {K8sConvergeTypeEnum} val 汇聚类型改变后的值
   */
  handleConvergeChange(columnKey: K8sTableColumnChartKey, val: K8sConvergeTypeEnum) {
    if (this.metricsForConvergeMap?.[columnKey] === val) {
      return;
    }
    this.$set(this.metricsForConvergeMap, columnKey, val);
    this.asyncDataCache.set(columnKey, {});
    if (this.sortContainer.prop === columnKey) {
      this.routerParamChange();
      this.tableLoading.loading = true;
      this.getK8sList({
        needRefresh: true,
      });
    } else {
      const resourceType = this.resourceType;
      const resourceParam = this.formatTableData(this.tableData, resourceType, [columnKey]);
      this.loadAsyncData(resourceType, resourceParam, [columnKey]);
    }
  }

  /**
   * @description 表格列 header 渲染配置方法
   */
  metricsColumnHeaderRender(column: K8sTableColumn<K8sTableColumnChartKey>) {
    const { id, name, category_name } = column;
    return (
      <div
        class='k8s-metrics-header'
        onClick={e => {
          e.stopPropagation();
        }}
      >
        <div class='header-category'>
          <K8sConvergeSelect
            method={this.metricsForConvergeMap[id]}
            onMethodChange={v => this.handleConvergeChange(id, v)}
          />
          <span
            class='label'
            v-bk-overflow-tips
          >
            {category_name}
          </span>
        </div>
        <div class='header-metrics'>
          <span>{name}</span>
        </div>
      </div>
    );
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
        ? { className: ['selected'], text: '移除该筛选项' }
        : { className: ['icon-monitor icon-a-sousuo'], text: '添加为筛选项' };
      return (
        <i
          class={elAttr.className}
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
        onHandleDrillDown={v => this.onDrillDown({ ...(v as DrillDownEvent), filterById }, true)}
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
          {column.can_click && text !== '--' ? (
            <span
              class='col-item-label can-click'
              onClick={() => this.handleLabelClick({ column, row, index })}
            >
              {text}
            </span>
          ) : (
            <span class='col-item-label'>{text}</span>
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
          <div class='k8s-metric-column'>
            <img
              class='loading-svg'
              alt=''
              src={loadingIcon}
            />
          </div>
        );
      }
      if ([undefined, null].includes(chartData?.datapoints?.[0]?.[0])) {
        return (
          <div class='k8s-metric-column'>
            <span class='value'>--</span>
          </div>
        );
      }
      const { datapoints, unit = '', valueTitle = this.$t('用量') } = chartData;
      const value = `${datapoints?.[0]?.[0]} ${unit}`;
      return (
        <div
          class='k8s-metric-column'
          v-bk-overflow-tips={{ interactive: false, content: `${valueTitle}：${value}` }}
        >
          <span class='value'>{value}</span>
        </div>
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
        fixed={column.fixed}
        formatter={this.handleSetFormatter(column)}
        header-align={column.header_align}
        label={column.name}
        min-width={column.min_width}
        prop={column.id}
        render-header={column?.renderHeader ? () => column.renderHeader(column) : undefined}
        resizable={typeof column.resizable === 'boolean' ? column.resizable : true}
        show-overflow-tooltip={false}
        sort-orders={['ascending', 'descending']}
        sortable={column.sortable}
      />
    );
  }

  render() {
    return (
      <div
        ref='tableViewportContainer'
        class='k8s-table-new'
      >
        <bk-table
          key={this.refreshKey}
          ref='table'
          style={{
            display: !this.tableLoading.loading ? 'block' : 'none',
            '--row-min-height': `${TABLE_ROW_MIN_HEIGHT}px`,
          }}
          height='100%'
          default-sort={{
            prop: this.sortContainer.prop,
            order: this.sortContainer.orderBy === 'asc' ? 'ascending' : 'descending',
          }}
          border={false}
          data={this.tableViewData}
          outer-border={false}
          size='small'
          on-scroll-end={this.handleTableScrollEnd}
          on-sort-change={val => this.handleSortChange(val as TableSort)}
        >
          {this.tableColumns.map(column => this.transformColumn(column))}
          <div
            class='k8s-table-loading'
            slot='append'
          >
            {this.tableHasScrollLoading ? (
              <bk-spin
                style={{
                  display: 'flex',
                }}
                placement='right'
                size='mini'
              >
                {this.$t('加载中')}
              </bk-spin>
            ) : null}
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
