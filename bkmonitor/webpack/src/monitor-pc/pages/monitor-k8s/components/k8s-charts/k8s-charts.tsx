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
import { Component, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listK8sResources } from 'monitor-api/modules/k8s';
import { Debounce } from 'monitor-common/utils';
import FlexDashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';

import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { K8S_METHOD_LIST, PANEL_INTERVAL_LIST } from '../../../../constant/constant';
import {
  type IK8SMetricItem,
  K8SPerformanceMetricUnitMap,
  K8sTableColumnKeysEnum,
  SceneEnum,
} from '../../typings/k8s-new';
import FilterVarSelectSimple from '../filter-var-select/filter-var-select-simple';
import K8sDetailSlider from '../k8s-detail-slider/k8s-detail-slider';
import TimeCompareSelect from '../panel-tools/time-compare-select';
import { K8sChartTargetsCreateTool } from './tools/targets-create/k8s-chart-targets-create-tool';

import type { K8sTableColumnResourceKey } from '../k8s-table-new/k8s-table-new';
import type { K8sBasePromqlGeneratorContext } from './typing';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import './k8s-charts.scss';
@Component
export default class K8SCharts extends tsc<{
  activeMetricId?: string;
  filterCommonParams: Record<string, any>;
  groupBy: K8sTableColumnResourceKey[];
  hideMetrics: string[];
  isDetailMode?: boolean;
  metricList: IK8SMetricItem[];
  resourceListData?: Record<K8sTableColumnKeysEnum, string>[];
}> {
  @Prop({ type: Array, default: () => [] }) metricList: IK8SMetricItem[];
  @Prop({ type: Array, default: () => [] }) hideMetrics: string[];
  @Prop({ type: Array, default: () => [] }) groupBy: K8sTableColumnResourceKey[];
  @Prop({ type: Object, default: () => ({}) }) filterCommonParams: Record<string, any>;
  @Prop({ type: Boolean, default: false }) isDetailMode: boolean;
  @Prop({ type: String, default: '' }) activeMetricId: string;
  @Prop({ type: Array, default: () => [] }) resourceListData: Record<K8sTableColumnKeysEnum, string>[];
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions & { unit?: string } = {};
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
  /** 创建 场景获取图表数据参数 target 对象配置工具 */
  k8sChartTargetsCreateTool = Object.freeze(new K8sChartTargetsCreateTool());

  get canGroupByCluster() {
    return this.scene === SceneEnum.Capacity;
  }
  get groupByField() {
    return this.groupBy.at(-1) || K8sTableColumnKeysEnum.CLUSTER;
  }
  get filterLevelField() {
    if (this.scene !== SceneEnum.Network) return '';
    if (
      this.groupByField === K8sTableColumnKeysEnum.INGRESS ||
      this.filterCommonParams?.filter_dict?.[K8sTableColumnKeysEnum.INGRESS]?.length
    )
      return K8sTableColumnKeysEnum.INGRESS;
    if (
      this.groupByField === K8sTableColumnKeysEnum.SERVICE ||
      this.filterCommonParams?.filter_dict?.[K8sTableColumnKeysEnum.SERVICE]?.length
    )
      return K8sTableColumnKeysEnum.SERVICE;
    if (
      this.groupByField === K8sTableColumnKeysEnum.NAMESPACE ||
      this.filterCommonParams?.filter_dict?.[K8sTableColumnKeysEnum.NAMESPACE]?.length
    )
      return K8sTableColumnKeysEnum.NAMESPACE;
    return K8sTableColumnKeysEnum.POD;
  }
  get scene() {
    return this.filterCommonParams.scenario;
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

  @Provide('onShowDetail')
  handleShowDetail(field: string) {
    if (this.groupByField === K8sTableColumnKeysEnum.CLUSTER && this.canGroupByCluster) {
      this.sideDetail = {
        cluster: this.filterCommonParams?.bcs_cluster_id,
        externalParam: {
          isCluster: true,
        },
      };
    } else {
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
      } else if ([K8sTableColumnKeysEnum.INGRESS, K8sTableColumnKeysEnum.SERVICE].includes(this.groupByField)) {
        const isIngress = this.groupByField === K8sTableColumnKeysEnum.INGRESS;
        const list = dimension.split(':');
        const field = isIngress ? list[0] : list[1];
        item = Array.from(this.resourceList).find(item => item[this.groupByField] === field);
      } else {
        item = Array.from(this.resourceList).find(item => item[this.groupByField] === dimension);
      }
      if (!item) return;
      this.sideDetail = {
        ...item,
        cluster: item.cluster || this.filterCommonParams?.bcs_cluster_id,
      };
    }
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
    const needAuxiliaryLine = this.resourceList.size === 1;
    const targetCreateContext: K8sBasePromqlGeneratorContext = {
      resourceMap: this.resourceMap,
      bcs_cluster_id: this.filterCommonParams.bcs_cluster_id,
      groupByField: this.groupByField,
      filter_dict: this.filterCommonParams.filter_dict,
    };
    for (const item of this.metricList) {
      panelList.push({
        id: item.id,
        title: item.name,
        type: 'row',
        collapsed: true,
        panels: item.children
          ?.filter(panel => !this.hideMetrics.includes(panel.id) && panel.show_chart)
          .map(panel => ({
            id: panel.id,
            type: 'k8s_custom_graph',
            title: panel.name,
            subTitle: '',
            externalData: {
              groupByField: this.groupByField,
              metrics: [{ metric_id: panel.id }],
              filterCommonParams: this.filterCommonParams,
            },
            options: {
              legend: {
                displayMode,
              },
              unit: this.method === 'count' ? '' : panel.unit || K8SPerformanceMetricUnitMap[panel.id] || '',
            },
            targets: this.k8sChartTargetsCreateTool.createTargetsPanelList(
              this.scene,
              panel.id,
              targetCreateContext,
              needAuxiliaryLine
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

  async getResourceList() {
    const resourceMap = new Map<K8sTableColumnKeysEnum, string>([
      [K8sTableColumnKeysEnum.CLUSTER, this.filterCommonParams.bcs_cluster_id],
      [K8sTableColumnKeysEnum.CONTAINER, ''],
      [K8sTableColumnKeysEnum.INGRESS, ''],
      [K8sTableColumnKeysEnum.NAMESPACE, ''],
      [K8sTableColumnKeysEnum.NODE, ''],
      [K8sTableColumnKeysEnum.POD, ''],
      [K8sTableColumnKeysEnum.SERVICE, ''],
      [K8sTableColumnKeysEnum.WORKLOAD, ''],
      [K8sTableColumnKeysEnum.WORKLOAD_KIND, ''],
    ]);
    let data: Array<Partial<Record<K8sTableColumnKeysEnum, string>>> = [];
    if (this.groupByField === K8sTableColumnKeysEnum.CLUSTER) {
      data = [
        {
          [K8sTableColumnKeysEnum.CLUSTER]: this.filterCommonParams.bcs_cluster_id,
        },
      ];
    } else {
      const { timeRange, ...filterCommonParams } = this.filterCommonParams;
      const formatTimeRange = handleTransformToTimestamp(timeRange);
      data = this.isDetailMode
        ? this.resourceListData
        : await listK8sResources({
            ...filterCommonParams,
            start_time: formatTimeRange[0],
            end_time: formatTimeRange[1],
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
        const ingress = new Set<string>();
        const service = new Set<string>();
        const node = new Set<string>();
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
          item.ingress && ingress.add(item.ingress);
          item.service && service.add(item.service);
          item.node && node.add(item.node);
        }
        resourceMap.set(K8sTableColumnKeysEnum.CONTAINER, Array.from(container).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.POD, Array.from(pod).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.WORKLOAD, Array.from(workload).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.NAMESPACE, Array.from(namespace).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.WORKLOAD_KIND, Array.from(workloadKind).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.INGRESS, Array.from(ingress).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.SERVICE, Array.from(service).filter(Boolean).join('|'));
        resourceMap.set(K8sTableColumnKeysEnum.NODE, Array.from(node).filter(Boolean).join('|'));
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
