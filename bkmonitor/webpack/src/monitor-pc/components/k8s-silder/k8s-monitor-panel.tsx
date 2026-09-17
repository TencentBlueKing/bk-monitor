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
import { Component, Emit, Mixins, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listBcsCluster, scenarioMetricList } from 'monitor-api/modules/k8s';
import { random } from 'monitor-common/utils';

import { getDefaultTimezone } from '../../i18n/dayjs';
import NewUserConfigMixin from '../../mixins/newUserStoreConfig';
import K8sEventExplore from '../../pages/event-explore/k8s-event-explore';
import FilterByCondition from '../../pages/monitor-k8s/components/filter-by-condition/filter-by-condition';
import GroupByCondition from '../../pages/monitor-k8s/components/group-by-condition/group-by-condition';
import K8SCharts from '../../pages/monitor-k8s/components/k8s-charts/k8s-charts';
import K8sDimensionList from '../../pages/monitor-k8s/components/k8s-left-panel/k8s-dimension-list';
import K8sLeftPanel from '../../pages/monitor-k8s/components/k8s-left-panel/k8s-left-panel';
import K8sMetricList from '../../pages/monitor-k8s/components/k8s-left-panel/k8s-metric-list';
import K8sTableNew, {
  type K8sTableColumnResourceKey,
  type K8sTableGroupByEvent,
} from '../../pages/monitor-k8s/components/k8s-table-new/k8s-table-new';
import { K8sGroupDimension, sceneDimensionMap } from '../../pages/monitor-k8s/k8s-dimension';
import {
  type ICommonParams,
  type IFilterCommonParams,
  type IK8SMetricItem,
  type ITableCommonParams,
  EDimensionKey,
  K8sNewTabEnum,
  SceneEnum,
} from '../../pages/monitor-k8s/typings/k8s-new';
import { EMode } from '../retrieval-filter/utils';
import { DEFAULT_TIME_RANGE } from '../time-range/utils';
import { parseK8sMonitorQuery } from './utils';

import type { IWhere } from '../../pages/monitor-k8s/typings';
import type { TimeRangeType } from '../time-range/time-range';
import type { IBcsClusterItem, K8sMonitorInitialParams, K8sMonitorState, K8sMonitorStateChangeEvent } from './typings';

import '../../pages/monitor-k8s/monitor-k8s-new.scss';

const HIDE_METRICS_KEY = 'monitor_k8s_hide_metrics';

/** 网络场景默认隐藏的指标 */
const networkDefaultHideMetrics = [
  'nw_container_network_receive_errors_total',
  'nw_container_network_transmit_errors_total',
];

/** 过滤区默认高度，与样式中的 min-height 保持一致 */
const DEFAULT_FILTER_HEADER_HEIGHT = 50;

const tabList = [
  {
    label: window.i18n.t('K8s对象列表'),
    id: K8sNewTabEnum.LIST,
    icon: 'icon-mc-list',
  },
  {
    label: window.i18n.t('指标视图'),
    id: K8sNewTabEnum.CHART,
    icon: 'icon-zhibiao',
  },
  {
    label: window.i18n.t('K8s集群数据详情'),
    id: K8sNewTabEnum.DETAIL,
    icon: 'icon-Component',
  },
];

/** navBar 作用域插槽向外暴露的上下文 */
export interface K8sMonitorNavBarScope {
  refreshInterval: number;
  scene: SceneEnum;
  showCancelDrill: boolean;
  timeRange: TimeRangeType;
  timezone: string;
  onCancelDrillDown: () => void;
  onImmediateRefresh: () => void;
  onRefreshChange: (value: number) => void;
  onSceneChange: (scene: SceneEnum) => void;
  onTimeRangeChange: (timeRange: TimeRangeType) => void;
  onTimezoneChange: (timezone: string) => void;
}

export interface K8sMonitorPanelEvents {
  onStateChange: (event: K8sMonitorStateChangeEvent) => void;
}

export interface K8sMonitorPanelProps {
  initialParams?: K8sMonitorInitialParams | null;
  queryCacheKey?: string;
}

export interface K8sMonitorPanelSlots {
  navBar?: K8sMonitorNavBarScope;
}

/**
 * 容器监控（新版）视图主体。
 *
 * 只吃 props、只抛事件，自身不读写路由，因此既能被 `/k8s-new` 路由页承载，
 * 也能被侧滑等任意容器复用。顶部导航通过 `navBar` 作用域插槽外置，
 * 不传该插槽即为「无 header」形态。
 */
@Component
export default class K8sMonitorPanel extends Mixins(
  NewUserConfigMixin,
  tsc<K8sMonitorPanelProps, K8sMonitorPanelEvents, K8sMonitorPanelSlots>
) {
  /** 初始状态；为空表示由调用方交给组件自行决定（配合 queryCacheKey 恢复上次查询条件） */
  @Prop({ type: Object, default: null }) initialParams: K8sMonitorInitialParams | null;
  /** 无初始状态时用于恢复上次查询条件的用户配置 key 前缀，不传则不启用 */
  @Prop({ type: String, default: '' }) queryCacheKey: string;

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 刷新间隔
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  // 是否立即刷新
  @ProvideReactive('refreshImmediate') refreshImmediate = '';
  @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('showRestore') showRestore = false;
  // 场景
  @ProvideReactive('scene')
  scene: SceneEnum = SceneEnum.Performance;
  // 集群
  cluster = '';
  /** 集群选择器下拉折叠状态 */
  clusterToggle = false;
  // 集群列表
  clusterList: IBcsClusterItem[] = [];
  // 集群加载状态
  clusterLoading = true;
  // 当前 tab
  activeTab = K8sNewTabEnum.LIST;
  filterBy: Record<string, string[]> = {};
  // Group By 选择器的值
  @ProvideReactive('groupInstance')
  groupInstance: K8sGroupDimension = K8sGroupDimension.createInstance(SceneEnum.Performance);

  // 是否展示撤回下钻
  showCancelDrill = false;

  bizId = this.$store.getters.bizId;

  cacheFilterBy: Record<string, string[]> = {};
  cacheGroupBy: K8sTableColumnResourceKey[] = [];

  /** 指标列表 */
  metricList: IK8SMetricItem[] = [];
  // 指标隐藏项
  hideMetrics: string[] = [];
  /** 当前选中的指标 */
  activeMetricId = '';

  metricLoading = true;
  /** 自动刷新定时器 */
  timer = null;
  /** 各维度数据总和 */
  dimensionTotal: Record<string, number> = {};

  cacheTimeRange = [];

  resizeObserver: ResizeObserver = null;
  /** 外置导航区实际高度，未使用 navBar 插槽时为 0 */
  navBarHeight = 0;
  filterHeaderHeight = DEFAULT_FILTER_HEADER_HEIGHT;
  /** 事件场景字段 */
  eventWhere: IWhere[] = [];
  eventQueryString = '';
  eventFilterMode = EMode.ui;

  get isChart() {
    return this.activeTab === K8sNewTabEnum.CHART;
  }

  /** 内容区需要扣除的头部总高度 */
  get headerHeight() {
    return this.navBarHeight + this.filterHeaderHeight;
  }

  /** 当前选择的集群 */
  get selectCluster() {
    return this.clusterList.find(item => item.id === this.cluster);
  }

  get groupFilters() {
    return this.groupInstance.groupFilters;
  }

  // 禁用的指标列表
  get disabledMetricList(): { id: string; tooltips: string }[] {
    /** 最后一级维度 */
    const { groupByDimensions: dimensions } = this.groupInstance;
    const lastDimension =
      this.activeTab === K8sNewTabEnum.DETAIL
        ? dimensions[dimensions.length - 1]
        : this.groupInstance.getResourceType();
    const disabledMetricList = [];
    for (const metrics of this.metricList) {
      for (const metric of metrics.children) {
        if ((metric.unsupported_resource || []).includes(lastDimension)) {
          disabledMetricList.push({
            id: metric.id,
            tooltips: this.$t('该指标在当前级别({0})不可用', [lastDimension]),
          });
        }
      }
    }
    return disabledMetricList;
  }

  /** 最终需要隐藏的指标项， 需要通过用户配置以及groupBy选择两种一起判断 */
  get resultHideMetrics(): string[] {
    const set = new Set<string>([...this.hideMetrics, ...this.disabledMetricList.map(item => item.id)]);
    return Array.from(set);
  }

  /** 当前场景下的维度列表 */
  get sceneDimensionList() {
    return sceneDimensionMap[this.scene] || [];
  }

  /** 公共参数 */
  @ProvideReactive('commonParams')
  get commonParams(): ICommonParams {
    return {
      scenario: this.scene,
      bcs_cluster_id: this.cluster,
      timeRange: this.timeRange,
    };
  }

  get tableCommonParam(): ITableCommonParams {
    return {
      ...this.commonParams,
      filter_dict: Object.fromEntries(Object.entries(this.filterBy).filter(([, v]) => v?.length)),
    };
  }

  get filterCommonParams(): IFilterCommonParams {
    return {
      ...this.tableCommonParam,
      resource_type: this.groupInstance.groupFilters.at(-1),
      with_history: false,
    };
  }

  /** 完整状态快照，供调用方回写 URL */
  get currentState(): K8sMonitorState {
    return {
      timeRange: this.timeRange,
      refreshInterval: this.refreshInterval,
      cluster: this.cluster,
      scene: this.scene,
      activeTab: this.activeTab,
      filterBy: this.filterBy,
      groupBy: this.groupInstance.groupFilters,
      where: this.eventWhere,
      queryString: this.eventQueryString,
      filterMode: this.eventFilterMode,
    };
  }

  /**
   * @description 状态变更抛给调用方，由其决定是否写入 URL
   * @param extra 表格排序等不属于视图状态的附加 query，原样透传
   */
  @Emit('stateChange')
  emitStateChange(extra: Record<string, any> = {}): K8sMonitorStateChangeEvent {
    return { state: this.currentState, extra };
  }

  setGroupFilters(groupId: K8sTableColumnResourceKey, config?: { single: boolean }) {
    if (this.groupInstance.hasGroupFilter(groupId)) {
      this.groupInstance.deleteGroupFilter(groupId, config);
      return;
    }
    this.groupInstance?.addGroupFilter(groupId, config);
  }

  @Watch('groupFilters')
  watchGroupFiltersChange() {
    this.emitStateChange({
      tableSort: '',
      tableOrder: '',
      tableMethod: '',
    });
  }

  @Watch('filterBy', { deep: true })
  watchFilterByChange() {
    this.emitStateChange();
  }

  /**
   * @description 表格下钻点击回调
   * @param {K8sTableGroupByEvent} item
   */
  @Provide('onGroupChange')
  handleTableGroupChange(item: K8sTableGroupByEvent, showCancelDrill = false) {
    const cacheGroupBy = [...this.groupInstance.groupFilters];
    const cacheFilterBy = JSON.parse(JSON.stringify(this.filterBy));
    const { filterById, id, dimension } = item;
    this.handleDrillDown(filterById, id, dimension);
    if (showCancelDrill) {
      this.showCancelDrill = true;
      this.cacheGroupBy = cacheGroupBy;
      this.cacheFilterBy = cacheFilterBy;
    }
  }

  /**
   * 修改filterBy
   * @param id 数据Id
   * @param dimensionId 维度Id
   * @param isSelect 是否选中
   */
  @Provide('onFilterChange')
  filterByChange(id: string, dimensionId: string, isSelect: boolean) {
    this.showCancelDrill = false;
    if (!this.filterBy[dimensionId]) {
      this.$set(this.filterBy, dimensionId, []);
    }
    if (isSelect) {
      if (!this.groupInstance.hasGroupFilter(dimensionId as K8sTableColumnResourceKey)) {
        this.groupByChange(dimensionId, true);
      }
      /** workload维度只能选择一项 */
      if (dimensionId === EDimensionKey.workload) {
        this.$set(this.filterBy, dimensionId, [id]);
      } else if (!this.filterBy[dimensionId].includes(id)) {
        this.filterBy[dimensionId].push(id);
      }
    } else {
      this.$set(
        this.filterBy,
        dimensionId,
        this.filterBy[dimensionId].filter(item => item !== id)
      );
    }
  }

  async created() {
    if (this.initialParams) {
      this.applyInitialParams(this.initialParams);
      this.getClusterList();
    } else if (this.queryCacheKey) {
      /** 无初始状态且开启了缓存，先定位默认集群再取该集群上次的查询条件 */
      await this.getClusterList();
      const data = await this.handleGetUserConfig<Record<string, string | string[]>>(
        `${this.queryCacheKey}_${this.bizId}_${this.cluster}`
      );
      data && this.applyInitialParams(parseK8sMonitorQuery(data));
    } else {
      this.getClusterList();
    }
    this.getScenarioMetricList();
    this.getHideMetrics();
  }

  mounted() {
    this.observerFilterByHeader();
  }

  destroyed() {
    this.resizeObserver?.disconnect();
    this.timer && clearInterval(this.timer);
  }

  /** 应用外部传入的初始状态 */
  applyInitialParams(params: K8sMonitorInitialParams) {
    this.timeRange = params.timeRange ?? DEFAULT_TIME_RANGE;
    this.refreshInterval = params.refreshInterval ?? -1;
    this.cluster = params.cluster ?? '';
    this.scene = params.scene ?? SceneEnum.Performance;
    if (this.scene === SceneEnum.Event) {
      this.eventFilterMode = params.filterMode || EMode.ui;
      this.eventWhere = params.where || [];
      this.eventQueryString = params.queryString || '';
    } else {
      this.initGroupBy();
      this.initFilterBy();
      this.activeTab = params.activeTab ?? K8sNewTabEnum.LIST;
      this.groupInstance.setGroupFilters(params.groupBy || []);
      this.filterBy = { ...this.filterBy, ...(params.filterBy || {}) };
    }
  }

  observerFilterByHeader() {
    this.resizeObserver?.disconnect();
    const filterEl = this.$el.querySelector('.____monitor-k8s-new-header');
    const navBarEl = this.$el.querySelector('.____k8s-monitor-nav-bar');
    this.navBarHeight = navBarEl ? navBarEl.getBoundingClientRect().height : 0;
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const height = entry?.contentRect?.height || 0;
        if (entry.target === navBarEl) {
          this.navBarHeight = height;
        } else {
          this.filterHeaderHeight = height || DEFAULT_FILTER_HEADER_HEIGHT;
        }
      }
    });
    navBarEl && this.resizeObserver.observe(navBarEl);
    filterEl && this.resizeObserver.observe(filterEl);
  }

  /** 初始化filterBy结构 */
  initFilterBy() {
    this.filterBy = this.sceneDimensionList.reduce((pre, cur) => {
      pre[cur] = [];
      return pre;
    }, {});
  }

  /** 重新实例化 GroupBy */
  initGroupBy() {
    this.groupInstance = K8sGroupDimension.createInstance(this.scene);
  }

  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }

  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }

  async getClusterList() {
    this.clusterLoading = true;
    this.clusterList = await listBcsCluster().catch(() => []);
    this.clusterLoading = false;
    if (this.clusterList.length && !this.cluster) {
      this.cluster = this.clusterList[0].id;
    }
    this.emitStateChange();
  }

  /**
   * @description 获取场景指标列表
   */
  async getScenarioMetricList() {
    this.metricList = [];
    if (this.scene === SceneEnum.Event) return;
    this.metricLoading = true;
    const data = await scenarioMetricList({ scenario: this.scene }).catch(() => []);
    this.metricLoading = false;
    this.metricList = data.map(item => ({
      ...item,
      count: item.children.length,
    }));
  }

  /** 获取隐藏的指标项 */
  getHideMetrics() {
    this.handleGetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`).then((res: string[]) => {
      if (this.scene === SceneEnum.Network && !res) {
        /** 网络场景初始化，默认隐藏丢包量指标 */
        this.hideMetrics = [...networkDefaultHideMetrics];
      } else {
        this.hideMetrics = res || [];
      }
    });
  }

  /** 场景切换 */
  handleSceneChange(value: SceneEnum) {
    const oldScene = this.scene;
    this.scene = value;
    /** 非事件场景之间切换，对filterBy和groupBy查询条件取交集 */
    if (oldScene !== SceneEnum.Event && value !== SceneEnum.Event) {
      this.filterBy = this.sceneDimensionList.reduce((pre, cur) => {
        if (Object.hasOwn(this.filterBy, cur)) {
          pre[cur] = this.filterBy[cur];
        } else {
          pre[cur] = [];
        }
        return pre;
      }, {});
      const groupBy = this.groupFilters.filter(item => this.sceneDimensionList.includes(item));
      this.initGroupBy();
      if (groupBy.length) this.groupInstance.setGroupFilters(groupBy);
    } else {
      this.initFilterBy();
      this.initGroupBy();
    }
    this.getHideMetrics();
    this.getScenarioMetricList();
    this.emitStateChange();
    this.showCancelDrill = false;
    this.$nextTick(() => {
      this.observerFilterByHeader();
    });
  }

  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
    this.emitStateChange();
    this.timer && clearInterval(this.timer);
    if (value > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, value);
    }
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.timeRange = timeRange;
    this.emitStateChange();
  }

  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
    // updateTimezone(timezone);
  }

  dimensionTotalChange(dimensionTotal: Record<string, number>) {
    this.dimensionTotal = dimensionTotal;
  }

  /** 撤回下钻 */
  handleCancelDrillDown() {
    this.filterBy = this.cacheFilterBy;
    this.groupInstance.setGroupFilters(this.cacheGroupBy);
    this.showCancelDrill = false;
  }

  /**
   * 修改groupBy
   * @param groupId
   * @param isSelect 是否选中
   */
  groupByChange(groupId: string, isSelect: boolean) {
    this.showCancelDrill = false;
    if (isSelect) {
      this.groupInstance.addGroupFilter(groupId as K8sTableColumnResourceKey);
    } else {
      this.setGroupFilters(groupId as K8sTableColumnResourceKey);
    }
  }

  /**
   * 下钻功能
   * @param filterById 下钻数据Id
   * @param filterByDimension  下钻数据所在维度
   * @param drillDownDimension 下钻维度
   */
  handleDrillDown(filterById: string, filterByDimension: string, drillDownDimension: string) {
    this.filterByChange(filterById, filterByDimension, true);
    this.groupByChange(drillDownDimension, true);
  }

  /** 清除某个维度的filterBy */
  clearFilterBy(dimensionId: string) {
    this.filterBy[dimensionId] = [];
    this.filterBy = { ...this.filterBy };
  }

  /** 隐藏指标项变化 */
  metricHiddenChange(hideMetrics: string[]) {
    this.hideMetrics = hideMetrics;
    /** 网络场景下如果隐藏的指标项和默认隐藏的指标项一致直接初始化 */
    if (
      this.scene === SceneEnum.Network &&
      this.hideMetrics.length === networkDefaultHideMetrics.length &&
      this.hideMetrics.every(item => networkDefaultHideMetrics.includes(item))
    ) {
      this.handleSetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`, JSON.stringify(null));
    } else {
      this.handleSetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`, JSON.stringify(this.hideMetrics));
    }
  }

  /** 指标列表项点击 */
  async handleMetricItemClick(metricId: string) {
    if (this.hideMetrics.includes(metricId) || !metricId) return;
    this.activeTab = K8sNewTabEnum.CHART;
    this.activeMetricId = metricId;
    setTimeout(() => {
      this.activeMetricId = '';
    }, 3000);
  }

  /** 事件场景 过滤模式切换 */
  handleEventFilterModeChange(filterMode: EMode.ui) {
    this.eventFilterMode = filterMode;
    this.emitStateChange();
  }

  /** 事件场景Where条件变更 */
  handleEventWhereChange(where: IWhere[]) {
    this.eventWhere = where;
    this.emitStateChange();
  }

  /** 事件场景queryString修改 */
  handleEventQueryStringChange(queryString: string) {
    this.eventQueryString = queryString;
    this.emitStateChange();
  }

  handleClusterChange(cluster: string) {
    this.cluster = cluster;
    this.eventWhere = [];
    this.eventQueryString = '';
    this.initFilterBy();
    this.groupInstance.initGroupFilter();
    this.showCancelDrill = false;
    this.getScenarioMetricList();
    this.emitStateChange();
  }

  handleClusterToggle(toggle: boolean) {
    this.clusterToggle = toggle;
  }

  /**
   * @description tab切换回调
   * @param {K8sNewTabEnum} v
   */
  async handleTabChange(v: K8sNewTabEnum) {
    this.activeTab = v;
    this.emitStateChange();
  }

  handleGroupChecked(groupId: K8sTableColumnResourceKey) {
    this.showCancelDrill = false;
    this.setGroupFilters(groupId, { single: true });
  }

  /**
   * @description table需要存储路由的值改变后回调，将值透传给调用方
   */
  handleTableRouterParamChange(tableRouterParam: Record<string, any>) {
    this.emitStateChange(tableRouterParam);
  }

  handleTableClearSearch() {
    this.initFilterBy();
  }

  handleFilterByChange(v) {
    this.filterBy = this.sceneDimensionList.reduce((pre, cur) => {
      if (v[cur]) {
        pre[cur] = v[cur];
      } else {
        pre[cur] = [];
      }
      return pre;
    }, {});
    this.showCancelDrill = false;
  }

  tabContentRender() {
    switch (this.activeTab) {
      case K8sNewTabEnum.CHART:
        return (
          <K8SCharts
            activeMetricId={this.activeMetricId}
            filterCommonParams={this.filterCommonParams}
            groupBy={this.groupFilters}
            hideMetrics={this.resultHideMetrics}
            metricList={this.metricList}
          />
        );
      default:
        return (
          <K8sTableNew
            activeTab={this.activeTab}
            filterCommonParams={this.tableCommonParam}
            groupInstance={this.groupInstance}
            hideMetrics={this.resultHideMetrics}
            metricList={this.metricList}
            onClearSearch={this.handleTableClearSearch}
            onRouterParamChange={this.handleTableRouterParamChange}
          />
        );
    }
  }

  renderClusterList() {
    if (this.clusterLoading) return <div class='skeleton-element cluster-skeleton' />;

    return (
      <bk-select
        class='cluster-select'
        clearable={false}
        search-placeholder={this.$t('请输入 关键字')}
        value={this.cluster}
        searchable
        onChange={this.handleClusterChange}
        onToggle={this.handleClusterToggle}
      >
        <div
          class='cluster-select-trigger'
          slot='trigger'
        >
          <span
            class='cluster-name'
            v-bk-overflow-tips
          >
            {this.$t('集群')}: {this.selectCluster?.name}
          </span>
          <span class={`icon-monitor icon-mc-arrow-down ${this.clusterToggle ? 'expand' : ''}`} />
        </div>
        {this.clusterList.map(cluster => (
          <bk-option
            id={cluster.id}
            key={cluster.id}
            name={cluster.name}
          />
        ))}
      </bk-select>
    );
  }

  /** 顶部导航区由调用方通过作用域插槽注入，不传则不渲染（侧滑等无 header 场景） */
  navBarRender() {
    const navBarSlot = this.$scopedSlots.navBar;
    if (!navBarSlot) return undefined;
    return (
      <div class='monitor-k8s-new-nav-bar ____k8s-monitor-nav-bar'>
        {navBarSlot({
          scene: this.scene,
          timeRange: this.timeRange,
          timezone: this.timezone,
          refreshInterval: this.refreshInterval,
          showCancelDrill: this.showCancelDrill,
          onSceneChange: this.handleSceneChange,
          onTimeRangeChange: this.handleTimeRangeChange,
          onTimezoneChange: this.handleTimezoneChange,
          onRefreshChange: this.handleRefreshChange,
          onImmediateRefresh: this.handleImmediateRefresh,
          onCancelDrillDown: this.handleCancelDrillDown,
        } as K8sMonitorNavBarScope)}
      </div>
    );
  }

  render() {
    return (
      <div class={['monitor-k8s-new', 'k8s-monitor-panel', this.scene]}>
        {this.navBarRender()}
        {this.scene === SceneEnum.Event ? (
          <K8sEventExplore
            scopedSlots={{
              filterPrepend: () => this.renderClusterList(),
            }}
            dataId={this.selectCluster?.event_table_id || ''}
            filterMode={this.eventFilterMode}
            queryString={this.eventQueryString}
            where={this.eventWhere}
            onFilterModeChange={this.handleEventFilterModeChange}
            onQueryStringChange={this.handleEventQueryStringChange}
            onSetRouteParams={this.emitStateChange}
            onWhereChange={this.handleEventWhereChange}
          />
        ) : (
          [
            <div
              key='monitor-k8s-new-header'
              class='monitor-k8s-new-header ____monitor-k8s-new-header'
            >
              {this.renderClusterList()}
              <div class='filter-header-wrap'>
                <div class='filter-by-wrap __filter-by__'>
                  <div class='filter-by-title'>{this.$t('过滤条件')}</div>
                  <div class='filter-by-content'>
                    <FilterByCondition
                      commonParams={this.commonParams}
                      filterBy={this.filterBy}
                      onChange={this.handleFilterByChange}
                    />
                  </div>
                </div>
                <div class='filter-by-wrap __group-by__'>
                  <GroupByCondition
                    dimensionTotal={this.dimensionTotal}
                    groupInstance={this.groupInstance}
                    scene={this.scene}
                    title={this.$tc('聚合维度')}
                    onChange={this.handleGroupChecked}
                  />
                </div>
              </div>
            </div>,
            <div
              key='monitor-k8s-new-content'
              style={{
                height: `calc(100% - ${this.headerHeight}px)`,
              }}
              class='monitor-k8s-new-content'
            >
              <div class='content-left'>
                <K8sLeftPanel>
                  <K8sDimensionList
                    key='dimension-list'
                    commonParams={this.commonParams as ICommonParams}
                    filterBy={this.filterBy}
                    groupBy={this.groupFilters}
                    onClearFilterBy={this.clearFilterBy}
                    onDimensionTotal={this.dimensionTotalChange}
                    onDrillDown={this.handleTableGroupChange}
                    onFilterByChange={this.filterByChange}
                    onGroupByChange={this.groupByChange}
                  />
                  <K8sMetricList
                    key='metric-list'
                    activeMetric={this.activeMetricId}
                    disabledMetricList={this.disabledMetricList}
                    hideMetrics={this.resultHideMetrics}
                    loading={this.metricLoading}
                    metricList={this.metricList}
                    onHandleItemClick={this.handleMetricItemClick}
                    onMetricHiddenChange={this.metricHiddenChange}
                  />
                </K8sLeftPanel>
              </div>
              <div class='content-right'>
                <div class='content-tab-wrap'>
                  <bk-tab
                    class='k8s-new-tab'
                    active={this.activeTab}
                    type='unborder-card'
                    {...{ on: { 'update:active': this.handleTabChange } }}
                  >
                    {tabList.map(panel => (
                      <bk-tab-panel
                        key={panel.id}
                        label={panel.label}
                        name={panel.id}
                      >
                        <div
                          class='k8s-tab-panel'
                          slot='label'
                        >
                          <i class={['icon-monitor', panel.icon]} />
                          <span class='panel-name'>{panel.label}</span>
                        </div>
                      </bk-tab-panel>
                    ))}
                  </bk-tab>
                </div>
                <div
                  style={{
                    background: this.activeTab === K8sNewTabEnum.CHART ? 'transparent' : '#fff',
                  }}
                  class='content-main-wrap'
                >
                  {this.tabContentRender()}
                </div>
              </div>
            </div>,
          ]
        )}
      </div>
    );
  }
}
