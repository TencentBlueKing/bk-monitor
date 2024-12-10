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
import { Component, Mixins, ProvideReactive, Ref } from 'vue-property-decorator';

import { random } from 'monitor-common/utils';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import UserConfigMixin from '../../mixins/userStoreConfig';
import FilterByCondition from './components/filter-by-condition/filter-by-condition';
import GroupByCondition, { type IGroupByChangeEvent } from './components/group-by-condition/group-by-condition';
import K8SCharts from './components/k8s-charts/k8s-charts';
import K8sDetailSlider from './components/k8s-detail-slider/k8s-detail-slider';
import K8sDimensionList from './components/k8s-left-panel/k8s-dimension-list';
import K8sLeftPanel from './components/k8s-left-panel/k8s-left-panel';
import K8sMetricList from './components/k8s-left-panel/k8s-metric-list';
import K8sNavBar from './components/k8s-nav-bar/K8s-nav-bar';
import K8sTableNew, {
  type K8sTableClickEvent,
  type K8sTableColumn,
  type K8sTableFilterByEvent,
  type K8sTableGroupByEvent,
  type K8sTableRow,
  type K8sTableSort,
} from './components/k8s-table-new/k8s-table-new';
import { getK8sTableAsyncDataMock, getK8sTableDataMock } from './components/k8s-table-new/utils';
import { type K8sGroupDimension, K8sPerformanceGroupDimension } from './k8s-dimension';
import { K8sNewTabEnum, K8sTableColumnKeysEnum, type SceneType } from './typings/k8s-new';

import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFilterByItem } from './components/filter-by-condition/utils';

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
  @Ref() k8sTableRef: InstanceType<typeof K8sTableNew>;
  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 刷新间隔
  @ProvideReactive('refleshInterval') refreshInterval = -1;
  // 是否立即刷新
  @ProvideReactive('refleshImmediate') refreshImmediate = '';
  tableConfig = {
    loading: false,
    scrollLoading: false,
    /** 当切换 tab 时进行刷新以达到清楚table中 sort 的状态 */
    refreshKey: random(10),
    pagination: {
      page: 1,
      pageSize: 20,
    },
    sortContainer: {
      prop: null,
      sort: null,
    },
  };
  sliderShow = false;
  // 场景
  scene: SceneType = 'performance';
  // 集群
  cluster = '';
  // 集群列表
  clusterList = [];
  // 集群加载状态
  clusterLoading = true;
  // 当前 tab
  activeTab = K8sNewTabEnum.LIST;
  filterBy: IFilterByItem[] = [];
  // Group By 选择器的值
  groupInstance: K8sGroupDimension = new K8sPerformanceGroupDimension();
  // 指标隐藏项
  hideMetrics = [];
  // 表格数据
  k8sTableData: any = {
    count: 0,
    items: [],
  };
  // table 点击选中数据项
  k8sTableChooseItem: { row: K8sTableRow; column: K8sTableColumn } = {
    row: null,
    column: null,
  };
  // 是否展示取消下钻
  showCancelDrill = false;
  groupList = [
    {
      name: 'namespace',
      id: 'namespace',
      count: 4,
      children: [
        {
          id: '监控测试集群(BCS-K8S-26286)',
          name: '监控测试集群(BCS-K8S-26286)',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)__222',
          name: '监控测试集群(BCS-K8S-26286)__222',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_3',
          name: '监控测试集群(BCS-K8S-26286)_3',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_4',
          name: '监控测试集群(BCS-K8S-26286)_4',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_5',
          name: '监控测试集群(BCS-K8S-26286)_5',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_6',
          name: '监控测试集群(BCS-K8S-26286)_6',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_7',
          name: '监控测试集群(BCS-K8S-26286)_7',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_8',
          name: '监控测试集群(BCS-K8S-26286)_8',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_9',
          name: '监控测试集群(BCS-K8S-26286)_9',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_10',
          name: '监控测试集群(BCS-K8S-26286)_10',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_11',
          name: '监控测试集群(BCS-K8S-26286)_11',
        },
      ],
    },
    {
      name: 'workload',
      id: 'workload',
      count: 4,
      children: [
        {
          name: 'Deployments',
          id: 'Deployments',
          count: 1,
          children: [
            {
              id: 'monitor-test1',
              name: 'monitor-test1',
            },
          ],
        },
        {
          name: 'StatefulSets',
          count: 1,
          id: 'StatefulSets',
          children: [
            {
              id: 'monitor-test2',
              name: 'monitor-test2',
            },
          ],
        },
      ],
    },
    {
      name: 'pod',
      id: 'pod',
      count: 5,
      children: [
        {
          id: 'bkbase-puller-datanode-inland…',
          name: 'bkbase-puller-datanode-inland…',
        },
        {
          id: 'sql-f76a1c37c9ae48f1a9daf0843534535345',
          name: 'sql-f76a1c37c9ae48f1a9daf081213123',
        },
        {
          id: 'pf-d1fba8d425e24f268bbed3b13123123',
          name: 'pf-d1fba8d425e24f268bbed3b13123123',
        },
        {
          id: 'pf-d1fba8d425e24f268bbed3b56456465466111',
          name: 'pf-d1fba8d425e24f268bbed3b56456465466111',
        },
        {
          id: 'pf-d1fba8d425e24f268bbed3b89789111111dd',
          name: 'pf-d1fba8d425e24f268bbed3b89789111111dd',
        },
      ],
    },
  ];

  cacheFilterBy: IFilterByItem[] = [];
  cacheGroupBy = [];

  metricList = [];

  metricLoading = true;

  get isChart() {
    return this.activeTab === K8sNewTabEnum.CHART;
  }

  get groupFilters() {
    return this.groupInstance.groupFilters;
  }

  setGroupFilters(item: { groupId: K8sTableColumnKeysEnum; checked: boolean }) {
    if (item.checked) {
      this.groupInstance?.addGroupFilter(item.groupId);
      return;
    }
    this.groupInstance.deleteGroupFilter(item.groupId);
  }

  setK8sTableChooseItem(item: K8sTableClickEvent) {
    this.$set(this.k8sTableChooseItem, 'column', item?.column || null);
    this.$set(this.k8sTableChooseItem, 'row', item?.row || null);
  }

  created() {
    this.getK8sList();
    this.getClusterList();
    this.getScenarioMetricList();
    this.handleGetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`).then((res: string[]) => {
      this.hideMetrics = res || [];
    });
  }

  /**
   * @description 重新渲染表格组件（主要是为了处理 table column 的 sort 状态）
   */
  refreshTable() {
    this.tableConfig.refreshKey = random(10);
  }

  async getClusterList() {
    this.clusterLoading = true;
    this.clusterList = await new Promise(resolve => {
      setTimeout(() => {
        resolve([
          { id: 'BCS-K8S-00000', name: '蓝鲸7.0(BCS-K8S-00000)' },
          { id: 'BCS-K8S-00001', name: '蓝鲸8.0(BCS-K8S-00000)' },
        ]);
      }, 1000);
    });
    this.clusterLoading = false;
    if (this.clusterList.length) {
      this.cluster = this.clusterList[0].id;
    }
  }

  /**
   * @description 获取k8s列表
   * @param {boolean} config.needRefresh 是否需要刷新表格状态
   * @param {boolean} config.needIncrement 是否需要增量加载（table 触底加载）
   */
  getK8sList(config: { needRefresh?: boolean; needIncrement?: boolean } = {}) {
    const loadingKey = config.needIncrement ? 'scrollLoading' : 'loading';
    this.tableConfig[loadingKey] = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    getK8sTableDataMock(Math.floor(Math.random() * 101))
      .then(res => {
        const asyncColumns: K8sTableColumn[] = (this.k8sTableRef?.tableColumnsConfig?.columns || []).filter(col =>
          // @ts-ignore
          Object.hasOwn(col, 'asyncable')
        );
        for (const asyncColumn of asyncColumns) {
          asyncColumn.asyncable = true;
        }

        this.$set(this, 'k8sTableData', res);
        this.loadAsyncData(startTime, endTime, asyncColumns);
      })
      .finally(() => {
        if (config.needRefresh) {
          this.refreshTable();
        }
        this.tableConfig[loadingKey] = false;
      });
  }

  /**
   * @description 获取场景指标列表
   */
  async getScenarioMetricList() {
    function mock(params) {
      console.log(params);
      return new Promise(resolve => {
        setTimeout(() => {
          resolve([
            {
              id: 'CPU',
              name: 'CPU',
              children: [
                { id: 'container_cpu_usage_seconds_total', name: 'CPU使用量' },
                { id: 'kube_pod_cpu_requests_ratio', name: 'CPU request使用率' },
                { id: 'kube_pod_cpu_limits_ratio', name: 'CPU limit使用率' },
              ],
            },
            {
              id: 'memory',
              name: '内存',
              children: [
                { id: 'container_memory_rss', name: '内存使用量(rss)' },
                { id: 'kube_pod_memory_requests_ratio', name: '内存 request使用率' },
                { id: 'kube_pod_memory_limits_ratio', name: '内存 limit使用率' },
              ],
            },
          ]);
        }, 1000);
      });
    }
    this.metricLoading = true;
    const data = await mock({ scenario: this.scene });
    this.metricLoading = false;
    this.metricList = data.map(item => ({
      ...item,
      count: item.children.length,
    }));
  }

  /**
   * @description 异步加载获取k8s列表（cpu、内存使用率）的数据
   */
  loadAsyncData(startTime: number, endTime: number, asyncColumns: K8sTableColumn[]) {
    const pods = (this.k8sTableData.items || []).map(v => v?.[K8sTableColumnKeysEnum.POD]);
    for (const field of asyncColumns) {
      getK8sTableAsyncDataMock({
        start_time: startTime,
        end_time: endTime,
        column: field.id,
        pods: pods,
      }).then(podData => {
        this.mapAsyncData(podData, field.id, asyncColumns);
      });
    }
  }

  /**
   * @description 将异步数据数组结构为 key-value 的 map
   * @param podData 异步数据
   * @param field 当前column的key
   * @param asyncColumns 需要异步加载的column字段对象
   */
  mapAsyncData(podData, field: K8sTableColumnKeysEnum, asyncColumns: K8sTableColumn[]) {
    const dataMap = {};
    if (podData?.length) {
      for (const podItem of podData) {
        if (podItem?.[K8sTableColumnKeysEnum.POD]) {
          const columnItem = asyncColumns.find(item => item.id === field);
          podItem[field].valueTitle = columnItem?.name || null;
          dataMap[String(podItem?.[K8sTableColumnKeysEnum.POD])] = podItem[field];
        }
      }
    }
    this.renderTableBatchByBatch(field, dataMap || {}, asyncColumns);
  }

  /**
   *
   * @description: 按需渲染表格数据
   * @param field 字段名
   * @param dataMap 数据map
   * @param asyncColumns 异步获取的column字段对象
   */
  renderTableBatchByBatch(field: string, dataMap: Record<string, any>, asyncColumns: K8sTableColumn[]) {
    const setData = (currentIndex = 0) => {
      let needBreak = false;
      if (currentIndex <= this.k8sTableData.items.length && this.k8sTableData.items.length) {
        const endIndex = Math.min(currentIndex + 2, this.k8sTableData.length);
        for (let i = currentIndex; i < endIndex; i++) {
          const item = this.k8sTableData.items[i];
          item[field] = dataMap[String(item?.[K8sTableColumnKeysEnum.POD] || '')] || null;
          needBreak = i === this.k8sTableData.items.length - 1;
        }
        if (!needBreak) {
          window.requestIdleCallback(() => {
            window.requestAnimationFrame(() => setData(endIndex));
          });
        } else {
          const item = asyncColumns.find(col => col.id === field);
          item.asyncable = false;
        }
      }
    };
    const item = asyncColumns.find(col => col.id === field);
    item.asyncable = false;
    setData(0);
  }

  handleSceneChange(value) {
    this.scene = value;
  }

  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.timeRange = timeRange;
  }

  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
    // updateTimezone(timezone);
  }

  /** 取消下钻 */
  handleCancelDrillDown() {
    this.filterBy = this.cacheFilterBy;
    this.groupInstance.setGroupFilters(this.cacheGroupBy);
    this.showCancelDrill = false;
  }

  /** 左侧面板group状态切换 */
  groupByChange({ groupId, isSelect }) {
    this.showCancelDrill = false;
    this.setGroupFilters({ groupId, checked: isSelect });
  }

  /** 左侧面板下钻功能 */
  handleDrillDown({ filterBy, groupId }) {
    this.cacheFilterBy = JSON.parse(JSON.stringify(this.filterBy));
    this.cacheGroupBy = [...this.groupFilters];
    this.groupByChange({ groupId, isSelect: true });
    this.filterByChange({ ids: filterBy.value, groupId: filterBy.key });
    this.showCancelDrill = true;
  }

  /* 左侧面板检索功能 */
  filterByChange({ ids, groupId }) {
    this.showCancelDrill = false;
    const target = this.filterBy.find(item => item.key === groupId);
    if (target) {
      target.value = ids;
      this.filterBy = [...this.filterBy];
    } else {
      this.filterBy.push({ key: groupId, value: ids, method: 'eq' });
    }
  }

  /** 隐藏指标项变化 */
  metricHiddenChange(hideMetrics: string[]) {
    this.hideMetrics = hideMetrics;
    this.handleSetUserConfig(`${HIDE_METRICS_KEY}_${this.scene}`, JSON.stringify(hideMetrics));
  }

  handleClusterChange(cluster: string) {
    this.cluster = cluster;
    this.filterBy = [];
    this.groupInstance.setGroupFilters([K8sTableColumnKeysEnum.NAMESPACE]);
    this.showCancelDrill = false;
  }

  /**
   * @description tab切换回调
   * @param {K8sNewTabEnum} v
   */
  async handleTabChange(v: K8sNewTabEnum) {
    this.activeTab = v;
    if (v !== K8sNewTabEnum.CHART) {
      // 重新渲染，从而刷新 table sort 状态
      this.getK8sList({ needRefresh: true });
    }
  }

  handleGroupChecked(item: IGroupByChangeEvent) {
    this.setGroupFilters({ groupId: item.id, checked: item.checked });
  }

  /**
   * @description 表格排序
   * @param {K8sTableSort} sort
   */
  handleTableSortChange(sort: K8sTableSort) {
    this.tableConfig.sortContainer = sort;
    this.getK8sList();
  }

  /**
   * @description 表格下钻点击回调
   * @param {K8sTableGroupByEvent} item
   */
  handleTableGroupChange(item: K8sTableGroupByEvent) {
    this.handleGroupChecked(item);
  }

  /**
   * @description 表格 添加筛选/移除筛选 icon点击回调
   * @param {K8sTableFilterByEvent} item
   */
  handleFilterChange(item: K8sTableFilterByEvent) {
    const { column, ids } = item;
    this.filterByChange({ groupId: column.id, ids });
  }

  /**
   * @description 表格文本点击回调
   * @param {K8sTableClickEvent} item
   */
  handleTextClick(item: K8sTableClickEvent) {
    this.setK8sTableChooseItem(item);
    this.handleSliderChange(true);
  }

  /**
   * @description 表格滚动到底部回调
   */
  handleTableScrollEnd() {
    console.log('table scroll end callback');
  }

  handleTableClearSearch() {
    console.log('table clear search callback');
  }

  /**
   * @description 抽屉页显示隐藏切换
   * @param v {boolean}
   */
  handleSliderChange(v: boolean) {
    this.sliderShow = v;
    if (!v) {
      this.setK8sTableChooseItem(null);
    }
  }

  /**
   * @description 抽屉页 下钻 按钮点击回调
   */
  handleSliderGroupChange(item: K8sTableGroupByEvent) {
    this.handleTableGroupChange(item);
    this.handleSliderChange(false);
  }

  /**
   * @description 抽屉页 添加筛选/移除筛选 按钮点击回调
   * @param {K8sTableFilterByEvent} item
   */
  handleSliderFilterChange(item: K8sTableFilterByEvent) {
    this.handleFilterChange(item);
    this.handleSliderChange(false);
  }

  handleFilterByChange(v: IFilterByItem[]) {
    console.log(v);
    this.filterBy = v;
  }

  tabContentRender() {
    switch (this.activeTab) {
      case K8sNewTabEnum.CHART:
        return <K8SCharts />;
      default:
        return (
          <K8sTableNew
            ref='k8sTableRef'
            activeTab={this.activeTab}
            filterBy={this.filterBy}
            groupFilters={this.groupFilters}
            loading={this.tableConfig.loading}
            refreshKey={this.tableConfig.refreshKey}
            scrollLoading={this.tableConfig.scrollLoading}
            tableData={this.k8sTableData.items}
            onClearSearch={this.handleTableClearSearch}
            onFilterChange={this.handleFilterChange}
            onGroupChange={this.handleTableGroupChange}
            onScrollEnd={this.handleTableScrollEnd}
            onSortChange={this.handleTableSortChange}
            onTextClick={this.handleTextClick}
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
                  filterBy={this.filterBy}
                  groupList={this.groupList}
                  scene={this.scene}
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
                filterBy={this.filterBy}
                groupBy={this.groupFilters}
                scene={this.scene}
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
        <K8sDetailSlider
          activeItem={this.k8sTableChooseItem}
          filterBy={this.filterBy}
          groupFilters={this.groupFilters}
          isShow={this.sliderShow}
          onFilterChange={this.handleSliderFilterChange}
          onGroupChange={this.handleSliderGroupChange}
          onShowChange={this.handleSliderChange}
        />
      </div>
    );
  }
}
