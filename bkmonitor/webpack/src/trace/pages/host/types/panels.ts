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

export enum HostViewsPanelType {
  Graph = 'graph',
  Row = 'row',
}

/** 单个图表面板 */
export interface HostViewsGraphPanel {
  /** 面板唯一标识，如 bk_monitor.time_series.system.load.load5 */
  id: string;
  /** 副标题，通常为指标全名，如 system.load.load5 */
  subTitle: string;
  targets: PanelTarget[];
  title: string;
  type: HostViewsPanelType.Graph;
  /** 展示匹配条件，按操作系统等维度决定是否展示该面板 */
  matchDisplay?: {
    [key: string]: string | undefined;
    os_type?: string;
  };
}

/** 顶层分组（row）面板 */
export interface HostViewsRowPanel {
  /** 分组唯一标识，如 cpu、memory、__UNGROUP__ */
  id: string;
  /** 分组下的图表面板列表 */
  panels: HostViewsGraphPanel[];
  /** 分组标题，如 CPU、内存 */
  title: string;
  type: HostViewsPanelType.Row;
}

/** 查询过滤条件，按目标维度过滤 */
export interface PanelFilterDict {
  /** 目标列表，通常为 $current_target、$compare_targets 占位符 */
  targets: Placeholder[];
}

/** query_config.functions 内单个函数项，如 time_shift */
export interface PanelFunction {
  id: string;
  params: PanelFunctionParam[];
}

/** 计算函数参数项，如 time_shift 的 n */
export interface PanelFunctionParam {
  id: string;
  value: Placeholder | string;
}

/** query_config.metrics 内单个指标项 */
export interface PanelMetric {
  /** 表达式中引用的别名，如 A */
  alias: string;
  /** 指标字段名，如 load5、usage */
  field: string;
  /** 聚合方法，通常为占位符 $method */
  method: Placeholder;
}

/** 单个查询配置 */
export interface PanelQueryConfig {
  /** 数据来源标签，如 bk_monitor */
  data_source_label: string;
  /** 数据类型标签，如 time_series */
  data_type_label: string;
  filter_dict: PanelFilterDict;
  functions: PanelFunction[];
  /** 聚合维度，含占位符 $group_by 及额外维度如 device_name */
  group_by: Array<Placeholder | string>;
  /** 汇聚周期，通常为占位符 $interval */
  interval: number | Placeholder;
  metrics: PanelMetric[];
  /** 结果表名，如 system.load */
  table: string;
  /** 过滤条件，结构由具体查询决定 */
  where: unknown[];
}

/** 图表面板的单个查询目标 */
export interface PanelTarget {
  alias: string;
  /** 取数接口，如 grafana.graphUnifyQuery */
  api: string;
  data: PanelTargetData;
  data_type: string;
  datasource: string;
  /** 聚合时忽略的维度，如 bk_host_id */
  ignore_group_by: string[];
}

/** 图表查询目标的 data 字段 */
export interface PanelTargetData {
  /** 表达式，如 A */
  expression: string;
  query_configs: PanelQueryConfig[];
}

/** 指标聚合方法、维度等占位符（如 $method、$interval、$group_by），运行时会被替换 */
type Placeholder = string;
