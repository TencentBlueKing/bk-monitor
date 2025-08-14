/* eslint-disable @typescript-eslint/naming-convention */
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

import { random } from 'monitor-common/utils/utils';

import { CP_METHOD_LIST, INTERVAL_LIST, METHOD_LIST } from '../../../../constant/constant';

import type { IModelData } from '../detection-rules/components/time-series-forecast/time-series-forecast';
import type { TranslateResult } from 'vue-i18n';

export enum MetricType {
  ALERT = 'alert',
  EVENT = 'event',
  /* 场景智能检测type传参用此字段 */
  HostAnomalyDetection = 'HostAnomalyDetection',
  LOG = 'log',
  MultivariateAnomalyDetection = 'MultivariateAnomalyDetection',
  TimeSeries = 'time_series',
}
export interface ICommonItem {
  id: number | string;
  is_dimension?: boolean;
  name: string | TranslateResult;
  type?: string;
}
export interface IMetricDetail {
  agg_condition: ICommonItem[];
  agg_dimension: string[];
  agg_interval: number;
  agg_interval_list: { id: number; name: string }[];
  agg_method: string;
  alias?: string;
  bk_biz_id: number | string;
  bkmonitor_strategy_id?: number;
  category_display: string;
  collect_config: string;
  collect_config_ids: string;
  collect_interval: number;
  custom_event_name?: string;
  data_label?: string;
  data_source_label: string;
  data_target: string;
  data_type_label: string;
  default_condition: unknown[];
  default_dimensions: string[];
  default_trigger_config: { check_window: number; count: number };
  description: string;
  dimensions: ICommonItem[];
  extend_fields: object;
  functions: unknown[];
  id: number | string;
  index_set_id?: number | string;
  index_set_name?: string;
  intelligent_detect?: Record<string, any>;
  key?: string;
  keywords_query_string?: string;
  level?: number;
  localQueryString?: string;
  logMetricList?: IMetricDetail[];
  method_list: string[];
  metric_description: string;
  metric_field: string;
  metric_field_name: string;
  metric_id: number | string;
  metric_type?: MetricType;
  name?: string;
  objectType?: string;
  plugin_type: string;
  query_string?: string;
  related_id: string;
  related_name: string;
  remarks?: string[];
  result_table_id: string;
  result_table_label: string;
  result_table_label_name: string;
  result_table_name: string;
  sceneConfig?: ISceneConfig;
  targetType?: string;
  time_field?: string;
  unit: string;
  unit_conversion: number;
  unit_suffix_id: string;
  unit_suffix_list: ICommonItem[];
  use_frequency: number;
}
export type unitType = 'm' | 's';

// 系统或插件指标前缀（result_table_id）
const sysOrPluginMetricsPrefix = [
  'dbm_system',
  'system',
  'devx_system',
  'perforce_system',
  'exporter_',
  'datadog_',
  'jmx_',
  'pushgateway_',
  'script_',
];
// 按指标类型划分的指标
const metricByType = {
  host: ['bk_target_ip', 'bk_target_cloud_id'],
  service: ['bk_target_service_instance_id'],
  node: ['bk_obj_id', 'bk_inst_id'],
};
// 检测规则算法类型枚举
export enum DetectionRuleTypeEnum {
  /** 离群检测 */
  AbnormalCluster = 'AbnormalCluster',
  /** 环比高级 */
  AdvancedRingRatio = 'AdvancedRingRatio',
  /** 同比高级 */
  AdvancedYearRound = 'AdvancedYearRound',
  /** 单指标异常检测 */
  IntelligentDetect = 'IntelligentDetect',
  /** 部分节点数 */
  PartialNodes = 'PartialNodes',
  /** 环比策略(大类) */
  RingRatio = 'RingRatio',
  /** 环比振幅 */
  RingRatioAmplitude = 'RingRatioAmplitude',
  /** 环比简易 */
  SimpleRingRatio = 'SimpleRingRatio',
  /** 同比简易 */
  SimpleYearRound = 'SimpleYearRound',
  /** 静态阈值 */
  Threshold = 'Threshold',
  /** 时序预测 */
  TimeSeriesForecasting = 'TimeSeriesForecasting',
  /** 同比策略(大类) */
  YearRound = 'YearRound',
  /** 同比振幅 */
  YearRoundAmplitude = 'YearRoundAmplitude',
  /** 同比区间 */
  YearRoundRange = 'YearRoundRange',
}

export type dataModeType = 'converge' | 'realtime';

export type EditModeType = 'Edit' | 'Source';
export interface IBaseInfoRouteParams {
  name: string; // 策略名
  scenario: string; // 监控对象
}

export interface IDetectionConfig {
  connector: 'and' | 'or';
  data: any[];
  query_configs?: any;
  unit: string;
  unitList: ICommonItem[];
  unitType: string;
}

export interface IDetectionType {
  default?: any;
  disabled?: boolean;
  id: string;
  name: string | TranslateResult;
  show: boolean;
}

// 检测规则算法类型结构
export interface IDetectionTypeItem {
  /** 算法类型中包含的子类型如: 简易,高级，振幅 */
  child?: DetectionRuleTypeEnum[];
  /** 算法类型所填写数据 */
  data?: IDetectionTypeRuleData;
  /** 算法是否禁用 */
  disabled: boolean;
  /** 算法禁用提示 */
  disabledTip: string;
  /** 算法icon */
  icon: any;
  /** 算法类型 */
  id: DetectionRuleTypeEnum;
  /** 前端生成的唯一key，没有特殊含义 */
  key?: string;
  /** 模型说明 */
  modelData?: IModelData;
  /** 算法名称 */
  name: string;
  /** 算法类型提示 */
  tip: string;
  /** 算法所属大类 ai 智能算法 convention 常规算法 */
  type: 'ai' | 'convention';
}

export interface IDetectionTypeRuleData<T = any> {
  config: T;
  level: number;
  type: DetectionRuleTypeEnum;
}

export interface IMetricMetaData {
  dataSourceLabel: string;
  dataTypeLabel: string;
  objectType: string;
}

export interface IScenarioItem {
  children?: IScenarioItem[];
  id: string;
  name: string;
}

/* 场景异常检测类型 此类型数据结构与其他几项数据结构不同 */
export interface ISceneConfig {
  algorithms: any[];
  query_configs: any[];
  scene_name?: string;
}
/* source模式下 sourceData */
export interface ISourceData {
  errorMsg?: string;
  promqlError?: boolean;
  sourceCode: string;
  sourceCodeCache?: string;
  step: number | string;
}

/** 条件类型 */
export interface IWhereItem {
  condition?: 'and' | 'or';
  key: string;
  method: string;
  value: number[] | string[];
}

// 策略类型
export type strategyType = 'fta' | 'monitor';

export class MetricDetail {
  _agg_condition = [];
  agg_dimension: string[] = [];
  agg_interval: any = 60;
  agg_interval_list = INTERVAL_LIST;
  agg_method = 'AVG';
  alias?: string = '';
  bk_biz_id: number | string = '';
  bkmonitor_strategy_id = 0;
  category_display = '';
  checked: boolean;
  collect_config = '';
  collect_config_ids = '';
  collect_interval = 0;
  custom_event_name = '';
  data_label = '';
  data_source_label = '';
  data_target = '';
  data_type_label = '';
  default_condition: unknown[] = [];
  default_dimensions: string[] = [];
  default_trigger_config: { check_window: number; count: number } = null;
  description = '';
  dimensions: ICommonItem[] = [];
  extend_fields: any = '';
  functions = [];
  id: number | string = '';
  index_set_id?: number | string = '';
  index_set_name = '';
  intelligent_detect?: Record<string, any>;
  key = '';
  keywords_query_string?: string = '*';
  level = 1;
  localQueryString?: string = '*';
  logMetricList: IMetricDetail[] = null;
  method_list = [];
  metric_description = '';
  metric_field: string;
  metric_field_name: string;
  metric_id: number | string = '';
  metric_type = null;
  name?: string = '';
  objectType = '';
  plugin_type = '';
  promql_metric?: string;
  rawDimensions: ICommonItem[] = [];
  readable_name = '';
  related_id = '';
  related_name = '';
  remarks = [];
  result_table_id = '';
  result_table_label = '';
  result_table_label_name = '';
  result_table_name = '';
  sceneConfig?: ISceneConfig = null;
  targetType = '';
  time_field = '';
  unit = '';
  unit_conversion = 0;
  unit_suffix_id = 'NONE';
  unit_suffix_list: ICommonItem[] = [];
  use_frequency = 0;
  constructor(public metricDetail?: Partial<IMetricDetail>) {
    if (!metricDetail) return;
    Object.keys(metricDetail).forEach(key => {
      if (key === 'unit_suffix_list') {
        this[key] = (metricDetail[key] || []).map(set => ({ ...set, id: set.id || 'NONE' }));
      } else {
        this[key] = metricDetail[key];
      }
    });
    this.keywords_query_string = metricDetail.keywords_query_string || metricDetail.query_string || '*';
    this.localQueryString = this.keywords_query_string;
    // 自定义事件
    if (['custom|event', 'bk_fta|event'].includes(this.metricMetaId)) {
      this.level = null;
    }
    const objectType = metricDetail.data_target
      ? metricDetail.data_target.replace('_target', '').toLocaleUpperCase()
      : 'HOST';
    this.objectType = metricDetail.objectType || objectType || '';
    this.targetType = metricDetail.targetType || (objectType === 'HOST' ? 'INSTANCE' : 'TOPO');

    this.id =
      metricDetail.data_type_label === 'log' && metricDetail.data_source_label !== 'bk_monitor'
        ? metricDetail.index_set_id
        : metricDetail.id;
    this.name = metricDetail.name || metricDetail.metric_field_name;
    if (this.agg_interval === 'auto' || !this.agg_interval) {
      this.agg_interval = 60;
    } else if (typeof this.agg_interval === 'string') {
      this.agg_interval = this.agg_interval.includes('m')
        ? +this.agg_interval.replace(/m/gi, '')
        : +this.agg_interval.replace(/s/gi, '');
    }
    this.agg_method =
      metricDetail.agg_method ||
      (this.onlyCountMethod ? 'COUNT' : metricDetail?.method_list?.length ? metricDetail.method_list[0] : 'AVG');
    if (this.agg_method.match(/_TIME$/)) {
      // 兼容老版本数据
      this.agg_method = this.agg_method.toLocaleLowerCase();
    }
    if (this.canSetDimension) {
      this.agg_dimension = metricDetail.agg_dimension || metricDetail.default_dimensions || [];
    }
    this.agg_condition =
      metricDetail.agg_condition ||
      (metricDetail.result_table_label === 'uptimecheck'
        ? metricDetail.related_id
          ? metricDetail.default_condition || []
          : []
        : metricDetail.default_condition || []);
    // 可选维度不包含业务id(默认为当前业务)
    // 如果agg_dimensions包含业务id则不筛选出业务id
    if (metricDetail?.dimensions) {
      /** 自定义时序指标的都可以配业务维度 */
      const needBizId = this.data_source_label === 'custom' && this.data_type_label === 'time_series';
      const hasbizId = this.agg_dimension.includes('bk_biz_id');
      this.dimensions = metricDetail.dimensions.filter(
        item =>
          (needBizId || hasbizId || item.id !== 'bk_biz_id') && (item.is_dimension || item.is_dimension === undefined)
      );
      this.rawDimensions = metricDetail.dimensions.filter(item => needBizId || hasbizId || item.id !== 'bk_biz_id');
    }
    if (
      this.metric_type === MetricType.LOG &&
      this.agg_method !== 'COUNT' &&
      this.metricMetaId === 'bk_log_search|time_series'
    ) {
      this.logMetricList = metricDetail.logMetricList;
      this.data_type_label = 'log';
      this.metric_field = '_index';
      this.metric_field_name = metricDetail.index_set_name || metricDetail.metric_field;
    } else {
      this.logMetricList = null;
    }
    // 处理日志关键字指标ID脏数据
    if (this.metricMetaId === 'bk_log_search|log' && this.agg_method === 'COUNT') {
      const list = this.metric_id.toString().split('.');
      if (list.length > 3) {
        this.metric_id = list.slice(0, 3).join('.');
      }
    }
    /* 随机key, 无实际含义 */
    this.key = random(8);
  }
  get agg_condition() {
    return this._agg_condition;
  }
  set agg_condition(v) {
    if (
      v?.length &&
      this.rawDimensions?.some(item => item?.type === 'number' && v?.some(set => set?.key === item?.id))
    ) {
      const conditions =
        v?.map(condition => {
          const dimension = this.rawDimensions?.find(dim => dim.id === condition.key);
          if (dimension?.type === 'number' && Array.isArray(condition.value)) {
            return {
              ...condition,
              value: condition.value.map(num => {
                return Number.isNaN(Number(num)) || num === '' ? num : Number(num);
              }),
            };
          }
          return condition;
        }) ||
        v ||
        [];
      this._agg_condition = conditions;
      return;
    }
    this._agg_condition = v;
  }
  get aggMethodList() {
    if (this.metric_type === MetricType.LOG && this.metricMetaId === 'bk_log_search|log') {
      return METHOD_LIST;
    }
    if (this.onlyCountMethod) {
      return [{ id: 'COUNT', name: 'COUNT' }];
    }
    if (this.method_list?.length) return this.method_list.map(set => ({ id: set, name: set }));
    return this.canSetMulitpeMetric ? [...METHOD_LIST, ...CP_METHOD_LIST] : METHOD_LIST;
  }
  /** 是否支持源码编辑 */
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
  // 是否可设置函数
  get canSetFunction() {
    if (this.metricMetaId === 'bk_data|time_series') return true; // 数据平台指标支持function
    return this.canSetMulitpeMetric && this.data_type_label !== 'alert';
  }
  // 是否可设置多指标计算
  get canSetMetricCalc() {
    if (this.data_source_label === 'bk_data') return true;
    return (
      ['bk_monitor|time_series', 'custom|time_series'].includes(this.metricMetaId) &&
      !this.result_table_id.match(/^uptimecheck/i) &&
      !this.isSpecialCMDBDimension
    );
  }
  // 是否可以设置多指标
  get canSetMulitpeMetric() {
    return (
      (['bk_monitor|time_series', 'custom|time_series'].includes(this.metricMetaId) &&
        !this.result_table_id.match(/^uptimecheck/i) &&
        !this.isSpecialCMDBDimension) ||
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
  // 是否可以设置实时查询
  get canSetRealTimeSearch() {
    return ['bk_monitor|time_series', 'custom|time_series', 'bk_monitor|event'].includes(this.metricMetaId);
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
  /** 日志关键字当前真实指标 */
  get curRealMetric() {
    if (this.metricMetaId === 'bk_log_search|log' && this.agg_method !== 'COUNT') {
      return this.logMetricList?.find(item => item.metric_id === this.metric_id);
    }
    return null;
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
  get isSpecialCMDBDimension() {
    return (
      this.metricMetaId === 'bk_monitor|time_series' &&
      (this.agg_dimension.some(dim => ['bk_inst_id', 'bk_obj_id'].includes(dim)) ||
        this.agg_condition.some(condition => ['bk_inst_id', 'bk_obj_id'].includes(condition.key)))
    );
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
  get sysBuiltInMetricList() {
    // 获取指标类型
    const dataTarget = this.data_target.replace('_target', '');
    // 根据指标类型获取相关维度
    const res = [metricByType[dataTarget] || []];
    // 检查是否有前缀匹配，并设置节点维度
    const startsWithAnyPrefix = sysOrPluginMetricsPrefix.some(prefix => this.result_table_id.startsWith(prefix));
    if (startsWithAnyPrefix && dataTarget === 'host') {
      res.push(metricByType.node);
    }
    return res;
  }
  setChecked(v: boolean) {
    this.checked = v;
  }
  /** 日志关键字对应指标列表 */
  setLogMetricList(list: IMetricDetail[]) {
    this.logMetricList = list;
    if (list?.length && !list.find(item => item.metric_id === this.metric_id) && this.agg_method !== 'COUNT') {
      this.metric_id = list[0].metric_id;
    }
  }
  setMetricType(type: MetricType) {
    this.metric_type = type;
  }
}
