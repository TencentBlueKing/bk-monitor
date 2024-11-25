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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import FilterByCondition from './components/filter-by-condition/filter-by-condition';
import { GROUP_OPTIONS } from './components/filter-by-condition/utils';
import GroupByCondition, {
  type IGroupOption,
  type IGroupByChangeEvent,
} from './components/group-by-condition/group-by-condition';
import K8sLeftPanel from './components/k8s-left-panel/k8s-left-panel';
import K8sNavBar from './components/k8s-nav-bar/K8s-nav-bar';
import K8sTableNew from './components/k8s-table-new/k8s-table-new';
import { getK8sTableDataMock } from './components/k8s-table-new/utils';
import { K8sNewTabEnum } from './typings/k8s-new';

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
    icon: 'icon-mc-detail',
  },
];
@Component
export default class MonitorK8sNew extends tsc<object> {
  // 场景
  scene = 'performance';
  // 时间范围
  timeRange: TimeRangeType = [...DEFAULT_TIME_RANGE];
  // 时区
  timezone = getDefaultTimezone();
  // 刷新间隔
  refreshInterval = -1;
  // 立即刷新
  immediateRefresh = random(8);
  // 集群
  cluster = '';
  // 集群列表
  clusterList = [];
  // 当前 tab
  activeTab = K8sNewTabEnum.LIST;
  filterBy = [];
  // Group By 选择器的值
  groupFilters: Array<number | string> = [];
  // Group By 选择器选项
  groupOptions = [...GROUP_OPTIONS];
  // 指标隐藏项
  hideMetrics = JSON.parse(localStorage.getItem(HIDE_METRICS_KEY) || '[]');
  // 表格数据
  k8sTableData: any[] = [];
  // 是否展示取消下钻
  showCancelDrill = false;

  loading = false;

  groupList = [
    {
      title: 'namespace',
      id: 'namespace',
      count: 4,
      children: [
        {
          id: '监控测试集群(BCS-K8S-26286)',
          title: '监控测试集群(BCS-K8S-26286)',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)__222',
          title: '监控测试集群(BCS-K8S-26286)__222',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_3',
          title: '监控测试集群(BCS-K8S-26286)_3',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_4',
          title: '监控测试集群(BCS-K8S-26286)_4',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_5',
          title: '监控测试集群(BCS-K8S-26286)_5',
        },
        {
          id: '监控测试集群(BCS-K8S-26286)_6',
          title: '监控测试集群(BCS-K8S-26286)_6',
        },
      ],
    },
    {
      title: 'workload',
      id: 'workload',
      count: 4,
      children: [
        {
          title: 'Deployments',
          id: 'Deployments',
          count: 1,
          children: [
            {
              id: 'monitor-test1',
              title: 'monitor-test1',
            },
          ],
        },
        {
          title: 'StatefulSets',
          count: 1,
          id: 'StatefulSets',
          children: [
            {
              id: 'monitor-test2',
              title: 'monitor-test2',
            },
          ],
        },
      ],
    },
    {
      title: 'pod',
      id: 'pod',
      count: 5,
      children: [
        {
          id: 'bkbase-puller-datanode-inland…',
          title: 'bkbase-puller-datanode-inland…',
        },
        {
          id: 'sql-f76a1c37c9ae48f1a9daf0843534535345',
          title: 'sql-f76a1c37c9ae48f1a9daf081213123',
        },
        {
          id: 'pf-d1fba8d425e24f268bbed3b13123123',
          title: 'pf-d1fba8d425e24f268bbed3b13123123',
        },
        {
          id: 'pf-d1fba8d425e24f268bbed3b56456465466111',
          title: 'pf-d1fba8d425e24f268bbed3b56456465466111',
        },
        {
          id: 'pf-d1fba8d425e24f268bbed3b89789111111dd',
          title: 'pf-d1fba8d425e24f268bbed3b89789111111dd',
        },
      ],
    },
  ];

  metricList = [
    {
      title: 'CPU',
      id: 'CPU',
      count: 3,
      children: [
        {
          id: 'CPU使用量',
          title: 'CPU使用量',
        },
        {
          id: 'CPU limit 使用率',
          title: 'CPU limit 使用率',
        },
        {
          id: 'CPU request 使用率',
          title: 'CPU request 使用率',
        },
      ],
    },
    {
      title: '内存',
      id: '内存',
      count: 4,
      children: [
        {
          id: '内存使用量(rss)',
          title: '内存使用量(rss)',
        },
      ],
    },
  ];

  get isChart() {
    return this.activeTab === K8sNewTabEnum.CHART;
  }

  created() {
    this.getK8sList();
  }

  /**
   * @description 获取k8s列表
   */
  getK8sList() {
    this.loading = true;
    getK8sTableDataMock(Math.floor(Math.random() * 101))
      .then(res => {
        this.$set(this, 'k8sTableData', res);
      })
      .finally(() => {
        this.loading = false;
      });
  }

  setGroupFilters(filters: Array<number | string>) {
    this.$set(this, 'groupFilters', filters);
  }

  handleImmediateRefresh() {
    this.immediateRefresh = random(8);
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

  /** 左侧面板group状态切换 */
  groupByChange({ groupId, isSelect }) {
    this.groupFilters = this.groupFilters.reduce(
      (pre, cur) => {
        if (cur !== groupId) pre.push(cur);
        return pre;
      },
      isSelect ? [groupId] : []
    );
  }

  /** 左侧面板下钻功能 */
  handleDrillDown({ groupId, ids, drillDownId }) {
    this.groupByChange({ groupId: drillDownId, isSelect: true });
    this.filterByChange({ ids, groupId });
  }

  /* 左侧面板检索功能 */
  filterByChange({ ids, groupId }) {
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
    localStorage.setItem(HIDE_METRICS_KEY, JSON.stringify(hideMetrics));
  }

  handleClusterChange(cluster: string) {
    this.cluster = cluster;
  }

  setGroupOption<T extends keyof IGroupOption>(option: IGroupOption, key: T, value: IGroupOption[T]) {
    this.$set(option, key, value);
  }

  async handleTabChange(v: K8sNewTabEnum) {
    this.activeTab = v;
    this.getK8sList();
  }

  handleGroupChecked(item: IGroupByChangeEvent) {
    this.setGroupFilters([...item.ids]);
    this.setGroupOption(item.option, 'checked', item.checked);
  }

  tabContentRender() {
    switch (this.activeTab) {
      case K8sNewTabEnum.CHART:
        return <div>chart</div>;
      default:
        return (
          <K8sTableNew
            activeTab={this.activeTab}
            loading={this.loading}
            tableData={this.k8sTableData}
            onColClick={() => {}}
            onFilterChange={() => {}}
            onGroupChange={() => {}}
            onSortChange={() => {}}
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
            onTimeRangeChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
        </div>
        <div class='monitor-k8s-new-header'>
          <bk-select
            class='cluster-select'
            clearable={false}
            value={this.cluster}
            onChange={this.handleClusterChange}
          >
            {this.clusterList.map(cluster => (
              <bk-option
                id={cluster.value}
                key={cluster.value}
                name={cluster.label}
              />
            ))}
          </bk-select>
          <div class='filter-header-wrap'>
            <div class='filter-by-wrap __filter-by__'>
              <div class='filter-by-title'>Filter by</div>
              <div class='filter-by-content'>
                <FilterByCondition />
              </div>
            </div>
            <div class='filter-by-wrap __group-by__'>
              <GroupByCondition
                dimensionOptions={this.groupOptions}
                groupFilters={this.groupFilters}
                title='Group by'
                onChange={this.handleGroupChecked}
              />
            </div>
          </div>
        </div>

        <div class='monitor-k8s-new-content'>
          <div class='content-left'>
            <K8sLeftPanel
              slot='main'
              filterBy={this.filterBy}
              groupBy={this.groupFilters}
              groupList={this.groupList}
              hideMetrics={this.hideMetrics}
              metricList={this.metricList}
              onDrillDown={this.handleDrillDown}
              onFilterByChange={this.filterByChange}
              onGroupByChange={this.groupByChange}
              onMetricHiddenChange={this.metricHiddenChange}
            />
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
            {this.isChart && (
              <div class='content-converge-wrap'>
                <div class='content-converge'>
                  <span>汇聚周期</span>
                </div>
              </div>
            )}
            <div class='content-main-wrap'>{this.tabContentRender()}</div>
          </div>
        </div>
      </div>
    );
  }
}
