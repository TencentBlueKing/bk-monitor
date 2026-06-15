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
import { Component, Inject, InjectReactive, Mixins, Provide, ProvideReactive, Watch } from 'vue-property-decorator';

import { listServiceK8sTargets } from 'monitor-api/modules/apm_container';
import { scenarioMetricList } from 'monitor-api/modules/k8s';
import { random, tryURLDecodeParse } from 'monitor-common/utils';

import introduce from '../../common/introduce';
import GuidePage from '../../components/guide-page/guide-page';
import NewUserConfigMixin from '../../mixins/newUserStoreConfig';
import FilterByCondition from './components/filter-by-condition/filter-by-condition';
import GroupByCondition from './components/group-by-condition/group-by-condition';
import K8SCharts from './components/k8s-charts/k8s-charts';
import K8sTableNew, {
  type K8sTableColumnResourceKey,
  type K8sTableGroupByEvent,
} from './components/k8s-table-new/k8s-table-new';
import { K8sGroupDimension, sceneDimensionMap } from './k8s-dimension';
import {
  type ICommonParams,
  type IFilterCommonParams,
  type IK8SMetricItem,
  type ITableCommonParams,
  EDimensionKey,
  K8sNewTabEnum,
  K8sTableColumnKeysEnum,
  SceneEnum,
} from './typings/k8s-new';

import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IK8sTargetList } from 'monitor-pc/pages/monitor-k8s/typings/book-mark';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings/index';

import './monitor-k8s-apm.scss';

const HIDE_METRICS_KEY = 'monitor_k8s_hide_metrics';

const CACHE_APM_SEARCH_QUERY = 'APM_K8S';

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
export default class MonitorK8sNew extends Mixins(NewUserConfigMixin) {
  @ProvideReactive('showRestore') showRestore = false;
  // 数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 时区
  @InjectReactive('timezone') readonly timezone: string;
  // 刷新间隔
  @InjectReactive('refreshInterval') readonly refreshInterval: number;
  // 是否立即刷新
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;

  @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  // 场景
  @ProvideReactive('scene')
  scene: SceneEnum = SceneEnum.Performance;
  @ProvideReactive('apmResourceType') apmResourceType: '' | IK8sTargetList['resource_type'] = '';
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // apm自定义路由参数
  @InjectReactive({ from: 'customRouteQuery', default: () => ({}) }) customRouteQuery: Record<string, string>;
  @Inject({ from: 'isApmMonitor', default: false }) isApmMonitor!: boolean;
  // 统一事件处理
  @Inject({ from: 'handleApmK8sNewEventChange', default: () => {} }) handleApmK8sNewEventChange: (
    eventName: string,
    params: any
  ) => void;

  // 集群
  cluster = '';
  // 当前 tab
  activeTab = K8sNewTabEnum.LIST;
  filterBy: Record<string, string[]> = {};
  // Group By 选择器的值
  @ProvideReactive('groupInstance')
  groupInstance: K8sGroupDimension = null;

  // 是否展示撤回下钻
  showCancelDrill = false;
  groupList = [];

  bizId = this.$store.getters.bizId;

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

  targetList: IK8sTargetList[] = [];
  targetListToggle = false;
  selectTarget = '';

  isUserManualSwitch = false;
  cacheData: Record<string, { target: string }> = {};

  get isChart() {
    return this.activeTab === K8sNewTabEnum.CHART;
  }

  get groupFilters() {
    return this.groupInstance?.groupFilters || [];
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

  get selectTargetText() {
    if (!this.selectTarget) return this.$t('请选择');
    const { bcs_cluster_id: clusterId = '', namespace = '', workload = '', pod = '' } = this.selectTargetItem || {};
    return `${workload || pod}（集群:${clusterId}）, namespace:${namespace}`;
  }

  // 选中的目标项
  get selectTargetItem() {
    return this.targetList.find(item => item.cacheId === this.selectTarget) || this.targetList[0];
  }

  get appName() {
    return this.viewOptions?.filters?.app_name || '';
  }

  get serviceName() {
    return this.viewOptions?.filters?.service_name || '';
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
      // this.showCancelDrill = true;
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
    // this.showCancelDrill = false;
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

  async created() {
    this.groupInstance = K8sGroupDimension.createInstance(SceneEnum.Performance, this.isApmMonitor);
    const apmK8sParams = this.customRouteQuery?.apmK8sParams ? JSON.parse(this.customRouteQuery?.apmK8sParams) : {};
    await this.getApmK8sData().catch(() => {});
    /** URL没有参数且存在缓存查询条件，使用缓存查询条件 */
    if (!Object.keys(apmK8sParams).length) {
      // 从接口获取缓存的数据
      const cacheRes = await this.handleGetUserConfig<Record<string, { target: string }>>(
        `${CACHE_APM_SEARCH_QUERY}_${this.bizId}_${this.appName}`
      ).catch(() => {});
      this.cacheData = cacheRes ? cacheRes : {};
      if (cacheRes?.[this.serviceName]) {
        this.getRouteParams(cacheRes[this.serviceName]);
      } else {
        this.getRouteParams({
          ...this.selectTargetItem,
          target: this.selectTargetItem.cacheId,
        });
      }
    } else {
      this.getRouteParams(apmK8sParams.selectTarget);
    }
    this.getScenarioMetricList();
    this.getHideMetrics();
    this.setRouteParams();
  }

  mounted() {
    this.observerFilterByHeader();
  }

  observerFilterByHeader() {
    this.resizeObserver?.disconnect();
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        this.headerHeight = entry?.contentRect?.height || 50;
      }
    });
    const el = this.$el.querySelector('.____monitor-k8s-new-header');
    if (el) {
      this.resizeObserver.observe(el);
    }
  }

  beforeDestroy() {
    // 用户手动切换过负载才需要缓存
    if (this.isUserManualSwitch && this.appName) {
      const setData = {
        ...this.cacheData,
        [this.serviceName]: {
          target: this.selectTarget,
        },
      };
      this.handleSetUserConfig(`${CACHE_APM_SEARCH_QUERY}_${this.bizId}_${this.appName}`, JSON.stringify(setData));
    }
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
    this.groupInstance = K8sGroupDimension.createInstance(this.scene, this.isApmMonitor);
  }

  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      // this.timeRange = value;
      this.showRestore = true;
      this.handleApmK8sNewEventChange('apmK8sNewTimeRangeChange', value);
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.handleApmK8sNewEventChange('apmK8sNewTimeRangeChange', JSON.parse(JSON.stringify(this.cacheTimeRange)));
    this.showRestore = false;
  }

  async getApmK8sData() {
    const res = await listServiceK8sTargets({
      app_name: this.appName,
      service_name: this.serviceName,
    }).catch(() => {});
    if (res.target_list?.length) {
      this.targetList = res.target_list.map(item => ({
        ...item,
        cacheId: `${item.bcs_cluster_id}-${item.namespace}-${item.pod || item.workload}`,
      }));
      this.cluster = res.target_list[0]?.bcs_cluster_id || '';
    }
    return;
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

  /**
   * 修改groupBy
   * @param groupId
   * @param isSelect 是否选中
   */
  groupByChange(groupId: string, isSelect: boolean) {
    // this.showCancelDrill = false;
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

  /**
   * @description tab切换回调
   * @param {K8sNewTabEnum} v
   */
  async handleTabChange(v: K8sNewTabEnum) {
    this.activeTab = v;
    this.setRouteParams();
  }

  handleGroupChecked(groupId: K8sTableColumnResourceKey) {
    // this.showCancelDrill = false;
    this.setGroupFilters(groupId, { single: true });
  }

  /** 跳转k8s页面 */
  handleGoToK8sPage() {
    const targetRoute = this.$router.resolve({
      path: '/k8s-new',
      query: {
        sceneId: this.scene,
        filterBy: JSON.stringify(this.filterBy),
        groupBy: JSON.stringify(this.groupFilters),
        activeTab: this.activeTab,
        cluster: this.cluster,
        refreshInterval: String(this.refreshInterval),
        from: this.timeRange[0],
        to: this.timeRange[1],
      }
    });
    window.open(`${location.origin}${location.pathname}${location.search}${targetRoute.href}`, '_blank');
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
    const apmHiddenDimensions =
      this.apmResourceType === 'pod'
        ? [EDimensionKey.namespace, EDimensionKey.workload, EDimensionKey.pod]
        : [EDimensionKey.namespace, EDimensionKey.workload];
    this.filterBy = this.sceneDimensionList.reduce((pre, cur) => {
      if (apmHiddenDimensions.includes(cur)) {
        pre[cur] = this.filterBy[cur] || [];
      } else if (v[cur]) {
        pre[cur] = v[cur];
      } else {
        pre[cur] = [];
      }
      return pre;
    }, {});
    // this.showCancelDrill = false;
  }

  // 切换apm容器targetList
  handleTargetListChange(value: string, oldValue?: string) {
    // if (!oldValue || !Object.keys(this.selectTargetItem).length) return;
    this.selectTarget = value;
    const {
      resource_type: resourceType = '',
      namespace = '',
      workload = '',
      pod = '',
      bcs_cluster_id: cluster = '',
    } = this.selectTargetItem;
    this.filterBy = {
      [EDimensionKey.namespace]: [namespace],
      ...(workload ? { [EDimensionKey.workload]: [workload] } : {}),
      ...(pod ? { [EDimensionKey.pod]: [pod] } : {}),
    };
    this.cluster = cluster;
    this.apmResourceType = resourceType;
    this.groupInstance.initGroupFilter();
    if (resourceType === 'pod') {
      this.groupInstance.addGroupFilter(K8sTableColumnKeysEnum.POD, { single: true });
    } else if (resourceType === 'workload') {
      this.groupInstance.addGroupFilter(K8sTableColumnKeysEnum.WORKLOAD, { single: true });
      this.groupInstance.addGroupFilter(K8sTableColumnKeysEnum.POD);
    }
    this.isUserManualSwitch = !!oldValue;
  }

  handleTargetListToggle(toggle: boolean) {
    this.targetListToggle = toggle;
  }

  // apm容器首版：只需要缓存targetList选中的那一项，暂时不需要过滤条件和聚合维度等其他参数
  getRouteParams(query: Record<string, string | string[]> = {}) {
    const { target = '' } = query;
    const res = this.targetList.find(item => item.cacheId === target) || '';
    if (!target || !res) {
      this.selectTarget = this.targetList[0].cacheId;
    } else {
      this.selectTarget = res.cacheId;
    }
    this.initGroupBy();
    this.initFilterBy();
  }

  setRouteParams(otherQuery = {}) {
    const apmK8sParams = {
      selectTarget: {
        target: this.selectTarget,
      },
      ...otherQuery,
    };
    this.handleApmK8sNewEventChange('apmK8sNewCustomRouteQueryChange', apmK8sParams);
    return;
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

  renderTargetListSelect() {
    return (
      <bk-select
        class='target-list-select'
        clearable={false}
        search-placeholder={this.$t('请输入 关键字')}
        value={this.selectTarget}
        searchable
        onChange={this.handleTargetListChange}
        onToggle={this.handleTargetListToggle}
      >
        <div
          class='target-list-trigger'
          slot='trigger'
        >
          <span
            class='target-list-name'
            v-bk-overflow-tips
          >
            {this.$t('workload')}: {this.selectTargetText}
          </span>
          <span class={`icon-monitor icon-mc-arrow-down ${this.targetListToggle ? 'expand' : ''}`} />
        </div>
        {this.targetList.map(target => (
          <bk-option
            id={target.cacheId}
            key={target.cacheId}
            name={`${target.workload || target.pod}（集群:${target.bcs_cluster_id}）, namespace:${target.namespace}`}
          />
        ))}
      </bk-select>
    );
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
      <div class={['monitor-k8s-new', this.scene]}>
        {[
          <div
            key='monitor-k8s-new-header'
            class='monitor-k8s-new-header ____monitor-k8s-new-header'
          >
            {this.renderTargetListSelect()}
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
            <div class='monitor-k8s-btn'>
              <bk-button
                ext-cls='monitor-k8s-btn-text'
                title='primary'
                text
                onClick={this.handleGoToK8sPage}
              >
                {this.$tc('容器监控')}
                <i class='icon-monitor icon-fenxiang' />
              </bk-button>
            </div>
          </div>,
          <div
            key='monitor-k8s-new-content'
            style={{
              height: `calc(100% - ${this.headerHeight}px)`,
            }}
            class='monitor-k8s-new-content'
          >
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
        ]}
      </div>
    );
  }
}
