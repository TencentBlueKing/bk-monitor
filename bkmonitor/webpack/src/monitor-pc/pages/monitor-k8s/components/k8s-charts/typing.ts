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

import type { K8sTableColumnKeysEnum } from '../../typings/k8s-new';
import type { IDataQuery } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

/** K8s基础Promql生成器上下文 */
export interface K8sBasePromqlGeneratorContext {
  /** bcs_cluster_id 集群ID */
  bcs_cluster_id: string;
  /** filter_dict 过滤字典 */
  filter_dict: Record<K8sTableColumnKeysEnum, string[]>;
  /** groupByField 分组字段 */
  groupByField: K8sTableColumnKeysEnum;
  /** resourceMap 资源映射 */
  resourceMap: Map<K8sTableColumnKeysEnum, string>;
}

/** K8s获取图表数据源 target 对象 */
export type K8sChartTargetsItem = Omit<IDataQuery, 'data' | 'dataType'> & {
  data: {
    expression: string;
    query_configs: K8sChartTargetsQueryConfig[];
  };
  data_type: string;
};

export interface K8sChartTargetsQueryConfig {
  alias: string;
  data_source_label: string;
  data_type_label: string;
  filter_dict: Record<string, string[]>;
  interval: string;
  promql: string;
}
