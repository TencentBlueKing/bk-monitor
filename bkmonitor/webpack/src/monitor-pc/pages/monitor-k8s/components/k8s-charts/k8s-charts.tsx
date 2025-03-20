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
import { Component, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listK8sResources } from 'monitor-api/modules/k8s';
import { Debounce } from 'monitor-common/utils';
import FlexDashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';

import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { K8S_METHOD_LIST, PANEL_INTERVAL_LIST } from '../../../../constant/constant';
import { K8SPerformanceMetricUnitMap, K8sTableColumnKeysEnum, type IK8SMetricItem } from '../../typings/k8s-new';
import FilterVarSelectSimple from '../filter-var-select/filter-var-select-simple';
import K8sDetailSlider from '../k8s-detail-slider/k8s-detail-slider';
import TimeCompareSelect from '../panel-tools/time-compare-select';

import type { K8sTableColumnResourceKey, K8sTableGroupByEvent } from '../k8s-table-new/k8s-table-new';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import './k8s-charts.scss';
@Component
export default class K8SCharts extends tsc<
  {
    metricList: IK8SMetricItem[];
    hideMetrics: string[];
    groupBy: K8sTableColumnResourceKey[];
    filterCommonParams: Record<string, any>;
    isDetailMode?: boolean;
    activeMetricId?: string;
    resourceListData?: Record<K8sTableColumnKeysEnum, string>[];
  },
  {
    onDrillDown: (item: K8sTableGroupByEvent, needBack: boolean) => void;
  }
> {
  @Prop({ type: Array, default: () => [] }) metricList: IK8SMetricItem[];
  @Prop({ type: Array, default: () => [] }) hideMetrics: string[];
  @Prop({ type: Array, default: () => [] }) groupBy: K8sTableColumnResourceKey[];
  @Prop({ type: Object, default: () => ({}) }) filterCommonParams: Record<string, string>;
  @Prop({ type: Boolean, default: false }) isDetailMode: boolean;
  @Prop({ type: String, default: '' }) activeMetricId: string;
  @Prop({ type: Array, default: () => [] }) resourceListData: Record<K8sTableColumnKeysEnum, string>[];
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  // 汇聚周期
  interval: number | string = 'auto';
  limitFunc = 'top';
  limit = 10;
  // 汇聚方法
  method = K8S_METHOD_LIST[0].id;
  showTimeCompare = false;
  panels: IPanelModel[] = [];
  loading = false;
  resourceMap: Map<K8sTableColumnKeysEnum, string> = new Map();
  resourceList: Set<Partial<Record<K8sTableColumnKeysEnum, string>>> = new Set();
  sideDetailShow = false;
  sideDetail: Partial<Record<K8sTableColumnKeysEnum, string>> = {};

  get groupByField() {
    return this.groupBy.at(-1) || K8sTableColumnKeysEnum.CLUSTER;
  }
  @Watch('metricList')
  onMetricListChange() {
    this.createPanelList();
  }
  @Watch('hideMetrics')
  onHideMetricListChange() {
    this.createPanelList(false);
  }
  @Watch('filterCommonParams')
  onFilterCommonParamsChange(newVal: Record<string, string>, oldVal: Record<string, string>) {
    if (
      !newVal ||
      !oldVal ||
      Object.entries(newVal.filter_dict).some(([key, value]) => value !== oldVal.filter_dict[key]) ||
      Object.entries(oldVal?.filter_dict || {}).some(([key, value]) => value !== newVal?.filter_dict?.[key]) ||
      Object.entries(newVal).some(
        ([key, value]) => !['start_time', 'end_time', 'filter_dict'].includes(key) && value !== oldVal[key]
      )
    ) {
      this.createPanelList();
    }
  }

  @Watch('activeMetricId')
  onActiveMetricIdChange(id: string) {
    document.querySelector('.dashboard-panel .scroll-in')?.classList.remove('scroll-in');
    if (!id) return;
    const dom = document.getElementById(`${id}__key__`);
    if (!dom) return;
    dom.scrollIntoView?.();
    dom.classList.add('scroll-in');
  }

  @Provide('onDrillDown')
  handleDrillDown(group: string, field: string) {
    let name = field;
    if (this.timeOffset.length) {
      name = field.split('-')?.slice(1).join('-');
    }
    if (this.groupByField === K8sTableColumnKeysEnum.CONTAINER) {
      const [container] = name.split(':');
      this.$emit('drillDown', { id: this.groupByField, dimension: group, filterById: container }, true);
      return;
    }
    this.$emit('drillDown', { id: this.groupByField, dimension: group, filterById: name }, true);
  }

  @Provide('onShowDetail')
  handleShowDetail(field: string) {
    let dimension = field;
    if (this.timeOffset.length) {
      dimension = dimension.split('-')?.slice(1).join('-');
    }
    let item: Partial<Record<K8sTableColumnKeysEnum, string>>;
    if (this.groupByField === K8sTableColumnKeysEnum.CONTAINER) {
      const [container, pod] = dimension.split(':');
      item = Array.from(this.resourceList).find(
        item => item[K8sTableColumnKeysEnum.POD] === pod && item[K8sTableColumnKeysEnum.CONTAINER] === container
      );
    } else {
      item = Array.from(this.resourceList).find(item => item[this.groupByField] === dimension);
    }
    if (!item) return;
    this.sideDetail = {
      ...item,
      cluster: item.cluster || this.filterCommonParams?.bcs_cluster_id,
    };
    this.sideDetailShow = true;
  }

  created() {
    this.updateViewOptions();
    this.createPanelList();
  }
  @Debounce(300)
  async createPanelList(hasLoading = true) {
    if (hasLoading) {
      this.loading = true;
    }
    await this.getResourceList();
    const displayMode = this.isDetailMode ? 'hidden' : 'table';
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
            externalData: {
              groupByField: this.groupByField,
              metrics: [{ metric_id: panel.id }],
            },
            options: {
              legend: {
                displayMode,
              },
              unit: this.method === 'count' ? '' : panel.unit || K8SPerformanceMetricUnitMap[panel.id] || '',
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
            ].concat(
              this.createPerformanceDetailPanel(panel.id).map(item => ({
                data: {
                  expression: 'A',
                  query_configs: [
                    {
                      ...item,
                    },
                  ],
                },
                request_or_limit: true,
                datasource: 'time_series',
                data_type: 'time_series',
                api: 'grafana.graphUnifyQuery',
              }))
            ),
          })),
      });
    }
    this.panels = panelList;
    if (hasLoading) {
      this.loading = false;
    }
    await this.$nextTick();
    this.onActiveMetricIdChange(this.activeMetricId);
  }
  createCommonPromqlMethod() {
    if (this.groupByField === K8sTableColumnKeysEnum.CLUSTER) return '$method by(bcs_cluster_id)';
    if (this.groupByField === K8sTableColumnKeysEnum.CONTAINER) return '$method by(pod_name,container_name)';
    return `$method by(${this.groupByField === K8sTableColumnKeysEnum.WORKLOAD ? 'workload_kind,workload_name' : this.groupByField})`;
    // return this.resourceLength > 1
    //   ? `$method by(${this.groupByField === K8sTableColumnKeysEnum.WORKLOAD ? 'workload_kind,workload_name' : this.groupByField})`
    //   : '$method';
  }
  createCommonPromqlContent(onlyNameSpace = false, needExcludePod = true) {
    let content = `bcs_cluster_id="${this.filterCommonParams.bcs_cluster_id}"`;
    const namespace = this.resourceMap.get(K8sTableColumnKeysEnum.NAMESPACE) || '';
    if (onlyNameSpace) {
      content += `,namespace=~"^(${namespace})$"`;
      return content;
    }
    if (namespace.length > 2) {
      content += `,namespace=~"^(${namespace})$"`;
    }
    switch (this.groupByField) {
      case K8sTableColumnKeysEnum.CONTAINER:
        content += `,pod_name=~"^(${this.resourceMap.get(K8sTableColumnKeysEnum.POD)})$",container_name=~"^(${this.resourceMap.get(K8sTableColumnKeysEnum.CONTAINER)})$"`;
        break;
      case K8sTableColumnKeysEnum.POD:
        content += `,pod_name=~"^(${this.resourceMap.get(K8sTableColumnKeysEnum.POD)})$",${needExcludePod ? 'container_name!="POD"' : ''}`;
        break;
      case K8sTableColumnKeysEnum.WORKLOAD:
        content += `,workload_kind=~"^(${this.resourceMap.get(K8sTableColumnKeysEnum.WORKLOAD_TYPE)})$",workload_name=~"^(${this.resourceMap.get(K8sTableColumnKeysEnum.WORKLOAD)})$"`;
        break;
      default:
        content += '';
    }
    return content;
  }
  createWorkLoadRequestOrLimit(isLimit: boolean, isCPU = true) {
    if (isCPU) {
      if (isLimit)
        return `($method by (workload_kind, workload_name) (count by (workload_kind, workload_name, pod_name, namespace) (rate(container_cpu_system_seconds_total{${this.createCommonPromqlContent()},container_name!="POD"}[1m] $time_shift) ) *
      on(pod_name, namespace)
      group_right(workload_kind, workload_name)
      $method by (pod_name, namespace) (
        kube_pod_container_resource_limits_cpu_cores{${this.createCommonPromqlContent(true)}} $time_shift
      )))`;
      return `($method by (workload_kind, workload_name) (count by (workload_kind, workload_name, pod_name, namespace) (rate(container_cpu_system_seconds_total{${this.createCommonPromqlContent()},container_name!="POD"}[1m] $time_shift)) *
      on(pod_name, namespace)
      group_right(workload_kind, workload_name)
      $method by (pod_name, namespace) (kube_pod_container_resource_requests_cpu_cores{${this.createCommonPromqlContent(true)}} $time_shift)))`;
    }
    if (isLimit)
      return `($method by (workload_kind, workload_name)
        (count by (workload_kind, workload_name, pod_name, namespace) (
      container_memory_working_set_bytes{${this.createCommonPromqlContent()},container_name!="POD"} $time_shift
    ) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    $method by (pod_name, namespace) (
      kube_pod_container_resource_limits_memory_bytes{${this.createCommonPromqlContent(true)}} $time_shift
    )))`;
    return `($method by (workload_kind, workload_name)
                (count by (workload_kind, workload_name, pod_name, namespace) (
              container_memory_working_set_bytes{${this.createCommonPromqlContent()},container_name!="POD"} $time_shift
            ) *
            on(pod_name, namespace)
            group_right(workload_kind, workload_name)
            $method by (pod_name, namespace) (
              kube_pod_container_resource_requests_memory_bytes{${this.createCommonPromqlContent(true)}} $time_shift
            )))`;
  }
  createPerformancePanelPromql(metric: string) {
    switch (metric) {
      case 'container_cpu_usage_seconds_total': // CPU使用量
        return `${this.createCommonPromqlMethod()}(rate(${metric}{${this.createCommonPromqlContent()}}[$interval] $time_shift))`;
      case 'container_network_receive_bytes_total': // 网络入带宽
      case 'container_network_transmit_bytes_total': // 网络出带宽
        return `${this.createCommonPromqlMethod()}(rate(${metric}{${this.createCommonPromqlContent(false, false)}}[$interval] $time_shift))`;
      case 'kube_pod_cpu_limits_ratio': // CPU limit使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(rate(container_cpu_system_seconds_total{${this.createCommonPromqlContent()},container_name!="POD"}[1m] $time_shift)) / ${this.createWorkLoadRequestOrLimit(true)}`;
        return `${this.createCommonPromqlMethod()}(rate(${'container_cpu_usage_seconds_total'}{${this.createCommonPromqlContent()}}[$interval] $time_shift)) / ${this.createCommonPromqlMethod()}(kube_pod_container_resource_limits_cpu_cores{${this.createCommonPromqlContent()}} $time_shift)`;
      case 'container_cpu_cfs_throttled_ratio': // CPU 限流占比
        return `${this.createCommonPromqlMethod()}((increase(container_cpu_cfs_throttled_periods_total{${this.createCommonPromqlContent()}}[$interval] $time_shift) / increase(container_cpu_cfs_periods_total{${this.createCommonPromqlContent()}}[$interval] $time_shift)))`;
      case 'kube_pod_cpu_requests_ratio': // CPU request使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(rate(container_cpu_system_seconds_total{${this.createCommonPromqlContent()},container_name!="POD"}[1m] $time_shift)) / ${this.createWorkLoadRequestOrLimit(false)}`;
        return `${this.createCommonPromqlMethod()}(rate(${'container_cpu_usage_seconds_total'}{${this.createCommonPromqlContent()}}[$interval] $time_shift)) / ${this.createCommonPromqlMethod()}(kube_pod_container_resource_requests_cpu_cores{${this.createCommonPromqlContent()}} $time_shift)`;
      case 'container_memory_working_set_bytes': // 内存使用量(rss)
        return `${this.createCommonPromqlMethod()}(${metric}{${this.createCommonPromqlContent()}} $time_shift)`;
      case 'kube_pod_memory_limits_ratio': // 内存limit使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(container_memory_working_set_bytes{${this.createCommonPromqlContent()},container_name!="POD"} $time_shift) / ${this.createWorkLoadRequestOrLimit(true, false)}`;
        return `${this.createCommonPromqlMethod()}(${'container_memory_working_set_bytes'}{${this.createCommonPromqlContent()}} $time_shift) / ${this.createCommonPromqlMethod()}(kube_pod_container_resource_limits_memory_bytes{${this.createCommonPromqlContent()}} $time_shift)`;
      case 'kube_pod_memory_requests_ratio': // 内存request使用率
        if (this.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(container_memory_working_set_bytes{${this.createCommonPromqlContent()},container_name!="POD"} $time_shift) / ${this.createWorkLoadRequestOrLimit(false, false)}`;
        return `${this.createCommonPromqlMethod()}(${'container_memory_working_set_bytes'}{${this.createCommonPromqlContent()}} $time_shift) / ${this.createCommonPromqlMethod()}(kube_pod_container_resource_requests_memory_bytes{${this.createCommonPromqlContent()}} $time_shift)`;
      default:
        return '';
    }
  }
  createPerformanceDetailPanelPromql(metric: string) {
    switch (metric) {
      case 'container_cpu_usage_seconds_total': // CPU使用量
        return `kube_pod_container_resource_limits_cpu_cores{${this.createCommonPromqlContent()}}`;
      case 'container_memory_working_set_bytes': // 内存使用量(rss)
        return `${this.createCommonPromqlMethod()}(kube_pod_container_resource_limit_memory_bytes{${this.createCommonPromqlContent()}})`;
      default:
        return '';
    }
  }
  createPerformanceDetailPanel(metric: string) {
    if (
      this.resourceList.size !== 1 ||
      !['container_cpu_usage_seconds_total', 'container_memory_working_set_bytes'].includes(metric)
    )
      return [];
    if (metric === 'container_cpu_usage_seconds_total')
      return [
        {
          data_source_label: 'prometheus',
          data_type_label: 'time_series',
          promql:
            this.groupByField === K8sTableColumnKeysEnum.WORKLOAD
              ? this.createWorkLoadRequestOrLimit(true, true)
              : `${this.createCommonPromqlMethod()}(kube_pod_container_resource_limits_cpu_cores{${this.createCommonPromqlContent()}})`,
          interval: '$interval_second',
          alias: 'limit',
          filter_dict: {},
        },
        {
          data_source_label: 'prometheus',
          data_type_label: 'time_series',
          promql:
            this.groupByField === K8sTableColumnKeysEnum.WORKLOAD
              ? this.createWorkLoadRequestOrLimit(false, true)
              : `${this.createCommonPromqlMethod()}(kube_pod_container_resource_requests_cpu_cores{${this.createCommonPromqlContent()}})`,
          interval: '$interval_second',
          alias: 'request',
          filter_dict: {},
        },
      ];
    if (metric === 'container_memory_working_set_bytes') {
      return [
        {
          data_source_label: 'prometheus',
          data_type_label: 'time_series',
          promql:
            this.groupByField === K8sTableColumnKeysEnum.WORKLOAD
              ? this.createWorkLoadRequestOrLimit(true, false)
              : `${this.createCommonPromqlMethod()}(kube_pod_container_resource_limits_memory_bytes{${this.createCommonPromqlContent()}})`,
          interval: '$interval_second',
          alias: 'limit',
          filter_dict: {},
        },
        {
          data_source_label: 'prometheus',
          data_type_label: 'time_series',
          promql:
            this.groupByField === K8sTableColumnKeysEnum.WORKLOAD
              ? this.createWorkLoadRequestOrLimit(false, false)
              : `${this.createCommonPromqlMethod()}(kube_pod_container_resource_requests_memory_bytes{${this.createCommonPromqlContent()}})`,
          interval: '$interval_second',
          alias: 'request',
          filter_dict: {},
        },
      ];
    }
  }
  async getResourceList() {
    const resourceMap = new Map<K8sTableColumnKeysEnum, string>([
      [K8sTableColumnKeysEnum.CONTAINER, ''],
      [K8sTableColumnKeysEnum.NAMESPACE, ''],
      [K8sTableColumnKeysEnum.POD, ''],
      [K8sTableColumnKeysEnum.WORKLOAD, ''],
      [K8sTableColumnKeysEnum.WORKLOAD_TYPE, ''],
    ]);
    let data: Array<Partial<Record<K8sTableColumnKeysEnum, string>>> = [];
    if (this.groupByField === K8sTableColumnKeysEnum.CLUSTER) {
      data = [
        {
          [K8sTableColumnKeysEnum.CLUSTER]: this.filterCommonParams.bk_cluster_id,
        },
      ];
    } else {
      data = this.isDetailMode
        ? this.resourceListData
        : await listK8sResources({
            ...this.filterCommonParams,
            with_history: true,
            page_size: Math.abs(this.limit),
            page: 1,
            page_type: 'scrolling',
            order_by: this.limitFunc === 'bottom' ? 'asc' : 'desc',
          })
            .then(data => {
              if (!data?.items?.length) return [];
              return data.items;
            })
            .catch(() => []);
      if (data.length) {
        const container = new Set<string>();
        const pod = new Set<string>();
        const workload = new Set<string>();
        const workloadKind = new Set<string>();
        const namespace = new Set<string>();
        const list = data.slice(0, this.limit);
        for (const item of list) {
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
    }
    this.resourceList = new Set(data);
    this.resourceMap = resourceMap;
  }
  updateViewOptions() {
    this.viewOptions = {
      interval: this.interval,
      method: this.method,
      unit: this.method === 'count' ? 'none' : undefined,
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
  @Debounce(300)
  handleLimitChange(v: string) {
    if (Number.isNaN(+v) || +v < 1 || +v > 100 || +v === this.limit) return;
    this.limit = +v;
    this.createPanelList();
  }
  /** 时间对比值变更 */
  handleCompareTimeChange(timeList: string[]) {
    this.timeOffset = timeList;
    this.updateViewOptions();
  }

  handleShowTimeCompare(v: boolean) {
    this.handleCompareTimeChange(!v ? [] : ['1h']);
  }
  handleLimitFuncChange(v: string) {
    this.limitFunc = v;
    this.createPanelList();
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
            <span class='ml-36 mr-8'>Limit</span>
            <bk-select
              style='width: 90px;'
              ext-cls='ml-8'
              behavior='simplicity'
              clearable={false}
              size='small'
              value={this.limitFunc}
              onChange={this.handleLimitFuncChange}
            >
              {['top', 'bottom'].map(method => (
                <bk-option
                  id={method}
                  key={method}
                  name={method}
                />
              ))}
            </bk-select>
            <bk-input
              style='width: 150px;'
              class='ml-8'
              behavior='simplicity'
              max={100}
              min={1}
              placeholder={this.$t('请输入1~100的数字')}
              size='small'
              type='number'
              value={this.limit}
              onChange={this.handleLimitChange}
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
          {this.loading || !this.panels.length ? (
            <TableSkeleton
              class='table-skeleton'
              type={5}
            />
          ) : (
            <FlexDashboardPanel
              id={this.isDetailMode ? 'k8s-detail' : 'k8s-charts'}
              column={1}
              needCheck={false}
              panels={this.panels}
            />
          )}
        </div>
        <K8sDetailSlider
          hideMetrics={this.hideMetrics}
          isShow={this.sideDetailShow}
          metricList={this.metricList}
          resourceDetail={this.sideDetail}
          onShowChange={v => {
            this.sideDetailShow = v;
          }}
        />
      </div>
    );
  }
}
