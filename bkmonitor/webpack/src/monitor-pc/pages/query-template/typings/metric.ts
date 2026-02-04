/* eslint-disable @typescript-eslint/naming-convention */
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

import { random } from 'monitor-common/utils';

import { CP_METHOD_LIST, METHOD_LIST } from '../../../constant/constant';

import type { AggCondition } from './query-config';

// 维度字段接口
export interface DimensionField {
  id: string;
  is_dimension?: boolean;
  name: string;
  type?: string;
}

export interface DimensionValue {
  label: string;
  value: string;
}

// 默认触发配置接口
interface DefaultTriggerConfig {
  check_window: number;
  count: number;
}

// 扩展字段接口
interface ExtendFields {
  index_set_id?: number;
  scenario_id?: string;
  scenario_name?: string;
  storage_cluster_id?: number;
  storage_cluster_name?: string;
  time_field?: string;
}

export class MetricDetailV2 {
  /** 数据标签 */
  readonly data_label: string;
  /** 数据源 */
  readonly data_source_label: string;
  /** 数据目标 */
  readonly data_target: string;
  /** 数据类型 */
  readonly data_type_label: string;
  /** 默认条件 */
  readonly default_condition: AggCondition[];
  /** 默认维度 */
  readonly default_dimensions: string[];
  /** 默认触发配置 */
  readonly default_trigger_config: DefaultTriggerConfig;
  /** 描述 */
  readonly description: string;
  /** 维度列表 */
  readonly dimensions: DimensionField[];
  /** 是否禁用 */
  readonly disabled: boolean;
  /** 扩展字段 */
  readonly extend_fields: ExtendFields;
  /** 指标ID */
  readonly id: number;
  /** 索引集ID */
  readonly index_set_id: string;
  /** 索引集名称 */
  readonly index_set_name: string;
  /** 指标字段 */
  readonly metric_field: string;
  /** 指标字段名称 */
  readonly metric_field_name: string;
  /** 指标ID */
  readonly metric_id: string;
  /** 指标DOM ID 用于dom id 设置*/
  readonly metricDomId: string;
  /** 指标名称 */
  readonly name: string;
  /** PromQL指标 */
  readonly promql_metric: string;
  /** 原始数据 */
  readonly rawMetricDetail: Partial<MetricDetailV2>;
  /** 可读名称 */
  readonly readable_name: string;
  /** 关联ID */
  readonly related_id: string;
  /** 关联名称 */
  readonly related_name: string;
  /** 备注 */
  readonly remarks: string[];
  /** 结果表ID */
  readonly result_table_id: string;
  /** 结果表标签 */
  readonly result_table_label: string;
  /** 结果表标签名称 */
  readonly result_table_label_name: string;
  /** 结果表名称 */
  readonly result_table_name: string;
  /** 时间字段 */
  readonly time_field: string;
  /** 单位 */
  readonly unit: string;
  /** 使用频率 */
  readonly use_frequency: number;

  constructor(data?: Partial<MetricDetailV2>) {
    if (data) {
      Object.assign(this, data);
      this.rawMetricDetail = Object.freeze(data);
    }
    if (data?.dimensions) {
      /** 自定义时序指标的都可以配业务维度 */
      const needBizId = this.data_source_label === 'custom' && this.data_type_label === 'time_series';
      this.dimensions = this.dimensions.filter(
        item => (needBizId || item.id !== 'bk_biz_id') && (item.is_dimension || item.is_dimension === undefined)
      );
    }
    this.metricDomId = data?.metricDomId || random(8, 'abcdefghijklmnopqrstuvwxyz');
  }
  /** 是否支持PromQL */
  get allowSource() {
    return ['bk_monitor', 'custom'].includes(this.data_source_label) && this.data_type_label === 'time_series';
  }
  // 是否可设置汇聚周期
  get canSetAggInterval() {
    return this.metricMetaId !== 'bk_monitor|event' && this.data_type_label !== 'alert';
  }
  // 是否可设置汇聚方法
  get canSetAggMethod() {
    return this.metricMetaId !== 'bk_monitor|event' && this.data_type_label !== 'alert';
  }
  // 是否可设置汇聚查询
  get canSetConvergeSearch() {
    return this.metricMetaId !== 'bk_monitor|event' && this.data_type_label !== 'alert';
  }
  // 是否需要检测算法
  get canSetDetEctionRules() {
    return this.metricMetaId !== 'bk_monitor|event' && this.data_type_label !== 'alert';
  }
  // 是否可设置维度
  get canSetDimension() {
    return this.metricMetaId !== 'bk_monitor|event';
  }
  // // 是否可设置函数
  // get canSetFunction() {
  //   if (this.metricMetaId === 'bk_data|time_series') return true; // 数据平台指标支持function
  //   return this.canSetMulitpeMetric && this.data_type_label !== 'alert';
  // }
  // // 是否可设置多指标计算
  // get canSetMetricCalc() {
  //   if (this.data_source_label === 'bk_data') return true;
  //   return (
  //     ['bk_monitor|time_series', 'custom|time_series'].includes(this.metricMetaId) &&
  //     !this.result_table_id.match(/^uptimecheck/i) &&
  //     !this.isSpecialCMDBDimension
  //   );
  // }

  // 是否可以设置多指标
  // TODO: 需要修改组件去支持特殊逻辑 !this.isSpecialCMDBDimension
  get canSetMultipleMetric() {
    return (
      (['bk_monitor|time_series', 'custom|time_series'].includes(this.metricMetaId) &&
        !this.result_table_id.match(/^uptimecheck/i)) ||
      this.data_type_label === 'alert' ||
      this.data_source_label === 'bk_data'
    );
  }
  // 是否可设置检索语句
  get canSetQueryString() {
    return (
      (this.data_source_label !== 'bk_monitor' && this.data_type_label === 'log') ||
      (this.data_source_label === 'custom' && this.data_type_label === 'event')
    );
  }
  // 是否可设置汇聚查询
  get canSetSourceCode() {
    return this.data_type_label === 'time_series' && this.data_source_label !== 'bk_log_search';
  }
  // 是否可以选择监控目标
  get canSetTarget() {
    return !(
      (
        this.data_target === 'none_target' ||
        (this.data_type_label === 'log' && this.data_source_label === 'bk_log_search') ||
        this.data_type_label === 'alert' ||
        ['host_device', 'hardware_device'].includes(this.result_table_label)
      ) // 主机设备 和 硬件设备 不可选择监控目标
    );
  }
  // 维度列表 这里已经是初始化的时候 去除了 is_dimension 为 false 的维度 以及 业务id
  get dimensionList() {
    return this.dimensions;
  }

  // 是否为icmp类型拨测指标
  get isICMP() {
    return this?.result_table_id === 'uptimecheck.icmp';
  }

  /** 是否为空指标 */
  get isNullMetric(): boolean {
    return !this.metric_id;
  }
  // 关联告警
  get isRelatedAlert() {
    return this.data_type_label === 'alert';
  }
  get methodList() {
    // if (this.metric_type === MetricType.LOG && this.metricMetaId === 'bk_log_search|log') {
    //   return METHOD_LIST;
    // }
    if (this.metricMetaId === 'bk_log_search|log') {
      return METHOD_LIST;
    }
    if (this.onlyCountMethod) {
      return [{ id: 'COUNT', name: 'COUNT' }];
    }
    return this.canSetMultipleMetric ? [...METHOD_LIST, ...CP_METHOD_LIST] : METHOD_LIST;
  }
  get metricAlias() {
    return !this.metric_field_name || this.metric_field_name === this.metric_field
      ? this.metric_id
      : this.metric_field_name;
  }

  get metricMetaId() {
    return `${this.data_source_label}|${this.data_type_label}`;
  }

  get onlyCountMethod() {
    return (
      ['bk_log_search|log', 'custom|event', 'bk_fta|event'].includes(this.metricMetaId) ||
      (this.metricMetaId === 'bk_monitor|time_series' &&
        this.result_table_id === 'uptimecheck.http' &&
        ['message', 'response_code'].includes(this.metric_field))
    );
  }

  // where 条件上维度列表 这里是 指标上的所有维度
  get whereDimensionList() {
    return this.rawMetricDetail.dimensions;
  }
}
