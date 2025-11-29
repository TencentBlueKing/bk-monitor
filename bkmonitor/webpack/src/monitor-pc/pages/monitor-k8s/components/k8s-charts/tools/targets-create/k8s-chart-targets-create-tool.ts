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

import { type SceneEnum, K8sTableColumnKeysEnum } from '../../../../typings/k8s-new';
import { K8sBasePromqlGenerator } from '../promql-generator/base-promql-generator';
import { K8sPromqlGeneratorFactory } from '../promql-generator/promql-generator-factory';

import type { K8sBasePromqlGeneratorContext, K8sChartTargetsItem, K8sChartTargetsQueryConfig } from '../../typing';

/**
 * @class K8sChartTargetsCreateTool
 * @description K8s 图表数据源 targets 创建工具类
 */
export class K8sChartTargetsCreateTool {
  private promqlGeneratorFactory: K8sPromqlGeneratorFactory;

  constructor() {
    this.promqlGeneratorFactory = new K8sPromqlGeneratorFactory();
  }

  /**
   * @method createAuxiliaryLineTargets
   * @description 创建 指标图表辅助线 数据源 targets 配置
   * @param {string} metric 指标ID
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns K8sChartTargetsItem[]
   */
  createAuxiliaryLineTargets(metric: string, context: K8sBasePromqlGeneratorContext): K8sChartTargetsItem[] {
    return this.getAuxiliaryLineQueryConfigsByMetric(metric, context).map(queryConfig => ({
      data: {
        expression: 'A',
        query_configs: [{ ...queryConfig }],
      },
      request_or_limit: true,
      datasource: 'time_series',
      data_type: 'time_series',
      api: 'grafana.graphUnifyQuery',
    }));
  }

  /**
   * @method createNodesTarget
   * @description 创建 具体节点 获取图表数据数据源 targets 配置
   * @param {SceneEnum} scene 场景
   * @param {string} metric 指标ID
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns K8sChartTargetsItem[]
   */
  createNodesTarget(scene: SceneEnum, metric: string, context: K8sBasePromqlGeneratorContext): K8sChartTargetsItem {
    return {
      data: {
        expression: 'A',
        query_configs: [
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql: this.promqlGeneratorFactory.getGeneratorInstance(scene).generate(metric, context),
            interval: '$interval_second',
            alias: 'a',
            filter_dict: {},
          },
        ],
      },
      datasource: 'time_series',
      data_type: 'time_series',
      api: 'grafana.graphUnifyQuery',
    };
  }

  /**
   * @method createTargetsPanelList
   * @description 创建 获取图表数据数据源 targets 配置
   * @param {SceneEnum} scene 场景
   * @param {string} metric 指标ID
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @param {boolean} needAuxiliaryLine 是否需要创建 指标图表辅助线
   * @returns K8sChartTargetsItem[]
   */
  createTargetsPanelList(
    scene: SceneEnum,
    metric: string,
    context: K8sBasePromqlGeneratorContext,
    needAuxiliaryLine = false
  ): K8sChartTargetsItem[] {
    const nodesTarget = this.createNodesTarget(scene, metric, context);
    const auxiliaryLineTargets = needAuxiliaryLine ? this.createAuxiliaryLineTargets(metric, context) : [];
    const targets: K8sChartTargetsItem[] = [nodesTarget, ...auxiliaryLineTargets];
    return targets;
  }

  /**
   * @method getAuxiliaryLineQueryConfigsByMetric
   * @description 获取 指标图表辅助线 查询配置中的 query_configs
   * @param {string} metric 指标ID
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns K8sChartTargetsItem[]
   */
  getAuxiliaryLineQueryConfigsByMetric(
    metric: string,
    context: K8sBasePromqlGeneratorContext
  ): K8sChartTargetsQueryConfig[] {
    switch (metric) {
      case 'node_cpu_seconds_total': // node 节点CPU使用量
        return [
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.NODE
                ? `sum by(node)(kube_pod_container_resource_limits_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`
                : `sum by(bcs_cluster_id)(kube_pod_container_resource_limits_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'limit',
            filter_dict: {},
          },
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.NODE
                ? `sum by(node)(kube_pod_container_resource_requests_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`
                : `sum by(bcs_cluster_id)(kube_pod_container_resource_requests_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'request',
            filter_dict: {},
          },
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.NODE
                ? `sum by(node)(kube_node_status_allocatable{resource="cpu",${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`
                : `sum by(bcs_cluster_id)(kube_node_status_allocatable{resource="cpu",${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'capacity',
            filter_dict: {},
          },
        ];
      case 'node_memory_working_set_bytes':
        return [
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.NODE
                ? `sum by(node)(kube_pod_container_resource_limits_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`
                : `sum by(bcs_cluster_id)(kube_pod_container_resource_limits_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'limit',
            filter_dict: {},
          },
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.NODE
                ? `sum by(node)(kube_pod_container_resource_requests_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`
                : `sum by(bcs_cluster_id)(kube_pod_container_resource_requests_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'request',
            filter_dict: {},
          },
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.NODE
                ? `sum by(node)(kube_node_status_allocatable{resource="memory",${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`
                : `sum by(bcs_cluster_id)(kube_node_status_allocatable{resource="memory",${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'capacity',
            filter_dict: {},
          },
        ];
      case 'container_cpu_usage_seconds_total':
        return [
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.WORKLOAD
                ? K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, true, true)
                : `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_limits_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'limit',
            filter_dict: {},
          },
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.WORKLOAD
                ? K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, false, true)
                : `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_requests_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'request',
            filter_dict: {},
          },
        ];
      case 'container_memory_working_set_bytes':
        return [
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.WORKLOAD
                ? K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, true, false)
                : `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_limits_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'limit',
            filter_dict: {},
          },
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql:
              context.groupByField === K8sTableColumnKeysEnum.WORKLOAD
                ? K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, false, false)
                : `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_requests_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}})`,
            interval: '$interval_second',
            alias: 'request',
            filter_dict: {},
          },
        ];
    }
    return [];
  }
}
