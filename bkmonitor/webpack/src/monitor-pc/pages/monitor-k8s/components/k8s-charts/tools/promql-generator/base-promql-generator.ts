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

import type { K8sBasePromqlGeneratorContext } from '../../typing';

/**
 * @abstract K8sBasePromqlGenerator K8s Promql 生成器场景抽象基类
 * @description K8s场景指标图表数据查询基础Promql生成器
 */
export abstract class K8sBasePromqlGenerator {
  /**
   * @static 静态方法
   * @method createCommonPromqlContent
   * @description 创建通用的Promql内容
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @param {boolean} onlyNameSpace 是否只包含namespace
   * @param {boolean} needExcludePod 是否需要排除pod
   * @param {boolean} usePod 是否使用pod
   * @returns {string} 通用的Promql内容
   */
  static createCommonPromqlContent(
    context: K8sBasePromqlGeneratorContext,
    onlyNameSpace = false,
    needExcludePod = true,
    usePod = false
  ) {
    let content = `bcs_cluster_id="${context.bcs_cluster_id}"`;
    const namespace = context.resourceMap.get(K8sTableColumnKeysEnum.NAMESPACE) || '';
    if (onlyNameSpace) {
      content += `,namespace=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(namespace)})$"`;
      return content;
    }
    // 仅当 namespace 非空时追加过滤；不能用 length>2，否则 qa/ci/a 等短 namespace 会被漏过滤导致查询范围扩大
    if (namespace) {
      content += `,namespace=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(namespace)})$"`;
    }
    const podName = usePod ? 'pod' : 'pod_name';
    switch (context.groupByField) {
      case K8sTableColumnKeysEnum.CONTAINER:
        content += `,${podName}=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(context.resourceMap.get(K8sTableColumnKeysEnum.POD))})$",container_name=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(context.resourceMap.get(K8sTableColumnKeysEnum.CONTAINER))})$"`;
        break;
      case K8sTableColumnKeysEnum.POD:
        content += `,${podName}=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(context.resourceMap.get(K8sTableColumnKeysEnum.POD))})$",${needExcludePod ? 'container_name!="POD"' : ''}`;
        break;
      case K8sTableColumnKeysEnum.WORKLOAD:
        content += `,workload_kind=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(context.resourceMap.get(K8sTableColumnKeysEnum.WORKLOAD_KIND))})$",workload_name=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(context.resourceMap.get(K8sTableColumnKeysEnum.WORKLOAD))})$"`;
        break;
      case K8sTableColumnKeysEnum.INGRESS:
      case K8sTableColumnKeysEnum.SERVICE:
      case K8sTableColumnKeysEnum.NODE:
        content += `,${context.groupByField}=~"^(${K8sBasePromqlGenerator.escapeRegExpValues(context.resourceMap.get(context.groupByField))})$"`;
        break;
      default:
        content += '';
    }
    return content;
  }
  /**
   * @static 静态方法
   * @method createCommonPromqlMethod
   * @description 创建通用的Promql方法
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns {string} 通用的Promql方法
   */
  static createCommonPromqlMethod(context: K8sBasePromqlGeneratorContext): string {
    if (context.groupByField === K8sTableColumnKeysEnum.CLUSTER) return '$method by(bcs_cluster_id)';
    if (context.groupByField === K8sTableColumnKeysEnum.CONTAINER) return '$method by(pod_name,container_name)';
    if (context.groupByField === K8sTableColumnKeysEnum.INGRESS) return '$method by(ingress,namespace)';
    if (context.groupByField === K8sTableColumnKeysEnum.SERVICE) return '$method by(service,namespace)';
    if (context.groupByField === K8sTableColumnKeysEnum.NODE) return '$method by(node)';
    return `$method by(${context.groupByField === K8sTableColumnKeysEnum.WORKLOAD ? 'workload_kind,workload_name' : context.groupByField})`;
  }
  /**
   * @static 静态方法
   * @method createWorkLoadRequestOrLimit
   * @description 创建workload的request或limit
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @param {boolean} isLimit 是否是limit
   * @param {boolean} isCPU 是否是cpu
   * @returns {string} workload的request或limit
   */
  static createWorkLoadRequestOrLimit(context: K8sBasePromqlGeneratorContext, isLimit: boolean, isCPU = true) {
    if (isCPU) {
      if (isLimit)
        return `($method by (workload_kind, workload_name) ((count by (workload_kind, workload_name, pod_name, namespace) (rate(container_cpu_usage_seconds_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"}[1m] $time_shift) ) * 0 + 1) *
      on(pod_name, namespace)
      group_right(workload_kind, workload_name)
      $method by (pod_name, namespace) (
        kube_pod_container_resource_limits_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true)}} $time_shift
      )))`;
      return `($method by (workload_kind, workload_name) ((count by (workload_kind, workload_name, pod_name, namespace) (rate(container_cpu_usage_seconds_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"}[1m] $time_shift)) * 0 + 1) *
      on(pod_name, namespace)
      group_right(workload_kind, workload_name)
      $method by (pod_name, namespace) (kube_pod_container_resource_requests_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true)}} $time_shift)))`;
    }
    if (isLimit)
      return `($method by (workload_kind, workload_name)
        ((count by (workload_kind, workload_name, pod_name, namespace) (
      container_memory_working_set_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"} $time_shift
    ) * 0 + 1) *
    on(pod_name, namespace)
    group_right(workload_kind, workload_name)
    $method by (pod_name, namespace) (
      kube_pod_container_resource_limits_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true)}} $time_shift
    )))`;
    return `($method by (workload_kind, workload_name)
                ((count by (workload_kind, workload_name, pod_name, namespace) (
              container_memory_working_set_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"} $time_shift
            ) * 0 + 1) *
            on(pod_name, namespace)
            group_right(workload_kind, workload_name)
            $method by (pod_name, namespace) (
              kube_pod_container_resource_requests_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context, true)}} $time_shift
            )))`;
  }

  /**
   * @static 静态方法
   * @method escapeRegExpValues 转义 PromQL 正则匹配值
   * @description 资源值以 =~"^(...)$" 形式拼入 PromQL，合法 K8s 资源名可能包含 . 等正则元字符，
   * 不转义会导致误匹配。多个资源名以 | 连接（K8s 名称不含 |），按 | 切分后逐个转义再拼回。
   * 不转义 -（正则中无特殊含义），保持常见带连字符资源名的输出整洁。
   * 注意：输出用于双引号字符串字面量内，PromQL 字符串遵循 Go 转义规则，单写 \. 不是
   * 合法转义序列（解析报 unknown escape sequence），正则转义引入的反斜杠须再成对转义为 \\.
   * @param {string} value 以 | 连接的资源值
   * @returns {string} 转义后的资源值
   */
  static escapeRegExpValues(value: string | undefined): string {
    return (value || '')
      .split('|')
      .map(item => item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\\/g, '\\\\'))
      .join('|');
  }

  /**
   * @abstract
   * @property promqlGenerateScene 生成器作用的场景
   */
  abstract readonly promqlGenerateScene: SceneEnum;

  /**
   * @method generate 生成Promql
   * @description 工具对外生成 promql 的统一入口
   * @param {string} metric 监控指标
   * @returns {string} 最终生成的 Promql 完整语句
   */
  generate(metric: string, context: K8sBasePromqlGeneratorContext) {
    if (!this.generateBeforeVerify(context)) return '';
    return this.scenePrivatePromqlGenerateMain(metric, context);
  }

  /**
   * @method generateBeforeVerify 前置校验传入参数是否合法有效（公共的校验逻辑）
   * @description 生成Promql(用于验证)
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns {boolean} 是否通过校验
   */
  generateBeforeVerify(context: K8sBasePromqlGeneratorContext): boolean {
    if (!context.groupByField) {
      console.warn('K8sBasePromqlGenerator: groupByField is required but empty');
      return false;
    }
    if (!context.resourceMap.size) {
      console.warn('K8sBasePromqlGenerator: resourceMap is required but empty');
      return false;
    }
    if (!context.resourceMap.get(context.groupByField)?.length) {
      console.warn('K8sBasePromqlGenerator: resourceMap.get(groupByField) is required but empty');
      return false;
    }
    if (!context.bcs_cluster_id) {
      console.warn('K8sBasePromqlGenerator: bcs_cluster_id is required but empty');
      return false;
    }

    return true;
  }

  /**
   * @abstract
   * @method scenePrivatePromqlGenerateMain
   * @description 场景私有Promql生成主函数
   * @param {string} metric 监控指标
   * @param {K8sBasePromqlGeneratorContext} context 生成器上下文
   * @returns {string} 最终生成的 Promql 完整语句
   */
  abstract scenePrivatePromqlGenerateMain(metric: string, context: K8sBasePromqlGeneratorContext): string;
}
