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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, random, typeTools } from 'monitor-common/utils/utils';
import ChartWrapper from 'monitor-ui/chart-plugins/components/chart-wrapper';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { handleThreshold } from 'monitor-ui/chart-plugins/utils';

import { LETTERS } from '../../../../../common/constant';
import { SET_DIMENSIONS_OF_SERIES } from '../../../../../store/modules/strategy-config';
import { transformSensitivityValue } from '../../../util';
import { EShortcutsType } from '../typing';

import type { ChartType } from '../../../strategy-config-set-new/detection-rules/components/intelligent-detect/intelligent-detect';
import type { IFunctionsValue } from '../../../strategy-config-set-new/monitor-data/function-select';
import type {
  EditModeType,
  IDetectionConfig,
  ISourceData,
  MetricDetail,
} from '../../../strategy-config-set-new/typings';

import './strategy-chart.scss';
const CustomEventMetricAll = '__INDEX__';
interface IEvent {
  onLogQuery: () => void;
}
interface IProps {
  aiopsChartType?: ChartType;
  chartType?: 'bar' | 'line';
  dataMode?: string;
  detectionConfig?: IDetectionConfig;
  dimensions?: Record<string, any>;
  editMode?: EditModeType;
  expFunctions: IFunctionsValue[];
  expression?: string;
  metricData?: MetricDetail[];
  nearNum?: number;
  needConnect?: boolean;
  shortcutsType?: EShortcutsType;
  sourceData?: ISourceData;
  /** 策略目标 */
  strategyTarget?: any[];
}

@Component
export default class StrategyChart extends tsc<IProps, IEvent> {
  @Prop({ type: Array }) panels: PanelModel;
  /** 指标数据 */
  @Prop({ required: true, type: Array }) readonly metricData: MetricDetail[];
  /** 检测算法数据 */
  @Prop({ default: () => ({}), type: Object }) readonly detectionConfig: IDetectionConfig;
  /** 表达式 */
  @Prop({ default: 'a', type: String }) expression: string;
  /** 数据模式 汇聚 / 实时 */
  @Prop({ type: String }) dataMode: string;
  /** 维度数据 */
  @Prop({ default: () => ({}), type: Object }) dimensions: string;
  /** 图表类型 */
  @Prop({ default: 'none', type: String }) aiopsChartType: ChartType;
  /** 是否需要图表联动 */
  @Prop({ default: true, type: Boolean }) needConnect: boolean;
  /** 图表类型 */
  @Prop({ default: 'line', type: String }) chartType: 'bar' | 'line';
  /** 表达式函数 */
  @Prop({ default: () => [], type: Array }) expFunctions: IFunctionsValue[];
  @Prop({ default: () => [], type: Array }) strategyTarget: any[];
  /* 策略配置数据模式 */
  @Prop({ default: '', type: String }) editMode: EditModeType;
  /* source模式数据 */
  @Prop({ default: () => ({ sourceCode: '', step: 'auto' }), type: Object }) sourceData: ISourceData;
  /* 近多条数据 */
  @Prop({ default: 20, type: Number }) nearNum: number;
  /* 当前快捷方式 近多少条数据/指定数据（包含维度且默认近20条） */
  @Prop({ default: EShortcutsType.NEAR, type: String }) shortcutsType: EShortcutsType;

  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly timeRange!: any;
  // 立即刷新图表
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;
  // yAxis是否需要展示单位
  @InjectReactive('yAxisNeedUnit') readonly yAxisNeedUnit: boolean;

  panel = null;
  dashboardId = random(10);

  get yAxisNeedUnitGetter() {
    return this.yAxisNeedUnit ?? true;
  }

  /** 是否存在智能检测算法 */
  get hasIntelligentDetect() {
    const data = this.detectionConfig.data.find(item => item.type === 'IntelligentDetect');
    return !!data && this.metricData?.some?.(item => item.intelligent_detect?.plan_id === data?.config?.plan_id);
  }

  /** 是否存在时序预测算法 */
  get hasTimeSeriesForecast() {
    const data = this.detectionConfig.data.find(item => item.type === 'TimeSeriesForecasting');
    return !!data && this.metricData?.some?.(item => item.intelligent_detect?.plan_id === data?.config?.plan_id);
  }
  /** 时序预测的预测时长 单位：秒 */
  get duration() {
    return (
      this.detectionConfig?.data?.find(item => item.type === 'TimeSeriesForecasting')?.config?.duration || 24 * 60 * 60
    );
  }

  /** 智能检测算法指标信息 */
  get intelligentDetect() {
    return this.metricData?.[0]?.intelligent_detect;
  }

  /** 异常分值阈值线数据 */
  get scoreThreshold(): IDetectionConfig {
    if (this.aiopsChartType === 'score') {
      const aiDetectionConfig = this.detectionConfig.data.find(item => item.type === 'IntelligentDetect');
      let val = aiDetectionConfig?.config?.args?.$sensitivity;
      if (val === undefined) return null;
      /** 敏感度阈值转换规则 threshold = (1 - sensitivity / 10) * 0.8 + 0.1 */
      val = transformSensitivityValue(val);
      return {
        connector: 'and',
        data: [
          {
            level: 1,
            type: 'Threshold',
            config: [[{ method: 'gte', threshold: val, name: this.$t('异常分值阈值') }]],
            title: this.$t('异常分值阈值'),
          },
        ],
        unit: '',
        unitList: [],
        unitType: '',
      };
    }
    return null;
  }

  get showLogContent() {
    return (
      this.isAlertStrategy ||
      this.metricData.some(
        item => item.data_type_label === 'log' || ['bk_fta|event', 'custom|event'].includes(item.metricMetaId)
      )
    );
  }
  // 是否是关联告警策略
  get isAlertStrategy() {
    return this.metricData.some(item => item.data_type_label === 'alert');
  }

  get promqlStr() {
    return this.sourceData.sourceCode;
  }
  get promqlStep() {
    return this.sourceData.step;
  }

  @Watch('promqlStep')
  @Watch('promqlStr')
  @Watch('metricData', { immediate: true })
  watchMetricDataChange(val: MetricDetail[]) {
    if (val?.length) {
      this.initPanel();
    }
  }
  @Watch('aiopsChartType', { immediate: true })
  watchAiopsChartType() {
    this.initPanel();
  }

  @Watch('nearNum')
  @Watch('shortcutsType')
  @Watch('dimensions')
  @Watch('timeRange')
  @Watch('detectionConfig', { deep: true })
  @Watch('refreshImmediate')
  watchDetectionConfig() {
    this.initPanel();
  }

  // created() {
  //   this.initPanel();
  // }

  /** 初始化图表panel */
  @Debounce(1000)
  async initPanel() {
    let panelData = null;
    if (this.hasTimeSeriesForecast) {
      panelData = await this.createTimeSeriesForecastPanelData();
    } else {
      if (this.editMode === 'Source' && !this.sourceData.sourceCode) return;
      panelData = {
        id: random(10),
        title: '',
        type: 'graphs',
        options: {
          time_series_list: {
            need_hover_style: false,
          },
        },
        panels: [await this.createLocalMetricPanel()],
      };
    }
    if (this.hasIntelligentDetect && this.aiopsChartType === 'score') {
      panelData.panels.push(await this.createLocalMetricPanel(false));
    }
    this.panel = new PanelModel(panelData as any);
    this.showLogContent && this.handleLogQuery();
  }

  @Emit('logQuery')
  handleLogQuery() {}

  /** 根据表达式生成指标图的title */
  getMetricName() {
    // 字符串分隔成多个单词
    const metricName = this.getExpression().replace(/\b\w+\b/g, alias => {
      // 单词分隔成多个关键字
      return alias.replace(/bool|and|or|\w/gi, keyword => {
        if (['bool', 'or', 'and'].includes(keyword.toLocaleLowerCase())) return keyword;
        const metric = this.metricData.find(item => item.alias === keyword);
        if (metric) return metric.metric_field_name || alias;
        return keyword || '';
      });
    });
    return metricName === 'undefined' ? '' : metricName;
  }

  /**
   * 创建时序预测图的panel data
   * @returns PanelModel
   */
  async createTimeSeriesForecastPanelData() {
    const thresholdOptions = await handleThreshold(this.detectionConfig, this.yAxisNeedUnitGetter);
    const data = {
      id: this.dashboardId,
      type: 'time-series-forecast',
      title: this.getMetricName(),
      subTitle: '',
      dashboardId: this.dashboardId,
      options: {
        time_series: {
          type: this.chartType,
          only_one_result: true,
          custom_timerange: true,
          nearSeriesNum: this.nearNum,
        },
        time_series_forecast: {
          need_hover_style: false,
          duration: this.duration,
          ...thresholdOptions,
        },
      },
      targets: [
        {
          data: this.getQueryParams(this.hasTimeSeriesForecast, true),
          alias: '',
          datasource: 'time_series',
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
        },
        {
          data: this.getQueryParams(this.hasTimeSeriesForecast, true, [
            { field: 'predict', alias: undefined, method: '', display: true },
            { field: 'upper_bound', alias: undefined, method: '', display: true },
            { field: 'lower_bound', alias: undefined, method: '', display: true },
          ]),
          alias: '',
          datasource: 'time_series',
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
        },
      ],
    };
    return new PanelModel(data as any);
  }

  /**
   * 生成当前指标的数据图panel data
   * @param isMetric 是否展示指标名
   * @returns
   */
  async createLocalMetricPanel(isMetric = true) {
    const queryConfigs = this.getQueryParams(this.hasIntelligentDetect, isMetric);

    const thresholdOptions = await handleThreshold(
      isMetric ? this.detectionConfig : this.scoreThreshold,
      this.yAxisNeedUnitGetter
    );
    const { data_source_label, data_type_label, result_table_id, custom_event_name, agg_condition } =
      this.metricData[0] || {};
    const type = `${data_source_label}_${data_type_label}`;
    /** 是否是事件 */
    const isEvent = type === 'custom_event' || type === 'bk_monitor_log';

    const data = {
      id: this.dashboardId,
      // type: 'graph',
      type: this.hasTimeSeriesForecast ? 'time-series-forecast' : 'graph',
      title: isMetric ? this.getMetricName() : this.$t('异常分值'),
      subTitle: '',
      dashboardId: this.dashboardId,
      options: {
        time_series: {
          type: this.chartType,
          custom_timerange: true,
          noTransformVariables: this.editMode === 'Source',
          only_one_result: false,
          nearSeriesNum: this.nearNum,
          ...thresholdOptions,
        },
        ...(isEvent
          ? {
              alert_filterable: {
                filter_type: 'event',
                data: {
                  result_table_id,
                  data_source_label,
                  data_type_label,
                  where: [
                    custom_event_name && custom_event_name !== CustomEventMetricAll
                      ? { key: 'event_name', method: 'eq', value: [custom_event_name] }
                      : undefined,
                    ...agg_condition,
                  ].filter(Boolean),
                },
              },
            }
          : {}),
      },
      targets: [
        {
          data: queryConfigs,
          alias: '',
          datasource: 'time_series',
          data_type: 'time_series',
          api: 'grafana.graphUnifyQuery',
        },
      ],
    };
    if (!isMetric) {
      data.options = {
        ...data.options,
        header: {
          tips: this.$t('异常分值范围从0～1，越大越异常'),
        },
      } as any;
    }
    return new PanelModel(data as any);
  }
  getExpression() {
    return (
      this.expression || (this.metricData?.length === 1 ? this.metricData[0].alias : LETTERS.at(0)) || LETTERS.at(0)
    );
  }
  /**
   * 获取图表查询参数设置
   * @param isDetect 是否为智能检测算法 | 时序预测算法
   * @param isMetric 是否展示指标名
   * @param metrics 其他的metrics
   * @returns 图表查询配置
   */
  getQueryParams(isDetect = false, isMetric = true, metrics?) {
    const params = {
      expression: this.getExpression(),
      functions: this.expression ? this.expFunctions : [],
      target: this.strategyTarget || [],
      query_configs:
        this.editMode === 'Source'
          ? [
              {
                data_source_label: 'prometheus',
                data_type_label: 'time_series',
                promql: this.sourceData.sourceCode.replace(/\n/g, ''),
                interval: this.sourceData.step,
              },
            ]
          : this.metricData.map(
              ({
                data_label,
                data_source_label: dataSourceLabel,
                index_set_id,
                keywords_query_string,
                agg_interval,
                result_table_id: resultTableId,
                agg_dimension,
                agg_condition,
                data_type_label: dataTypeLabel,
                metric_field: metricField,
                agg_method: aggMethod,
                alias,
                extend_fields: extendFields,
                intelligent_detect,
                functions = [],
                metricMetaId,
                time_field: timeField,
                bkmonitor_strategy_id: bkmonitorStrategyId,
                custom_event_name,
                curRealMetric,
              }) => {
                dataSourceLabel = curRealMetric?.data_source_label || dataSourceLabel;
                dataTypeLabel = curRealMetric?.data_type_label || dataTypeLabel;
                resultTableId = curRealMetric?.result_table_id || resultTableId;
                metricField = curRealMetric?.metric_field || metricField;
                /** 原始的指标数据 避免跳转检索查不到原指标 */
                const originMetricData = isDetect
                  ? {
                      dataSourceLabel,
                      resultTableId,
                      metricField,
                      dataTypeLabel,
                    }
                  : {};
                const fieldValue = () => {
                  if (this.hasTimeSeriesForecast) return 'value';
                  if (dataSourceLabel === 'bk_log_search' && dataTypeLabel === 'log') {
                    return '_index'; // 此类情况field固定为_index
                  }
                  if (dataSourceLabel === 'custom' && dataTypeLabel === 'event') {
                    return metricField;
                  }
                  return metricField || bkmonitorStrategyId;
                };
                const method = aggMethod === 'REAL_TIME' || this.dataMode === 'realtime' ? 'REAL_TIME' : aggMethod;
                let localMetrics = this.hasIntelligentDetect
                  ? this.createMetrics(isMetric)
                  : [
                      {
                        field: fieldValue(),
                        method,
                        alias: alias || LETTERS.at(0),
                        display: dataTypeLabel === 'alert',
                      },
                    ];
                if (this.hasTimeSeriesForecast && metrics) {
                  // 时序预测
                  localMetrics = [...localMetrics, ...metrics];
                }
                const func = isDetect ? [...functions, { max_point_number: 0 }] : functions;
                let logParam = {};
                if (dataSourceLabel === 'bk_log_search') {
                  logParam =
                    metricMetaId === 'bk_log_search|log'
                      ? {
                          index_set_id,
                          query_string: keywords_query_string,
                        }
                      : { index_set_id: extendFields.index_set_id || '' };
                }
                const tableValue = () => {
                  if (dataSourceLabel === 'bk_monitor' && dataTypeLabel === 'alert') {
                    return 'strategy'; // 此类情况table固定为strategy
                  }
                  return !isDetect ? resultTableId : intelligent_detect?.result_table_id || resultTableId;
                };
                const getFieldDict = () => {
                  const fieldDict: Record<string, string> =
                    this.shortcutsType === EShortcutsType.NEAR
                      ? {}
                      : Object.keys(this.dimensions).reduce((pre, key) => {
                          if (!typeTools.isNull(this.dimensions[key]) && agg_dimension.includes(key)) {
                            pre[key] = this.dimensions[key];
                          }
                          return pre;
                        }, {});
                  if (
                    dataSourceLabel === 'custom' &&
                    dataTypeLabel === 'event' &&
                    !typeTools.isNull(custom_event_name)
                  ) {
                    fieldDict.event_name = custom_event_name;
                  }
                  return fieldDict;
                };
                const result = {
                  originMetricData: isDetect ? originMetricData : undefined,
                  data_source_label: !isDetect ? dataSourceLabel : 'bk_data',
                  data_type_label: dataTypeLabel,
                  data_label: this.detectionConfig.data.some(item =>
                    ['IntelligentDetect', 'TimeSeriesForecasting', 'AbnormalCluster', 'HostAnomalyDetection'].includes(
                      item.type
                    )
                  )
                    ? ''
                    : data_label,
                  metrics: localMetrics,
                  table: tableValue(),
                  group_by: isDetect ? intelligent_detect?.agg_dimension || [] : agg_dimension,
                  where: isDetect
                    ? intelligent_detect?.agg_condition || []
                    : agg_condition.filter(item => item.key && item.value?.length),
                  interval: agg_interval,
                  time_field: isDetect ? 'dtEventTimeStamp' : timeField || 'time',
                  filter_dict: getFieldDict(),
                  functions: isDetect ? [] : func,
                  target: this.strategyTarget || [],
                  ...logParam,
                };
                const tempAggDimension = [...agg_dimension];
                /** 指标带有智能检测算法的数据时候使用 */
                if (this.hasIntelligentDetect && this.intelligentDetect) {
                  const {
                    data_source_label,
                    data_type_label,
                    result_table_id,
                    agg_dimension = tempAggDimension,
                    agg_condition,
                  } = this.intelligentDetect;
                  result.data_source_label = data_source_label;
                  result.data_type_label = data_type_label;
                  result.table = result_table_id;
                  result.group_by = agg_dimension;
                  result.where = agg_condition;
                }
                return result;
              }
            ),
    };
    if (this.shortcutsType === EShortcutsType.NEAR) {
      Object.assign(params, { series_num: this.nearNum });
    }
    return params;
  }
  /** 智能检测算法创建请求的指标数据 */
  createMetrics(isMetric = true) {
    const { agg_method: method, alias } = this.metricData[0];
    let metricFields = [];
    const type = this.aiopsChartType;
    if (type === 'none') metricFields = ['value', 'is_anomaly'];
    if (type === 'boundary') metricFields = ['value', 'lower_bound', 'upper_bound', 'is_anomaly'];
    if (type === 'score') metricFields = isMetric ? ['value', 'is_anomaly'] : ['anomaly_score'];
    const metrics = metricFields.map((field, index) => ({
      field,
      method: field === 'anomaly_score' ? '' : this.intelligentDetect?.agg_method || method,
      alias: field === 'value' ? alias : LETTERS.at(index),
      display: ['anomaly_score', 'value'].includes(field) ? undefined : true,
    }));
    return metrics;
  }

  handleDimensionsOfSeries(dimensions: string[]) {
    this.$store.commit(`strategy-config/${SET_DIMENSIONS_OF_SERIES}`, dimensions);
  }

  render() {
    return (
      <div class={['aiops-chart-strategy-wrap', { 'time-series-forecast': this.hasTimeSeriesForecast }]}>
        {!!this.panel && (
          <ChartWrapper
            needHoverStyle={false}
            panel={this.panel}
            onDimensionsOfSeries={this.handleDimensionsOfSeries}
          />
        )}
      </div>
    );
  }
}
