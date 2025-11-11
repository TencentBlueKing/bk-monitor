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

import { K8sTableColumnKeysEnum, SceneEnum } from '../../../../typings/k8s-new';
import { K8sBasePromqlGenerator } from './base-promql-generator';

import type { K8sBasePromqlGeneratorContext } from '../../typing';

/**
 * @class K8sNetworkPromqlGenerator K8s 网络 Promql 生成器
 * @description K8s场景网络指标图表数据查询Promql生成器
 */
export class K8sNetworkPromqlGenerator extends K8sBasePromqlGenerator {
  readonly promqlGenerateScene = SceneEnum.Network;

  /**
   * @method determineFilterLevelField 确定过滤级别字段
   * @description 确定过滤级别字段
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns {K8sTableColumnKeysEnum} 过滤级别字段
   */
  determineFilterLevelField(context: K8sBasePromqlGeneratorContext): K8sTableColumnKeysEnum {
    if (
      context.groupByField === K8sTableColumnKeysEnum.INGRESS ||
      context.filter_dict?.[K8sTableColumnKeysEnum.INGRESS]?.length
    )
      return K8sTableColumnKeysEnum.INGRESS;
    if (
      context.groupByField === K8sTableColumnKeysEnum.SERVICE ||
      context.filter_dict?.[K8sTableColumnKeysEnum.SERVICE]?.length
    )
      return K8sTableColumnKeysEnum.SERVICE;
    if (
      context.groupByField === K8sTableColumnKeysEnum.NAMESPACE ||
      context.filter_dict?.[K8sTableColumnKeysEnum.NAMESPACE]?.length
    )
      return K8sTableColumnKeysEnum.NAMESPACE;
    return K8sTableColumnKeysEnum.POD;
  }

  scenePrivatePromqlGenerateMain(metric: string, context: K8sBasePromqlGeneratorContext): string {
    const formatterMetric = metric.replace('nw_', '');
    const filterLevelField = this.determineFilterLevelField(context);
    switch (metric) {
      case 'nw_container_network_receive_bytes_total': // 网络入带宽
      case 'nw_container_network_transmit_bytes_total': // 网络出带宽
      case 'nw_container_network_receive_packets_total': // 网络入包量
      case 'nw_container_network_transmit_packets_total': // 网络出包量
      case 'nw_container_network_receive_errors_total': // 网络入丢包量
      case 'nw_container_network_transmit_errors_total': // 网络出丢包量
        if (filterLevelField === K8sTableColumnKeysEnum.INGRESS) {
          return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} ((count by (bcs_cluster_id, namespace, ingress, service, pod)
            (ingress_with_service_relation{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}) * 0 + 1)
            * on (namespace, service) group_left(pod)
            (count by (service, namespace, pod) (pod_with_service_relation))
            * on (namespace, pod) group_left()
            sum by (namespace, pod)
            (last_over_time(
            rate(${formatterMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true, false)}}[$interval])[$interval:] $time_shift)))`;
        }
        if (filterLevelField === K8sTableColumnKeysEnum.SERVICE) {
          return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} ((count by (service, namespace, pod) (pod_with_service_relation{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}) * 0 + 1) * on (namespace, pod) group_left()
            sum by (namespace, pod)
            (last_over_time(
            rate(${formatterMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true, false)}}[$interval])[$interval:] $time_shift)))`;
        }
        if (filterLevelField === K8sTableColumnKeysEnum.NAMESPACE) {
          return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
            (last_over_time(
            rate(${formatterMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}[$interval])[$interval:] $time_shift)))`;
        }
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
          sum by (namespace, pod)
          (last_over_time(
          rate(${formatterMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}[$interval])[$interval:] $time_shift)))`;
      // 网络出丢包率
      case 'nw_container_network_transmit_errors_ratio':
      // 网络入丢包率
      // eslint-disable-next-line no-fallthrough
      case 'nw_container_network_receive_errors_ratio': {
        // const commonFilter = K8sBasePromqlGenerator.createCommonPromqlContent(false, false);
        // const isPod = this.groupByField === K8sTableColumnKeysEnum.POD;
        const isReceiveMetric = metric === 'nw_container_network_receive_errors_ratio';
        // const firstFilter = isPod ? `bcs_cluster_id="${this.filterCommonParams.bcs_cluster_id}"` : commonFilter;
        // const secondFilter = isPod ? `{${commonFilter}}` : '';
        const errorMetric = isReceiveMetric
          ? 'container_network_receive_errors_total'
          : 'container_network_transmit_errors_total';
        const totalMetric = isReceiveMetric
          ? 'container_network_receive_packets_total'
          : 'container_network_transmit_packets_total';

        if (filterLevelField === K8sTableColumnKeysEnum.INGRESS) {
          return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
              (
                count by (bcs_cluster_id, namespace, ingress, pod)
                (ingress_with_service_relation{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}) * 0 + 1)
                * on (namespace, service) group_left(pod)
                (count by (service, namespace, pod) (pod_with_service_relation))
                * on (namespace, pod) group_left()
                sum by (namespace, pod)
                (last_over_time(
                rate(${errorMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true, false)}}[$interval])[$interval:] $time_shift)
              )
              /
              (
                count by (bcs_cluster_id, namespace, ingress, pod)
                (ingress_with_service_relation{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}) * 0 + 1)
                * on (namespace, service) group_left(pod)
                (count by (service, namespace, pod) (pod_with_service_relation))
                * on (namespace, pod) group_left()
                sum by (namespace, pod)
                (last_over_time(
                rate(${totalMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true, false)}}[$interval])[$interval:] $time_shift)
              )
          )`;
        }
        if (filterLevelField === K8sTableColumnKeysEnum.SERVICE) {
          return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
            (
              count by (service, namespace, pod) (pod_with_service_relation{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}) * 0 + 1) * on (namespace, pod) group_left()
              sum by (namespace, pod)
              (last_over_time(
              rate(${errorMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true, false, true)}}[$interval])[$interval:] $time_shift)
            )
            /
            (
              count by (service, namespace, pod) (pod_with_service_relation{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}) * 0 + 1) * on (namespace, pod) group_left()
              sum by (namespace, pod)
              (last_over_time(
              rate(${totalMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true, false)}}[$interval])[$interval:] $time_shift)
            )
          )`;
        }
        if (filterLevelField === K8sTableColumnKeysEnum.NAMESPACE) {
          return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
            (
              last_over_time(
              rate(${errorMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}[$interval])[$interval:] $time_shift)
            )
            /
            (
              last_over_time(
              rate(${totalMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}[$interval])[$interval:] $time_shift)
            )
          )`;
        }
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
          (
            sum by (namespace, pod)
            (last_over_time(
            rate(${errorMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}[$interval])[$interval:] $time_shift))
          )
          /
          (
            sum by (namespace, pod)
            (last_over_time(
            rate(${totalMetric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false, true)}}[$interval])[$interval:] $time_shift))
          )
        )`;
      }
      default:
        return '';
    }
  }
}
