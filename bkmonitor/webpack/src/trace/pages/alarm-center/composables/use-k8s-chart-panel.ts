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
import { type MaybeRef, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { K8sChartTargetsCreateTool } from 'monitor-pc/pages/monitor-k8s/components/k8s-charts/tools/targets-create/k8s-chart-targets-create-tool';
import {
  type SceneEnum,
  K8SPerformanceMetricUnitMap,
  K8sTableColumnKeysEnum,
} from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';

import type { AlertK8SMetricItem } from '../typings';
import type { K8sBasePromqlGeneratorContext } from 'monitor-pc/pages/monitor-k8s/components/k8s-charts/typing';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

const _mockMetricListData = [
  {
    id: 'CPU',
    name: 'CPU',
    children: [
      {
        id: 'container_cpu_usage_seconds_total',
        name: 'CPU使用量',
        unit: 'core',
      },
      // {
      //   id: 'kube_pod_cpu_requests_ratio',
      //   name: 'CPU request使用率',
      //   unit: 'percentunit',
      // },
      // {
      //   id: 'kube_pod_cpu_limits_ratio',
      //   name: 'CPU limit使用率',
      //   unit: 'percentunit',
      // },
      // {
      //   id: 'container_cpu_cfs_throttled_ratio',
      //   name: 'CPU 限流占比',
      //   unit: 'percentunit',
      // },
    ],
  },
  // {
  //   id: 'memory',
  //   name: '内存',
  //   children: [
  //     {
  //       id: 'container_memory_working_set_bytes',
  //       name: '内存使用量(Working Set)',
  //       unit: 'bytes',
  //     },
  //     {
  //       id: 'kube_pod_memory_requests_ratio',
  //       name: '内存 request使用率',
  //       unit: 'percentunit',
  //     },
  //     {
  //       id: 'kube_pod_memory_limits_ratio',
  //       name: '内存 limit使用率',
  //       unit: 'percentunit',
  //     },
  //     {
  //       id: 'kube_pod_container_resource_requests_memory_bytes',
  //       name: '内存 request',
  //       unit: 'bytes',
  //     },
  //   ],
  // },
  // {
  //   id: 'network',
  //   name: '流量',
  //   children: [
  //     {
  //       id: 'container_network_receive_bytes_total',
  //       name: '网络入带宽',
  //       unit: 'Bps',
  //     },
  //     {
  //       id: 'container_network_transmit_bytes_total',
  //       name: '网络出带宽',
  //       unit: 'Bps',
  //     },
  //   ],
  // },
];

export interface UseK8sChartPanelOptions {
  /** 容器监控-集群ID */
  clusterId?: MaybeRef<string>;
  /** 容器监控-过滤数据 */
  filterBy?: Partial<Record<K8sTableColumnKeysEnum, string[]>>;
  /** 容器监控-下钻维度 */
  groupByField?: MaybeRef<K8sTableColumnKeysEnum>;
  /** 容器监控-资源列表数据 */
  resourceListData?: MaybeRef<Partial<Record<K8sTableColumnKeysEnum, string>>[]>;
  /** 容器监控-场景 */
  scene?: MaybeRef<SceneEnum>;
}

/**
 * @description 容器监控图表面板 panel hook
 * @param options 容器监控图表面板 panel hook选项
 */
export const useK8sChartPanel = (options: UseK8sChartPanelOptions = {}) => {
  const { scene, clusterId, filterBy, groupByField, resourceListData } = options;
  /** 容器监控图表面板创建工具 */
  const k8sChartTargetsCreateTool = new K8sChartTargetsCreateTool();
  /** 容器监控-显示数量 */
  const limit = 10;
  /** 容器监控-场景需要展示的指标项数组 */
  let metricList: AlertK8SMetricItem[] = [];
  /** 容器监控-资源映射 */
  let resourceMap: Map<K8sTableColumnKeysEnum, string> = new Map();
  /** 容器监控-资源列表 */
  let resourceList: Set<Partial<Record<K8sTableColumnKeysEnum, string>>> = new Set();

  /** 容器监控图表面板数组 */
  const dashboards = shallowRef<IPanelModel[]>([]);
  /** 是否处于请求加载状态 */
  const loading = shallowRef(false);

  /**
   * @description 获取资源列表并转化为Map结构
   */
  const getResourceList = async () => {
    const map = new Map<K8sTableColumnKeysEnum, string>([
      [K8sTableColumnKeysEnum.CLUSTER, get(clusterId)],
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
    if (get(groupByField) === K8sTableColumnKeysEnum.CLUSTER) {
      data = [
        {
          [K8sTableColumnKeysEnum.CLUSTER]: get(clusterId),
        },
      ];
    } else {
      data = get(resourceListData);
      if (data.length) {
        const container = new Set<string>();
        const pod = new Set<string>();
        const workload = new Set<string>();
        const workloadKind = new Set<string>();
        const namespace = new Set<string>();
        const ingress = new Set<string>();
        const service = new Set<string>();
        const node = new Set<string>();
        const list = data.slice(0, limit);
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
        map.set(K8sTableColumnKeysEnum.CONTAINER, Array.from(container).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.POD, Array.from(pod).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.WORKLOAD, Array.from(workload).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.NAMESPACE, Array.from(namespace).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.WORKLOAD_KIND, Array.from(workloadKind).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.INGRESS, Array.from(ingress).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.SERVICE, Array.from(service).filter(Boolean).join('|'));
        map.set(K8sTableColumnKeysEnum.NODE, Array.from(node).filter(Boolean).join('|'));
      }
    }
    resourceList = new Set(data);
    resourceMap = map;
  };

  /**
   * @description 创建面板列表
   */
  const createPanelList = async () => {
    await getResourceList();
    const panelList = [];
    const needAuxiliaryLine = resourceList.size === 1;
    const targetCreateContext: K8sBasePromqlGeneratorContext = {
      resourceMap: get(resourceMap),
      bcs_cluster_id: get(clusterId),
      groupByField: get(groupByField),
      // @ts-expect-error
      filter_dict: get(filterBy),
    };
    for (const dashboard of metricList) {
      panelList.push({
        id: dashboard.id,
        title: dashboard.name,
        type: 'row',
        collapsed: true,
        panels: dashboard.children.map(panel => ({
          id: panel.id,
          type: 'k8s_custom_graph',
          title: panel.name,
          subTitle: '',
          options: {
            unit: panel.unit || K8SPerformanceMetricUnitMap[panel.id] || '',
          },
          targets: k8sChartTargetsCreateTool.createTargetsPanelList(
            get(scene),
            panel.id,
            targetCreateContext,
            needAuxiliaryLine
          ),
        })),
      });
    }
    dashboards.value = panelList;
  };

  /**
   * @description 获取场景指标列表
   */
  const getScenarioMetricList = async () => {
    if (!get(scene)) {
      return;
    }
    loading.value = true;
    // _metricList = await getK8sScenarioMetricList(get(scene));
    metricList = _mockMetricListData;
    await createPanelList();
    loading.value = false;
  };
  watch(
    () => get(scene),
    () => {
      getScenarioMetricList();
    },
    { immediate: true }
  );
  return { dashboards };
};
