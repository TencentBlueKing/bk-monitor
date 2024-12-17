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
import { Component, Mixins, ProvideReactive, Watch } from 'vue-property-decorator';

import { listBcsCluster, scenarioMetricList } from 'monitor-api/modules/k8s';
import { random } from 'monitor-common/utils';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import UserConfigMixin from '../../mixins/userStoreConfig';
import FilterByCondition from './components/filter-by-condition/filter-by-condition';
import GroupByCondition, { type IGroupByChangeEvent } from './components/group-by-condition/group-by-condition';
import K8SCharts from './components/k8s-charts/k8s-charts';
import K8sDimensionList from './components/k8s-left-panel/k8s-dimension-list';
import K8sLeftPanel from './components/k8s-left-panel/k8s-left-panel';
import K8sMetricList from './components/k8s-left-panel/k8s-metric-list';
import K8sNavBar from './components/k8s-nav-bar/K8s-nav-bar';
import K8sTableNew, {
  type K8sTableColumnResourceKey,
  type K8sTableFilterByEvent,
  type K8sTableGroupByEvent,
} from './components/k8s-table-new/k8s-table-new';
import { type K8sGroupDimension, K8sPerformanceGroupDimension, sceneDimensionMap } from './k8s-dimension';
import {
  type IK8SMetricItem,
  type ICommonParams,
  K8sNewTabEnum,
  K8sTableColumnKeysEnum,
  SceneEnum,
} from './typings/k8s-new';

import type { TimeRangeType } from '../../components/time-range/time-range';

import './monitor-k8s-new.scss';

const HIDE_METRICS_KEY = 'monitor_hide_metrics';
const tabList = [
  {
    label: '列表',
    id: K8sNewTabEnum.LIST,
    icon: 'icon-mc-list',
  },
  {
    label: '图表',
    id: K8sNewTabEnum.CHART,
    icon: 'icon-mc-two-column',
  },
  {
    label: '数据明细',
    id: K8sNewTabEnum.DETAIL,
    icon: 'icon-mingxi',
  },
];
@Component
export default class MonitorK8sNew extends Mixins(UserConfigMixin) {
  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 刷新间隔
  @ProvideReactive('refleshInterval') refreshInterval = -1;
  // 是否立即刷新
  @ProvideReactive('refleshImmediate') refreshImmediate = '';

  // 场景
  scene: SceneEnum = SceneEnum.Performance;
  // 集群
  cluster = '';
  // 集群列表
  clusterList = [];
  // 集群加载状态
  clusterLoading = true;
  // 当前 tab
  activeTab = K8sNewTabEnum.LIST;
  filterBy: Record<string, string[]> = {};
  // Group By 选择器的值
  groupInstance: K8sGroupDimension = new K8sPerformanceGroupDimension();

  // 是否展示取消下钻
  showCancelDrill = false;
  groupList = [];

  cacheFilterBy: Record<string, string[]> = {};
  cacheGroupBy = [];

  /** 指标列表 */
  metricList: IK8SMetricItem[] = [];
  // 指标隐藏项
  hideMetrics: string[] = [];

  metricLoading = true;
  /** 自动刷新定时器 */
  timer = null;
  /** 各维度数据总和 */
  dimensionTotal = {};

  get isChart() {
    return this.activeTab === K8sNewTabEnum.CHART;
  }

  get groupFilters() {
    return this.groupInstance.groupFilters;
  }

  /** 当前场景下的维度列表 */
  get sceneDimensionList() {
    return sceneDimensionMap[this.scene] || [];
  }

  /** 公共参数 */
  get commonParams(): ICommonParams {
    return {
      scenario: this.scene,
      bcs_cluster_id: this.cluster,
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    };
  }

  @ProvideReactive('formatTimeRange')
  get formatTimeRange() {
    return handleTransformToTimestamp(this.timeRange);
  }

  get filterCommonParams() {
    return {
      ...this.commonParams,
      resource_type: this.groupInstance.groupFilters.at(-1),
      filter_dict: this.filterBy,
      with_history: false,
    };
  }

  setGroupFilters(item: { groupId: K8sTableColumnResourceKey; checked: boolean }) {
    if (item.checked) {
      this.groupInstance?.addGroupFilter(item.groupId);
      return;
    }
    this.groupInstance.deleteGroupFilter(item.groupId);
  }

  @Watch('groupFilters')
  watchGroupFiltersChange() {
    this.setRouteParams();
  }

  @Watch('filterBy')
  watchFilterByChange() {
    this.setRouteParams();
  }

  created() {
    this.getRouteParams();
    this.getClusterList();
    this.getScenarioMetricList();
    this.initFilterBy();
    this.handleGetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`).then((res: string[]) => {
      this.hideMetrics = res || [];
    });
    this.setRouteParams();
  }

  /** 初始化filterBy结构 */
  initFilterBy() {
    this.filterBy = this.sceneDimensionList.reduce((pre, cur) => {
      pre[cur] = [];
      return pre;
    }, {});
  }

  async getClusterList() {
    this.clusterLoading = true;
    this.clusterList = await listBcsCluster().catch(() => []);
    this.clusterLoading = false;
    if (this.clusterList.length) {
      this.cluster = this.clusterList[0].id;
    }
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

  handleSceneChange(value) {
    this.scene = value;
    this.initFilterBy();
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

  /** 取消下钻 */
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
      this.setGroupFilters({ groupId, checked: isSelect });
    } else {
      this.groupInstance.deleteGroupFilterForce(groupId);
    }
  }

  /**
   * 下钻功能
   * @param filterById 下钻数据Id
   * @param filterByDimension  下钻数据所在维度
   * @param drillDownDimension 下钻维度
   */
  handleDrillDown(filterById: string, filterByDimension: string, drillDownDimension: string) {
    this.groupByChange(drillDownDimension, true);
    this.filterByChange(filterById, filterByDimension, true);
  }

  /**
   * 修改filterBy
   * @param id 数据Id
   * @param dimensionId 维度Id
   * @param isSelect 是否选中
   */
  filterByChange(id: string, dimensionId: string, isSelect: boolean) {
    this.showCancelDrill = false;
    if (isSelect) {
      this.filterBy[dimensionId].push(id);
    } else {
      this.filterBy[dimensionId] = this.filterBy[dimensionId].filter(item => item !== id);
    }
    this.filterBy = { ...this.filterBy };
  }

  /** 清除某个维度的filterBy */
  clearFilterBy(dimensionId: string) {
    this.filterBy[dimensionId] = [];
    this.filterBy = { ...this.filterBy };
  }

  /** 隐藏指标项变化 */
  metricHiddenChange(hideMetrics: string[]) {
    this.hideMetrics = hideMetrics;
    this.handleSetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`, JSON.stringify(hideMetrics));
  }

  handleClusterChange(cluster: string) {
    this.cluster = cluster;
    this.initFilterBy();
    this.groupInstance.setGroupFilters([K8sTableColumnKeysEnum.NAMESPACE]);
    this.showCancelDrill = false;
    this.getScenarioMetricList();
  }

  /**
   * @description tab切换回调
   * @param {K8sNewTabEnum} v
   */
  async handleTabChange(v: K8sNewTabEnum) {
    this.activeTab = v;
  }

  handleGroupChecked(item: IGroupByChangeEvent) {
    this.showCancelDrill = false;
    this.setGroupFilters({ groupId: item.id, checked: item.checked });
  }

  /**
   * @description 表格 添加筛选/移除筛选 icon点击回调
   * @param {K8sTableFilterByEvent} item
   */
  handleFilterChange(item: K8sTableFilterByEvent) {
    this.filterByChange(item);
  }

  /**
   * @description 表格下钻点击回调
   * @param {K8sTableGroupByEvent} item
   */
  handleTableGroupChange(item: K8sTableGroupByEvent) {
    this.showCancelDrill = true;
    this.cacheGroupBy = this.groupInstance.groupFilters;
    this.setGroupFilters(item);
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
  }

  getRouteParams() {
    const {
      from = 'now-1h',
      to = 'now',
      refreshInterval = '-1',
      filterBy = '[]',
      groupBy = '[]',
      cluster = '',
      scene = SceneEnum.Performance,
    } = this.$route.query || {};
    this.timeRange = [from as string, to as string];
    this.refreshInterval = Number(refreshInterval);
    this.filterBy = JSON.parse(filterBy as string);
    this.cluster = cluster as string;
    this.scene = scene as SceneEnum;
    if (JSON.parse(groupBy as string).length) {
      this.groupInstance.setGroupFilters(JSON.parse(groupBy as string));
    }
  }

  setRouteParams() {
    const query = {
      sceneId: 'kubernetes',
      from: this.timeRange[0],
      to: this.timeRange[1],
      refreshInterval: String(this.refreshInterval),
      filterBy: JSON.stringify(this.filterBy),
      groupBy: JSON.stringify(this.groupInstance.groupFilters),
      cluster: this.cluster,
      scene: this.scene,
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
            filterCommonParams={this.filterCommonParams}
            groupBy={this.groupFilters}
            hideMetrics={this.hideMetrics}
            metricList={this.metricList}
          />
        );
      default:
        return (
          <K8sTableNew
            activeTab={this.activeTab}
            clusterId={this.cluster}
            filterBy={this.filterBy}
            groupInstance={this.groupInstance}
            scene={this.scene}
            onClearSearch={this.handleTableClearSearch}
            onFilterChange={this.handleFilterChange}
            onGroupChange={this.handleTableGroupChange}
          />
        );
    }
  }
  render() {
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
                  <i class='icon-monitor icon-back-left' />
                </div>
                <span class='text'>{this.$t('取消下钻')}</span>
              </div>
            )}
          </K8sNavBar>
        </div>
        <div class='monitor-k8s-new-header'>
          {this.clusterLoading ? (
            <div class='skeleton-element cluster-skeleton' />
          ) : (
            <bk-select
              class='cluster-select'
              clearable={false}
              value={this.cluster}
              onChange={this.handleClusterChange}
            >
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
              <div class='filter-by-title'>Filter by</div>
              <div class='filter-by-content'>
                <FilterByCondition
                  bcsClusterId={this.cluster}
                  filterBy={this.filterBy}
                  scene={this.scene}
                  timeRange={this.timeRange}
                  onChange={this.handleFilterByChange}
                />
              </div>
            </div>
            <div class='filter-by-wrap __group-by__'>
              <GroupByCondition
                dimensionOptions={this.groupList}
                groupInstance={this.groupInstance}
                title='Group by'
                onChange={this.handleGroupChecked}
              />
            </div>
          </div>
        </div>

        <div class='monitor-k8s-new-content'>
          <div class='content-left'>
            <K8sLeftPanel>
              <K8sDimensionList
                commonParams={this.commonParams}
                filterBy={this.filterBy}
                groupBy={this.groupFilters}
                onClearFilterBy={this.clearFilterBy}
                onDimensionTotal={this.dimensionTotalChange}
                onDrillDown={this.handleDrillDown}
                onFilterByChange={this.filterByChange}
                onGroupByChange={this.groupByChange}
              />
              <K8sMetricList
                hideMetrics={this.hideMetrics}
                loading={this.metricLoading}
                metricList={this.metricList}
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
