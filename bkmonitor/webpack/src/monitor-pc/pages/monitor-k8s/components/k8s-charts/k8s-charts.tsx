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
import { Component, Emit, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listK8sResources } from 'monitor-api/modules/k8s';
import { Debounce } from 'monitor-common/utils';
import FlexDashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';

import { K8S_METHOD_LIST, PANEL_INTERVAL_LIST } from '../../../../constant/constant';
import { K8SPerformanceMetricUnitMap, K8sTableColumnKeysEnum, type IK8SMetricItem } from '../../typings/k8s-new';
import FilterVarSelectSimple from '../filter-var-select/filter-var-select-simple';
import TimeCompareSelect from '../panel-tools/time-compare-select';

import type { K8sTableColumnResourceKey } from '../k8s-table-new/k8s-table-new';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import './k8s-charts.scss';
@Component
export default class K8SCharts extends tsc<{
  metricList: IK8SMetricItem[];
  hideMetrics: string[];
  groupBy: K8sTableColumnResourceKey[];
  filterCommonParams: Record<string, any>;
}> {
  @Prop({ type: Array, default: () => [] }) metricList: IK8SMetricItem[];
  @Prop({ type: Array, default: () => [] }) hideMetrics: string[];
  @Prop({ type: Array, default: () => [] }) groupBy: K8sTableColumnResourceKey[];
  @Prop({ type: Object, default: () => ({}) }) filterCommonParams: Record<string, any>;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  // 汇聚周期
  interval: number | string = 'auto';
  limit = 10;
  // 汇聚方法
  method = K8S_METHOD_LIST[0].id;
  showTimeCompare = false;
  panels: IPanelModel[] = [];
  loading = false;
  resourceMap: Map<K8sTableColumnKeysEnum, string> = new Map();
  resourceLength = 0;
  get groupByField() {
    return this.groupBy.at(-1) || K8sTableColumnKeysEnum.NAMESPACE;
  }
  @Watch('metricList')
  onMetricListChange() {
    this.createPanelList();
  }
  @Watch('hideMetrics')
  onHideMetricListChange() {
    this.createPanelList();
  }
  @Watch('filterCommonParams')
  onFilterCommonParamsChange() {
    this.createPanelList();
  }
  @Provide('onDrillDown')
  @Emit('drillDown')
  handleDrillDown(group: string) {
    return group;
  }

  created() {
    this.updateViewOptions();
    this.createPanelList();
  }
  @Debounce(300)
  async createPanelList() {
    this.loading = true;
    await this.getResourceList();
    const panelList = [];
    for (const item of this.metricList) {
      panelList.push({
        id: item.id,
        title: item.name,
        type: 'row',
        collapsed: true,
        panels: item.children
          ?.filter(panel => !this.hideMetrics.includes(panel.id))
          .map(panel => ({
            id: panel.id,
            type: 'k8s_custom_graph',
            title: panel.name,
            subTitle: '',
            options: {
              legend: {
                displayMode: 'list',
                placement: 'right',
              },
              unit: K8SPerformanceMetricUnitMap[panel.id] || '',
            },
            targets: [
              {
                data: {
                  expression: 'A',
                  query_configs: [
                    {
                      data_source_label: 'prometheus',
                      data_type_label: 'time_series',
                      promql: this.createPerformancePanelPromql(panel.id),
                      interval: '$interval_second',
                      alias: 'a',
                      filter_dict: {},
                    },
                  ],
                },
                datasource: 'time_series',
                data_type: 'time_series',
                api: 'grafana.graphUnifyQuery',
              },
            ],
          })),
      });
    }
    this.panels = panelList;
    this.loading = false;
  }
  createCommonPromqlMethod() {
    return this.resourceLength > 1
      ? `$method by(${this.groupByField === K8sTableColumnKeysEnum.WORKLOAD ? 'workload_kind,workload_name' : this.groupByField})`
      : '$method';
  }
  createCommonPromqlContent() {
    let content = `bcs_cluster_id="${this.filterCommonParams.bcs_cluster_id}"`;
    const namespace = this.resourceMap.get(K8sTableColumnKeysEnum.NAMESPACE);
    if (namespace.length > 2) {
      content += `,namespace=~"${namespace}"`;
    }
    switch (this.groupByField) {
      case K8sTableColumnKeysEnum.CONTAINER:
        content += `,container_name=~"${this.resourceMap.get(K8sTableColumnKeysEnum.CONTAINER)}"`;
        break;
      case K8sTableColumnKeysEnum.POD:
        content += `,pod_name=~"${this.resourceMap.get(K8sTableColumnKeysEnum.POD)}"`;
        break;
      case K8sTableColumnKeysEnum.WORKLOAD:
        content += `,workload_kind=~"${this.resourceMap.get(K8sTableColumnKeysEnum.WORKLOAD_TYPE)}",workload_name=~"${this.resourceMap.get(K8sTableColumnKeysEnum.WORKLOAD)}"`;
        break;
      default:
        content += `,namespace=~"${namespace}"`;
    }
    return content;
  }
  createPerformancePanelPromql(metric: string) {
    switch (metric) {
      case 'container_cpu_usage_seconds_total': // CPU使用量
        return `${this.createCommonPromqlMethod()}(rate(${metric}{${this.createCommonPromqlContent()}}[$interval]))`;
      case 'kube_pod_cpu_limits_ratio': // CPU limit使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD) return '';
        return `${this.createCommonPromqlMethod()}(rate(${'container_cpu_usage_seconds_total'}{${this.createCommonPromqlContent()}}[$interval])) / sum(kube_pod_container_resource_limits_cpu_cores{${this.createCommonPromqlContent()}})`;
      case 'kube_pod_cpu_requests_ratio': // CPU request使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD) return '';
        return `${this.createCommonPromqlMethod()}(rate(${'container_cpu_usage_seconds_total'}{${this.createCommonPromqlContent()}}[$interval])) / sum(kube_pod_container_resource_requests_cpu_cores{${this.createCommonPromqlContent()}})`;
      case 'container_memory_rss': // 内存使用量(rss)
        return `${this.createCommonPromqlMethod()}(${metric}{${this.createCommonPromqlContent()}})`;
      case 'kube_pod_memory_limits_ratio': // 内存limit使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD) return '';
        return `${this.createCommonPromqlMethod()}(${'container_memory_rss'}{${this.createCommonPromqlContent()}}) / ${this.createCommonPromqlMethod()}(kube_pod_container_resource_limits_memory_bytes{${this.createCommonPromqlContent()}})`;
      case 'kube_pod_memory_requests_ratio': // 内存request使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD) return '';
        return `${this.createCommonPromqlMethod()}(${'container_memory_rss'}{${this.createCommonPromqlContent()}}) / ${this.createCommonPromqlMethod()}(kube_pod_container_resource_requests_memory_bytes{${this.createCommonPromqlContent()}})`;
      default:
        return '';
    }
  }
  async getResourceList() {
    const data = await listK8sResources({
      ...this.filterCommonParams,
      with_history: false,
      page_size: 10,
      page: 1,
      page_type: 'scrolling',
    })
      .then(data => {
        if (!data?.items?.length) return [];
        return data.items.slice(0, 10);
      })
      .catch(() => []);
    const resourceMap = new Map<K8sTableColumnKeysEnum, string>([
      [K8sTableColumnKeysEnum.CONTAINER, ''],
      [K8sTableColumnKeysEnum.NAMESPACE, ''],
      [K8sTableColumnKeysEnum.POD, ''],
      [K8sTableColumnKeysEnum.WORKLOAD, ''],
      [K8sTableColumnKeysEnum.WORKLOAD_TYPE, ''],
    ]);
    if (data.length) {
      const container = new Set<string>();
      const pod = new Set<string>();
      const workload = new Set<string>();
      const workloadKind = new Set<string>();
      const namespace = new Set<string>();
      for (const item of data) {
        item.container && container.add(item.container);
        item.pod && pod.add(item.pod);
        if (item.workload) {
          const [workloadType, workloadName] = item.workload.split(':');
          workload.add(workloadName);
          workloadKind.add(workloadType);
        }
        item.namespace && namespace.add(item.namespace);
      }
      resourceMap.set(K8sTableColumnKeysEnum.CONTAINER, Array.from(container).filter(Boolean).join('|'));
      resourceMap.set(K8sTableColumnKeysEnum.POD, Array.from(pod).filter(Boolean).join('|'));
      resourceMap.set(K8sTableColumnKeysEnum.WORKLOAD, Array.from(workload).filter(Boolean).join('|'));
      resourceMap.set(K8sTableColumnKeysEnum.NAMESPACE, Array.from(namespace).filter(Boolean).join('|'));
      resourceMap.set(K8sTableColumnKeysEnum.WORKLOAD_TYPE, Array.from(workloadKind).filter(Boolean).join('|'));
    }
    this.resourceLength = data.length;
    this.resourceMap = resourceMap;
  }
  updateViewOptions() {
    this.viewOptions = {
      interval: this.interval,
      method: this.method,
    };
  }
  // 刷新间隔设置
  handleIntervalChange(v: string) {
    this.interval = v;
    this.updateViewOptions();
  }
  // 汇聚方法改变时触发
  handleMethodChange(v: string) {
    this.method = v;
    this.updateViewOptions();
  }
  /** 时间对比值变更 */
  handleCompareTimeChange(timeList: string[]) {
    this.timeOffset = timeList;
    this.updateViewOptions();
  }

  handleShowTimeCompare(v: boolean) {
    if (!v) {
      this.handleCompareTimeChange([]);
    }
  }
  render() {
    return (
      <div class='k8s-charts'>
        <div class='content-converge-wrap'>
          <div class='content-converge'>
            <FilterVarSelectSimple
              field={'interval'}
              label={this.$t('汇聚周期')}
              options={PANEL_INTERVAL_LIST}
              value={this.interval}
              onChange={this.handleIntervalChange}
            />
            <FilterVarSelectSimple
              class='ml-36'
              field={'method'}
              label={this.$t('汇聚方法')}
              options={K8S_METHOD_LIST}
              value={this.method}
              onChange={this.handleMethodChange}
            />
            <span class='ml-36 mr-8'>{this.$t('时间对比')}</span>
            <bk-switcher
              v-model={this.showTimeCompare}
              size='small'
              theme='primary'
              onChange={this.handleShowTimeCompare}
            />

            {this.showTimeCompare && (
              <TimeCompareSelect
                class='ml-18'
                timeValue={this.timeOffset}
                onTimeChange={this.handleCompareTimeChange}
              />
            )}
          </div>
        </div>
        <div class='k8s-charts-list'>
          <FlexDashboardPanel
            id='k8s-charts'
            column={1}
            panels={this.panels}
          />
        </div>
      </div>
    );
  }
}
