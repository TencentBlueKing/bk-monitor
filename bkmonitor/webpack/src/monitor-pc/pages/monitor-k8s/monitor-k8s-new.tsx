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
import { Component, Mixins, Provide, ProvideReactive, Watch } from 'vue-property-decorator';

import { listBcsCluster, scenarioMetricList } from 'monitor-api/modules/k8s';
import { random } from 'monitor-common/utils';

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import UserConfigMixin from '../../mixins/userStoreConfig';
import FilterByCondition from './components/filter-by-condition/filter-by-condition';
import GroupByCondition from './components/group-by-condition/group-by-condition';
import K8SCharts from './components/k8s-charts/k8s-charts';
import K8sDimensionList from './components/k8s-left-panel/k8s-dimension-list';
import K8sLeftPanel from './components/k8s-left-panel/k8s-left-panel';
import K8sMetricList from './components/k8s-left-panel/k8s-metric-list';
import K8sNavBar from './components/k8s-nav-bar/K8s-nav-bar';
import K8sTableNew, {
  type K8sTableColumnResourceKey,
  type K8sTableGroupByEvent,
} from './components/k8s-table-new/k8s-table-new';
import { K8sGroupDimension, sceneDimensionMap } from './k8s-dimension';
import { type ICommonParams, type IK8SMetricItem, EDimensionKey, K8sNewTabEnum, SceneEnum } from './typings/k8s-new';

import type { TimeRangeType } from '../../components/time-range/time-range';

import './monitor-k8s-new.scss';

const HIDE_METRICS_KEY = 'monitor_k8s_hide_metrics';

/** 网络场景默认隐藏的指标 */
const networkDefaultHideMetrics = [
  'nw_container_network_receive_errors_total',
  'nw_container_network_transmit_errors_total',
];

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

@Component
export default class MonitorK8sNew extends Mixins(UserConfigMixin) {
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
  clusterList = [];
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
  groupList = [];

  cacheFilterBy: Record<string, string[]> = {};
  cacheGroupBy = [];

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

  resizeObserver = null;
  headerHeight = 102;

  get isChart() {
    return this.activeTab === K8sNewTabEnum.CHART;
  }

  get selectClusterName() {
    return this.clusterList.find(item => item.id === this.cluster)?.name;
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

  // 获取引导页状态
  get showGuidePage() {
    return introduce.getShowGuidePageByRoute(this.$route.meta?.navId);
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

  get tableCommonParam() {
    return {
      ...this.commonParams,
      filter_dict: Object.fromEntries(Object.entries(this.filterBy).filter(([, v]) => v?.length)),
    };
  }

  get filterCommonParams() {
    return {
      ...this.tableCommonParam,
      resource_type: this.groupInstance.groupFilters.at(-1),
      with_history: false,
    };
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
    this.setRouteParams({
      tableSort: '',
      tableOrder: '',
      tableMethod: '',
    });
  }

  @Watch('filterBy', { deep: true })
  watchFilterByChange() {
    this.setRouteParams();
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
    if (!this.filterBy[dimensionId]) this.filterBy[dimensionId] = [];
    if (isSelect) {
      if (!this.groupInstance.hasGroupFilter(dimensionId as K8sTableColumnResourceKey)) {
        this.groupByChange(dimensionId, true);
      }
      /** workload维度只能选择一项 */
      if (dimensionId === EDimensionKey.workload) {
        this.filterBy[dimensionId] = [id];
      } else if (!this.filterBy[dimensionId].includes(id)) {
        this.filterBy[dimensionId].push(id);
      }
    } else {
      this.filterBy[dimensionId] = this.filterBy[dimensionId].filter(item => item !== id);
    }
  }

  created() {
    this.getRouteParams();
    this.getClusterList();
    this.getScenarioMetricList();
    this.getHideMetrics();
  }

  mounted() {
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const height = entry?.contentRect?.height || 50;
        this.headerHeight = 52 + height;
      }
    });
    const el = this.$el.querySelector('.____monitor-k8s-new-header');
    this.resizeObserver.observe(el);
  }

  destroyed() {
    this.resizeObserver.disconnect();
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
    this.setRouteParams();
  }

  /**
   * @description 获取场景指标列表
   */
  async getScenarioMetricList() {
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

  handleSceneChange(value) {
    this.scene = value;
    this.initGroupBy();
    this.initFilterBy();
    this.getScenarioMetricList();
    this.showCancelDrill = false;
    this.getHideMetrics();
    this.setRouteParams();
  }

  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
    this.setRouteParams();
    this.timer && clearInterval(this.timer);
    if (value > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, value);
    }
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.timeRange = timeRange;
    this.setRouteParams();
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

  handleClusterChange(cluster: string) {
    this.cluster = cluster;
    this.initFilterBy();
    this.groupInstance.initGroupFilter();
    this.showCancelDrill = false;
    this.getScenarioMetricList();
    this.setRouteParams();
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
    this.setRouteParams();
  }

  handleGroupChecked(groupId: K8sTableColumnResourceKey) {
    this.showCancelDrill = false;
    this.setGroupFilters(groupId, { single: true });
  }

  /**
   * @description table需要存储路由的值改变后回调，将值存入路由
   */
  handleTableRouterParamChange(tableRouterParam: Record<string, any>) {
    this.setRouteParams(tableRouterParam);
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

  getRouteParams() {
    const {
      from = 'now-1h',
      to = 'now',
      refreshInterval = '-1',
      filterBy,
      groupBy,
      cluster = '',
      scene = SceneEnum.Performance,
      activeTab = K8sNewTabEnum.LIST,
    } = this.$route.query || {};
    this.timeRange = [from as string, to as string];
    this.refreshInterval = Number(refreshInterval);
    this.cluster = cluster as string;
    this.scene = scene as SceneEnum;
    this.activeTab = activeTab as K8sNewTabEnum;
    this.initGroupBy();
    if (groupBy && Array.isArray(JSON.parse(groupBy as string))) {
      this.groupInstance.setGroupFilters(JSON.parse(groupBy as string));
    }
    if (!filterBy) {
      this.initFilterBy();
    } else {
      this.filterBy = JSON.parse(filterBy as string);
    }
  }

  setRouteParams(otherQuery = {}) {
    const query = {
      ...this.$route.query,
      sceneId: 'kubernetes',
      from: this.timeRange[0],
      to: this.timeRange[1],
      refreshInterval: String(this.refreshInterval),
      filterBy: JSON.stringify(this.filterBy),
      groupBy: JSON.stringify(this.groupInstance.groupFilters),
      cluster: this.cluster,
      scene: this.scene,
      activeTab: this.activeTab,
      ...otherQuery,
    };

    const targetRoute = this.$router.resolve({
      query,
    });

    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.replace({
        query,
      });
    }
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
            onDrillDown={this.handleTableGroupChange}
          />
        );
      default:
        return (
          <K8sTableNew
            activeTab={this.activeTab}
            filterBy={this.filterBy}
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
  render() {
    if (this.showGuidePage)
      return (
        <GuidePage
          guideData={introduce.data['k8s-new'].introduce}
          guideId='k8s'
        />
      );
    return (
      <div class='monitor-k8s-new'>
        <div class='monitor-k8s-new-nav-bar'>
          <K8sNavBar
            refreshInterval={this.refreshInterval}
            timeRange={this.timeRange}
            timezone={this.timezone}
            value={this.scene}
            onImmediateRefresh={this.handleImmediateRefresh}
            onRefreshChange={this.handleRefreshChange}
            onSelected={this.handleSceneChange}
            onTimeRangeChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          >
            {this.showCancelDrill && (
              <div
                class='cancel-drill-down'
                onClick={this.handleCancelDrillDown}
              >
                <div class='back-icon'>
                  <i class='icon-monitor icon-undo' />
                </div>
                <span class='text'>{this.$t('撤回下钻')}</span>
              </div>
            )}
          </K8sNavBar>
        </div>
        <div class='monitor-k8s-new-header ____monitor-k8s-new-header'>
          {this.clusterLoading ? (
            <div class='skeleton-element cluster-skeleton' />
          ) : (
            <bk-select
              class='cluster-select'
              clearable={false}
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
                  {this.$t('集群')}: {this.selectClusterName}
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
          )}

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
        </div>

        <div
          style={{
            height: `calc(100% - ${this.headerHeight}px)`,
          }}
          class='monitor-k8s-new-content'
        >
          <div class='content-left'>
            <K8sLeftPanel>
              <K8sDimensionList
                commonParams={this.commonParams}
                filterBy={this.filterBy}
                groupBy={this.groupFilters}
                onClearFilterBy={this.clearFilterBy}
                onDimensionTotal={this.dimensionTotalChange}
                onDrillDown={this.handleTableGroupChange}
                onFilterByChange={this.filterByChange}
                onGroupByChange={this.groupByChange}
              />
              <K8sMetricList
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
        </div>
      </div>
    );
  }
}
