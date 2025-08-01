/* eslint-disable @typescript-eslint/member-ordering */
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
import { Component, Emit, Prop, Provide, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { dimensionUnifyQuery, graphUnifyQuery, logQuery } from 'monitor-api/modules/grafana';
import { fetchItemStatus, getUnitInfo } from 'monitor-api/modules/strategies';
import { asyncDebounceDecorator } from 'monitor-common/utils/debounce-decorator';
import { concatMonitorDocsUrl, DOCS_LINK_MAP } from 'monitor-common/utils/docs';
import { Debounce, deepClone, random, typeTools } from 'monitor-common/utils/utils';
import Viewer from 'monitor-ui/markdown-editor/viewer';
import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import MonitorDivider from '../../../../components/divider/divider.vue';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { type ILogUrlParams, transformLogUrlQuery } from '../../../../utils/index';
import CollectChart from '../../../data-retrieval/components/collect-chart.vue';
import GroupPanel from '../../strategy-config-set-new/components/group-panel';
import {
  type dataModeType,
  type EditModeType,
  type ICommonItem,
  type IDetectionConfig,
  type ISourceData,
  type IWhereItem,
  type MetricDetail,
  MetricType,
} from '../../strategy-config-set-new/typings/index';
import { allDescription } from './description';
import MultipleMetricView from './multiple-metric-view';
import NumberSelect from './number-select';
import StrategyChart from './strategy-chart/strategy-chart';
import StrategyViewAlarm from './strategy-view-alarm.vue';
import StrategyViewLog from './strategy-view-log.vue';
import StrategyViewTool from './strategy-view-tool.vue';
import { EShortcutsType } from './typing';
// import StrategyViewDimensions from './strategy-view-dimensions.vue';
import ViewDimensions from './view-dimensions';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IViewOptions } from '../../../monitor-k8s/typings';
import type { ChartType } from '../../strategy-config-set-new/detection-rules/components/intelligent-detect/intelligent-detect';
import type { IModelData } from '../../strategy-config-set-new/detection-rules/components/time-series-forecast/time-series-forecast';
import type { IFunctionsValue } from '../../strategy-config-set-new/monitor-data/function-select';
import type { IMultivariateAnomalyDetectionParams } from '../../strategy-config-set-new/type';

import './strategy-view.scss';

const windowHostDataFieldsForDimensionNameMap = {
  bk_target_ip: 'strategy-目标IP',
  bk_target_cloud_id: 'strategy-云区域ID',
  bk_host_id: 'strategy-主机ID',
};
const defaultHostDataFields = ['bk_target_ip', 'bk_target_cloud_id'];

interface IStrateViewProps {
  activeModelMd?: number;
  aiopsChartType: ChartType;
  aiopsModelMdList?: IModelData[];
  dataMode: dataModeType;
  descriptionType?: string;
  detectionConfig: IDetectionConfig;
  editMode?: EditModeType;
  expFunctions: IFunctionsValue[];
  expression: string;
  isMultivariateAnomalyDetection?: boolean;
  legalDimensionList: ICommonItem[];
  metricData: MetricDetail[];
  multivariateAnomalyDetectionParams?: IMultivariateAnomalyDetectionParams;
  sourceData?: ISourceData;
  /** 策略目标 */
  strategyTarget?: any[];
  onMultivariateAnomalyRefreshView: () => void;
}
@Component({
  name: 'strategy-view',
  components: {
    StrategyViewTool,
    MonitorEcharts,
    MonitorDivider,
    // StrategyViewDimensions,
    StrategyViewLog,
    StrategyViewAlarm,
    CollectChart,
  },
})
export default class StrategyView extends tsc<IStrateViewProps> {
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-1h', 'now'];
  // 刷新间隔
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 是否立即刷新
  @ProvideReactive('refreshImmediate') refreshImmediate = '';
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 对比类型
  @ProvideReactive('compareType') compareType = 'none';
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.toolRef.timeRange = value;
      this.tools.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    const cacheTime = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.timeRange = cacheTime;
    this.toolRef.timeRange = cacheTime;
    this.tools.timeRange = cacheTime;
    this.showRestore = false;
  }

  @Prop({ default: false, type: Boolean }) private readonly loading!: boolean;
  // 指标数据
  @Prop({ required: true, type: Array }) private readonly metricData: MetricDetail[];
  // 检测算法数据
  @Prop({ default: () => ({}), type: Object }) private readonly detectionConfig: IDetectionConfig;
  // 表达式
  @Prop({ required: true, type: String }) private readonly expression: string;
  @Prop({ default: 'converge', type: String }) private readonly dataMode: dataModeType;
  // 合法的指标维度列表
  @Prop({ default: () => [], type: Array }) private readonly legalDimensionList: ICommonItem[];
  @Prop({ default: 'none', type: String }) private readonly aiopsChartType: ChartType;
  @Prop({ default: () => [], type: Array }) private readonly aiopsModelMdList: IModelData[];
  @Prop({ default: -1, type: Number }) private readonly activeModelMd: number;
  @Prop({ default: () => [], type: Array }) private readonly expFunctions: IFunctionsValue[];
  @Prop({ default: () => [], type: Array }) private readonly strategyTarget: any[];
  @Prop({ default: '', type: String }) private readonly descriptionType: string;
  @Prop({ default: '', type: String }) private readonly editMode: EditModeType;
  @Prop({ default: () => ({ sourceCode: '', step: 'auto' }), type: Object }) private readonly sourceData: ISourceData;
  /* 是否为场景智能检测数据 */
  @Prop({ default: false, type: Boolean }) isMultivariateAnomalyDetection: boolean;
  /* 场景智能检测多指标视图参数 */
  @Prop({ default: null, type: Object }) multivariateAnomalyDetectionParams: IMultivariateAnomalyDetectionParams;

  @Ref('tool') toolRef!: StrategyViewTool;

  private tools: { refreshInterval: number; timeRange: TimeRangeType } = {
    timeRange: ['now-3h', 'now'],
    refreshInterval: 5 * 60 * 1000,
  };
  // 原始时间范围，用于图表双击还原
  private lastTimeRange: TimeRangeType = ['now-1h', 'now'];
  private metricViewChartKey = random(10);
  private dimensionsPanelKey = random(10);
  // 指标项对应的下拉列表项（原始值）
  private dimensionsScopeMap: { [prop: string]: any[] } = {};
  // 当前指标项对应的下拉列表值（当前值）
  private currentDimensionScopeMap: { [prop: string]: any[] } = {};
  private dimensions = {};
  // 当前图表指标项
  private chartDimensions = {};
  private collect = {
    show: false,
    list: [],
    count: 0,
  };
  private logData = [];
  private limit = 20;
  // private offset = 0
  private isLast = false;
  // 日志表格loading
  private isLoading = false;
  private methodMap = {
    gte: '>=',
    gt: '>',
    lte: '<=',
    lt: '<',
    eq: '=',
    neq: '!=',
  };
  private metricQueryString = '';
  private alertTabActive = '';
  // 快捷方式 近20条数据或指定（指定：不变）
  private shortcutsType: EShortcutsType = EShortcutsType.NEAR;
  /* 实际的快捷方式 当选择了维度并且切换的指定数据则为指定类型 */
  private realShortcutsType: EShortcutsType = EShortcutsType.NEAR;
  private nearNum = 10;
  private shortcutsList = [
    { id: EShortcutsType.NEAR, name: '' },
    { id: EShortcutsType.assign, name: window.i18n.t('查看指定数据') },
  ];
  // 时间范围缓存用于复位功能
  cacheTimeRange = [];
  // 柱形图不支持面积图和y轴固定
  private get chartOptions() {
    const [startTime, endTime] = handleTransformToTimestamp(this.tools.timeRange);
    let list = [];
    const isCustomEvent = this.metricQueryData.some(item => item.metricMetaId === 'custom|event');
    if (this.chartType === 'line') {
      list =
        isCustomEvent || this.metricQueryData.length > 1
          ? ['screenshot', 'set', 'area']
          : ['save', 'screenshot', 'explore', 'set', 'area'];
    } else {
      list = isCustomEvent ? ['screenshot'] : ['save', 'screenshot', 'explore'];
    }
    return {
      tool: {
        list,
      },
      xAxis: {
        // 大于 1 天时，坐标轴标签数量建议值减少
        splitNumber: endTime - startTime > 86400 ? 6 : 10,
      },
    };
  }

  private get dimensionList() {
    let list = this.legalDimensionList;
    if (this.isMultivariateAnomalyDetection) {
      list = (window.host_data_fields?.length ? window.host_data_fields : defaultHostDataFields).map(key => ({
        id: key,
        is_dimension: true,
        name: this.$t(windowHostDataFieldsForDimensionNameMap[key]),
        type: 'string',
      }));
    }
    return list;
  }

  private get dimensionData() {
    if (!this.dimensionList?.length) return [];
    return this.dimensionList.map(item => ({
      ...item,
      list: this.dimensionsScopeMap[item.id] || [],
    }));
  }

  private get chartType() {
    // 日志关键字选择了指标 转换为 时序图
    if (this.metricData.some(item => item.curRealMetric)) return 'line';
    return this.showLogContent || this.isAlertStrategy ? 'bar' : 'line';
  }

  private get showLogContent() {
    return (
      this.isAlertStrategy ||
      this.metricData.some(
        item => item.data_type_label === 'log' || ['bk_fta|event', 'custom|event'].includes(item.metricMetaId)
      )
    );
  }
  // 是否是关联告警策略
  private get isAlertStrategy() {
    return this.metricData.some(item => item.data_type_label === 'alert');
  }

  private get metricQueryData() {
    const metricData = this.isMultivariateAnomalyDetection
      ? this.multivariateAnomalyDetectionParams.metrics
      : this.metricData;
    return metricData.filter(item => !item.isNullMetric);
  }

  private get chartTitle() {
    if (this.isAlertStrategy) {
      return this.$t('事件数量');
    }
    if (this.metricQueryData.length === 1) {
      return this.metricQueryData[0].metric_field_name;
    }
    if (this.metricQueryData.length > 1 && this.expression.trim().length) {
      const title = this.metricQueryData.reduce(
        (pre, cur) => pre.replace(new RegExp(`${cur.alias}\\b`, 'gm'), cur.metric_field_name),
        this.expression
      );
      if (this.expression === title) {
        return this.metricQueryData.map(item => item.metric_field_name).join(',');
      }
      return title;
    }
    return '';
  }
  /** 多指标 */
  private get isMultipleMetrics() {
    return this.metricData.length > 1;
  }

  /** 是否需要展示说明区域 智能检测算法说明 || 系统事件说明*/
  private get needDescContent() {
    return !!this.aiopsModelMdList.length || this.isEventMetric;
  }
  /** 系统事件 */
  private get isEventMetric() {
    return this.metricQueryData.some(item => item.metricMetaId === 'bk_monitor|event');
  }

  /** 是否存在时序预测算法 */
  private get hasTimeSeriesForecast() {
    const data = this.detectionConfig.data.find(item => item.type === 'TimeSeriesForecasting');
    return !!data && this.metricQueryData?.some?.(item => item.intelligent_detect?.plan_id === data?.config?.plan_id);
  }

  /* 是否为最近多少条数据 */
  get isNear() {
    return this.realShortcutsType === EShortcutsType.NEAR;
  }

  get needNearRadio() {
    const metric = this.metricData.filter(item => !item.isNullMetric)[0];
    const dataTypeLabel = metric?.curRealMetric?.data_type_label || metric?.data_type_label;
    return dataTypeLabel === 'time_series' || (this.editMode === 'Source' && !!this.sourceData.sourceCode);
  }

  get showViewContent() {
    if (this.isMultivariateAnomalyDetection) {
      return false;
    }
    return this.metricQueryData.length > 0 || this.metricQueryData;
  }

  deactivated() {
    // 图例查看方式还原
    this.shortcutsType = EShortcutsType.NEAR;
    this.nearNum = 10;
    this.handleShortcutsTypeChange(this.shortcutsType);
  }

  @Emit('multivariateAnomalyRefreshView')
  handleMultivariateAnomalyRefreshView() {}

  @Watch('metricData', { deep: true })
  handleMetricDataChange(v: MetricDetail[]) {
    const metricData = v.filter(item => !!item.metric_id);
    if (!metricData.length) {
      return;
    }
    if (!metricData?.some?.(item => item.alias === this.alertTabActive)) {
      this.alertTabActive = metricData?.[0]?.alias || '';
    }
    const queryData = this.handleGetMetricQueryData(metricData || []);
    if (queryData.some(item => item.agg_interval < 1)) return;
    const curQueryString = JSON.stringify(queryData);
    if (curQueryString !== this.metricQueryString) {
      this.handleQueryChart();
      this.metricQueryString = JSON.stringify(queryData);
    }
  }
  @Watch('detectionConfig', { deep: true })
  handleDetectionConfigChange() {
    this.handleQueryChart();
  }
  @Watch('legalDimensionList')
  handleLegalDimensionListChange() {
    this.handleQueryChart();
  }
  @Watch('expression')
  @Watch('expFunctions', { deep: true })
  handleExpressionChange() {
    this.handleQueryChart();
  }
  @Watch('dataMode')
  handleDataModeChange() {
    this.handleQueryChart();
  }

  @Watch('strategyTarget')
  handleDataTargetChange() {
    this.handleQueryChart();
  }

  @Watch('multivariateAnomalyDetectionParams.metrics', { deep: true })
  handleMultivariateAnomalyDetectionMetricChange() {
    this.handleMultivariateAnomalyDetectionDimensionsQueryChart();
  }

  handleGetMetricQueryData(data: MetricDetail[]) {
    return data.map(
      ({ agg_dimension, agg_interval, agg_method, agg_condition, keywords_query_string, index_set_id, functions }) => ({
        agg_dimension,
        agg_interval,
        agg_method,
        agg_condition: agg_condition?.filter(item => item.key && item.value?.length) || [],
        keywords_query_string,
        index_set_id,
        functions,
      })
    );
  }
  handleToolPanelChange({ tools, type }) {
    this.tools = tools;
    type !== 'interval' && (this.lastTimeRange = tools.timeRange);
    if (type === 'timeRange') {
      this.timeRange = this.tools.timeRange;
      this.handleRefreshView();
    } else if (type === 'interval') {
      this.refreshInterval = tools.refreshInterval || -1;
    }
  }
  // 刷新策略视图
  handleRefreshView() {
    this.refreshImmediate = random(10);
    // this.metricViewChartKey = random(10);
  }
  // 触发图表查询
  @Debounce(500)
  async handleQueryChart() {
    // 没有选择监控数据，不进行图表查询
    if (!this.metricData.length || this.isMultivariateAnomalyDetection) return;
    try {
      if (!this.needNearRadio) {
        this.shortcutsType = EShortcutsType.assign;
        this.nearNum = 10;
        this.handleShortcutsTypeChange(this.shortcutsType);
      }
      /* 触发图表查询无需清空已选条件 */
      const keys = this.dimensionData.map(item => item.id);
      const temp = deepClone(this.dimensions);
      const dimensions = {};
      for (const key of keys) {
        if (temp[key]) {
          dimensions[key] = temp[key];
        }
      }
      this.dimensions = dimensions;
      // 重置数据
      this.currentDimensionScopeMap = {};
      this.limit = 20;
      this.logData = [];
      this.dimensionsPanelKey = random(10);
      await this.handleGetVariableValue();
      this.handleRefreshView();
    } catch (err) {
      console.log(err);
    }
  }

  // 触发场景监控图表查询
  @Debounce(500)
  async handleMultivariateAnomalyDetectionDimensionsQueryChart() {
    // 没有选择监控数据，不进行图表查询
    if (!this.multivariateAnomalyDetectionParams?.metrics?.length) return;
    try {
      /* 触发图表查询无需清空已选条件 */
      const keys = this.dimensionData.map(item => item.id);
      const temp = deepClone(this.dimensions);
      const dimensions = {};
      for (const key of keys) {
        if (temp[key]) {
          dimensions[key] = temp[key];
        }
      }
      this.dimensions = dimensions;
      // 重置数据
      this.currentDimensionScopeMap = {};
      this.dimensionsPanelKey = random(10);
      await this.handleGetVariableValue();
      this.handleMultivariateAnomalyRefreshView();
    } catch (err) {
      console.log(err);
    }
  }

  // 获取告警状态信息
  async getAlarmStatus(id) {
    const data = await fetchItemStatus({ metric_ids: [id] }).catch(() => ({ [id]: 0 }));
    return data?.[id];
  }
  async handleGetVariableValue() {
    // const [{ metric_field, result_table_id, data_source_label,
    //  agg_condition, data_type_label, keywords_query_string, index_set_id }] = this.metricData
    const promiseList = [];
    // const { startTime, endTime } = handleTimeRange(this.tools.timeRange);
    const [startTime, endTime] = handleTransformToTimestamp(this.tools.timeRange);
    const commonParams = this.getQueryParams(startTime, endTime);
    // 接口不支持批量，需要逐个发请求拿维度可选值信息
    for (const item of this.dimensionList) {
      const queryConfigs = commonParams.query_configs.map(queryConfig => {
        const filter_dict = this.dimensions?.[item.id] ? queryConfig.filter_dict : {};
        return {
          ...queryConfig,
          filter_dict,
        };
      });
      const params = {
        ...commonParams,
        query_configs: queryConfigs,
        dimension_field: item.id,
      };
      // promql模式下不需要再去查询维度值列表
      if (this.editMode !== 'Source') {
        promiseList.push(dimensionUnifyQuery(params));
      }
    }
    const data = await Promise.all(promiseList).catch(() => []);
    this.dimensionList.forEach((dimension, index) => {
      if (data[index] && Array.isArray(data[index])) {
        const obj = !this.dimensions?.[dimension.id] ? this.dimensionsScopeMap : this.currentDimensionScopeMap;
        const value = data[index].map(item => ({ id: item.value, name: item.label }));
        this.$set(obj, dimension.id, value);
      }
    });
  }
  // 获取策略辅助视图数据
  @asyncDebounceDecorator(200)
  async getSeriesData(startTime, endTime) {
    // 框选图表后更新时间框
    if (startTime && endTime) {
      const timeRange = [startTime, endTime] as TimeRangeType;
      this.tools.timeRange = timeRange;
    } else {
      this.tools.timeRange = this.lastTimeRange;
    }
    (this.toolRef as any)?.handleSetTimeRange?.(this.tools.timeRange);
    // 日志平台日志且检索语句为空时不执行搜索
    if (this.metricQueryData.some(item => item.metricMetaId === 'bk_log_search|log' && !item.keywords_query_string))
      return [];
    // 汇聚类型为实时不支持图表查询
    // if (this.metricQueryData.some(item => item.agg_method === 'REAL_TIME') || this.dataMode === 'realtime') return []
    // 刷新日志
    this.showLogContent && this.handleLogQuery();

    if (!Object.keys(this.dimensionsScopeMap).length) {
      await this.handleGetVariableValue();
    }
    const hasIntelligentDetect =
      !!this.metricData.some(item => item.intelligent_detect?.result_table_id) &&
      this.detectionConfig?.data?.some(item => item.type === 'IntelligentDetect');
    const params = this.getQueryParams(startTime, endTime, hasIntelligentDetect);
    if (!startTime || !endTime) {
      const [startTime, endTime] = handleTransformToTimestamp(this.tools.timeRange);
      params.start_time = startTime;
      params.end_time = endTime;
    }
    let firstData;
    const { series: queryData } = await graphUnifyQuery(params).catch(() => ({ series: [] }));
    if (hasIntelligentDetect) {
      firstData = queryData.find(item => item.alias === 'value') || [];
    } else if (this.isAlertStrategy) {
      // 关联告警视图特殊处理
      const seriesList = (queryData || []).map(item => ({ ...item, name: item.target, stack: 'fta-alert' }));
      return seriesList.reduce((pre, cur) => {
        if (pre.some(item => item.metric_field === cur.metric_field)) {
          return pre;
        }
        cur && pre.push(cur);
        return pre;
      }, []);
    } else {
      [firstData] = queryData;
    }
    if (firstData) {
      firstData.thresholds = await this.getThresholds();
      this.chartDimensions = firstData.dimensions || {};
    }
    if (!hasIntelligentDetect) {
      return [firstData];
    }
    // 智能异常检测算法 边界画图设置
    const { dimensions } = firstData;
    const boundaryList = [];
    const coverList = [];
    const algorithm2Level = {
      1: 5,
      2: 4,
      3: 3,
    };
    this.detectionConfig?.data
      ?.filter(item => item?.type === 'IntelligentDetect')
      .forEach(algItem => {
        const upBoundary =
          queryData
            ?.find(
              item =>
                item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
                item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
                item.alias === 'upper_bound'
            )
            ?.datapoints?.map(item => [item[1], item[0]]) || [];
        const lowBoundary =
          queryData
            ?.find(
              item =>
                item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
                item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
                item.alias === 'lower_bound'
            )
            ?.datapoints.map(item => [item[1], item[0]]) || [];
        boundaryList.push({
          upBoundary,
          lowBoundary,
          color: '#e6e6e6',
          stack: `boundary-${algItem?.level || ''}`,
          z: algorithm2Level[algItem?.level] || 1,
        });
        const coverData = queryData?.find(
          item =>
            item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
            item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
            item.alias === 'is_anomaly'
        )?.datapoints;
        if (coverData?.length) {
          coverList.push({
            data: coverData.map((item, index) => [
              firstData?.datapoints[index][1],
              item[0] > 0 ? firstData?.datapoints[index][0] : null,
            ]),
            color: '#ff3d3f',
            z: algorithm2Level[algItem.level] + 10,
            name: `cover-${algItem.level}`,
          });
        }
      });
    return [
      {
        ...firstData,
        boundary: boundaryList,
        coverSeries: coverList,
      },
    ];
  }
  // 获取图表查询参数设置
  getQueryParams(startTime: number | string, endTime: number | string, hasIntelligentDetect = false) {
    const timePrams = {
      start_time:
        typeof startTime === 'string' || String(startTime).length > 10 ? dayjs.tz(startTime).unix() : startTime,
      end_time: typeof endTime === 'string' || String(startTime).length > 10 ? dayjs.tz(endTime).unix() : endTime,
    };
    if (this.editMode === 'Source') {
      const params = {
        ...timePrams,
        expression: 'a',
        query_configs: [
          {
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql: this.sourceData.sourceCode,
            agg_interval: this.sourceData.step,
          },
        ],
      };
      return params;
    }
    const params = {
      ...timePrams,
      expression: this.expression || 'a',
      query_configs: this.metricQueryData.map(
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
          curRealMetric,
        }) => {
          dataTypeLabel = curRealMetric?.data_type_label || dataTypeLabel;
          resultTableId = curRealMetric?.result_table_id || resultTableId;
          dataSourceLabel = curRealMetric?.data_source_label || dataSourceLabel;
          metricField = curRealMetric?.metric_field || metricField;
          const fieldValue = () => {
            if (dataTypeLabel === 'log' && dataSourceLabel === 'bk_log_search') {
              return '_index'; // 此类情况field固定为_index
            }
            if (dataSourceLabel === 'custom' && dataTypeLabel === 'event') {
              return metricField;
            }
            return metricField || bkmonitorStrategyId;
          };
          const method = aggMethod === 'REAL_TIME' || this.dataMode === 'realtime' ? 'REAL_TIME' : aggMethod;
          const metrics = hasIntelligentDetect
            ? ['value', 'lower_bound', 'is_anomaly', 'upper_bound'].map(field => ({ field, method, alias }))
            : [{ field: fieldValue(), method, alias, display: dataTypeLabel === 'alert' }];
          const func = hasIntelligentDetect ? [...functions, { max_point_number: 0 }] : functions;
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
            return !hasIntelligentDetect ? resultTableId : intelligent_detect?.result_table_id || resultTableId;
          };
          const params = {
            data_label,
            data_source_label: !hasIntelligentDetect ? dataSourceLabel : 'bk_data',
            data_type_label: dataTypeLabel,
            metrics,
            table: tableValue(),
            group_by: agg_dimension,
            where: agg_condition.filter(item => item.key && item.value?.length),
            interval: agg_interval,
            time_field: hasIntelligentDetect ? 'dtEventTimeStamp' : timeField || 'time',
            filter_dict: this.isNear
              ? {}
              : Object.keys(this.dimensions).reduce((pre, key) => {
                  if (!typeTools.isNull(this.dimensions[key]) && agg_dimension.includes(key)) {
                    pre[key] = this.dimensions[key];
                  }
                  return pre;
                }, {}),
            functions: hasIntelligentDetect ? [] : func,
            ...logParam,
          };
          return params;
        }
      ),
    };
    return params;
  }
  // 获取阈值信息
  async getThresholds() {
    if (!this.detectionConfig?.data?.length) return [];
    const lineColor = {
      1: '#ea3636',
      2: '#ffd000',
      3: '#ff8000',
    };
    let unitSeries = [];
    if (this.detectionConfig.unit) {
      const data = await getUnitInfo({ unit_id: this.metricData[0].unit }).catch(() => ({}));
      unitSeries = data.unit_series || [];
    }
    const list = [];
    this.detectionConfig.data
      .filter(item => item.type === 'Threshold')
      .forEach(item => {
        const { config, level } = item;
        const unitConversion = unitSeries.find(item => item.suffix === this.detectionConfig.unit);
        config?.[0].forEach(cfg => {
          const thresholdTitle = this.methodMap[cfg.method] ? `(${this.methodMap[cfg.method]}${cfg.threshold})` : '';
          list.push({
            name: `${this.$t('静态阈值')}${thresholdTitle}`,
            // 动态单位转换
            yAxis: unitConversion ? unitConversion.unit_conversion * +cfg.threshold : +cfg.threshold,
            method: cfg.method,
            condition: cfg.condition,
            lineStyle: {
              color: lineColor[level],
            },
            label: {
              color: lineColor[level],
            },
            itemStyle: {
              color: lineColor[level],
              opacity: 0.1,
            },
          });
        });
      });
    return list;
  }
  // 获取指标参数
  getTargetParams(metricData?: MetricDetail[]): any {
    if (!this.metricQueryData?.length) return {};
    const [
      {
        data_source_label,
        data_type_label,
        keywords_query_string,
        agg_method,
        agg_interval,
        agg_condition: aggCondition,
        result_table_id,
        metric_field,
      },
    ] = metricData || this.metricQueryData;
    return {
      data_source_label,
      data_type_label,
      group_by: this.dimensionList.map(item => item.id),
      interval: agg_interval,
      method: agg_method,
      metric_field,
      result_table_id,
      where: (aggCondition || []).filter(item => item.key && item.value?.length),
      filter_dict: this.isNear
        ? {}
        : Object.keys(this.dimensions).reduce((pre, key) => {
            if (!typeTools.isNull(this.dimensions[key])) {
              pre[key] = this.dimensions[key];
            }
            return pre;
          }, {}),
      query_string: keywords_query_string,
    };
  }
  // 监控维度变更
  handleDimensionsChange(dimensions) {
    this.dimensions = dimensions;
    this.handleShortcutsTypeChange(this.shortcutsType);
    this.handleGetVariableValue();
    // this.handleRefreshView();
  }
  // 监控场景智能监控维度变更
  handleMultivariateAnomalyDetectionDimensionsChange(dimensions) {
    this.dimensions = dimensions;
    this.handleMultivariateAnomalyRefreshView();
  }

  hasDimensionValue() {
    return Object.values(this.dimensions).some(v => !!v);
  }
  // 查询日志内容
  async handleLogQuery() {
    const [
      {
        metric_field: metricField,
        data_source_label: dataSourceLabel,
        data_type_label: dataTypeLabel,
        agg_condition,
        result_table_id: resultTableId,
        index_set_id: indexSetId,
        keywords_query_string: indexStatement,
        bkmonitor_strategy_id: bkmonitorStrategyId,
        custom_event_name,
      },
    ] = this.metricQueryData;
    // const { startTime, endTime } = handleTimeRange(this.tools.timeRange);
    const [startTime, endTime] = handleTransformToTimestamp(this.tools.timeRange);

    // 自定义事件查询需要过滤事件名
    const filterDict: any = this.isNear ? {} : { ...this.dimensions };
    const metric = this.isAlertStrategy
      ? this.metricData.find(item => item.alias === this.alertTabActive)
      : this.metricData[0];
    if (dataSourceLabel === 'custom' && dataTypeLabel === 'event') {
      filterDict.event_name = custom_event_name || undefined;
    }
    let extendData = {};
    if (this.isAlertStrategy) {
      extendData = {
        bkmonitor_strategy_id: metricField || bkmonitorStrategyId,
        alert_name: metricField,
      };
    } else if (metric.metricMetaId === 'bk_fta|event') {
      extendData = {
        alert_name: metricField,
      };
    }
    this.isLoading = true;
    const data = await logQuery({
      data_source_label: dataSourceLabel,
      data_type_label: dataTypeLabel,
      query_string: indexStatement,
      index_set_id: String(indexSetId),
      result_table_id: resultTableId,
      where: agg_condition.filter(item => item.key && item.value?.length),
      start_time: startTime,
      end_time: endTime,
      limit: this.limit,
      filter_dict: filterDict,
      ...extendData,
    }).catch(() => []);
    this.isLoading = false;
    this.logData = data;
  }

  handleLoadMore() {
    this.handleLogQuery();
  }

  // 跳转数据检索
  handleExportToRetrieval() {
    if (this.metricQueryData.some(item => item.metricMetaId === 'bk_log_search|log')) {
      const monitorParams = this.getTargetParams();
      // const { startTime, endTime } = handleTimeRange(this.tools.timeRange);
      const [startTime, endTime] = handleTransformToTimestamp(this.tools.timeRange);
      const retrieveParams: ILogUrlParams = {
        // 检索参数
        bizId: `${this.$store.getters.bizId}`,
        keyword: monitorParams.query_string, // 搜索关键字
        addition: monitorParams.where || [],
        start_time: startTime * 1000,
        end_time: endTime * 1000,
        time_range: 'customized',
      };
      const indexSetId = this.metricQueryData[0]?.index_set_id;

      const queryStr = transformLogUrlQuery(retrieveParams);
      const url = `${this.$store.getters.bkLogSearchUrl}#/retrieve/${indexSetId}${queryStr}`;
      window.open(url);
    } else {
      const targets = [
        {
          data: {
            expression: this.isMultipleMetrics ? this.expression : '',
            query_configs: this.metricQueryData.map(item => {
              const metricData = this.getTargetParams([item]);
              return {
                ...metricData,
                // 兼容数据检索逻辑
                where: Object.keys(this.chartDimensions)
                  .map((key, index) => {
                    const temp: IWhereItem = {
                      key,
                      method: 'eq',
                      value: [this.chartDimensions[key]],
                    };
                    index > 0 && (temp.condition = 'and');
                    return temp;
                  })
                  .filter(item => !!item.key && item.value?.length),
              };
            }),
          },
        },
      ];
      window.open(
        `${location.href.replace(location.hash, '#/data-retrieval')}?targets=${encodeURIComponent(
          JSON.stringify(targets)
        )}`
      );
    }
  }

  // 收藏到仪表盘
  handleCollectSingleChart() {
    const { query_configs } = this.getQueryParams(null, null, false);
    this.collect.list = [
      {
        targets: [
          {
            alias: '',
            data: {
              expression: this.expression || 'a',
              query_configs,
            },
          },
        ],
        title: this.chartTitle,
        type: 'graph',
      },
    ];
    this.collect.show = true;
  }

  handleCloseCollect() {
    this.collect.show = false;
    this.collect.list = [];
  }
  /**
   * @description: 关联告警选项卡切换触发
   * @param {*} v 对应选项卡值
   * @return {*}
   */
  handleLogTabChange(v: string) {
    this.alertTabActive = v;
    this.handleLogQuery();
  }

  handleShortcutsTypeChange(type: EShortcutsType) {
    this.shortcutsType = type;
    if (type === EShortcutsType.assign && this.hasDimensionValue()) {
      this.realShortcutsType = type;
    } else {
      this.realShortcutsType = EShortcutsType.NEAR;
    }
  }

  render() {
    return (
      <div class='strategy-view'>
        {this.showViewContent
          ? [
              <strategy-view-tool
                key='tool'
                ref='tool'
                on-change={this.handleToolPanelChange}
                on-on-immediate-refresh={this.handleRefreshView}
                onTimezoneChange={this.handleRefreshView}
              />,
              <div
                key='strategy-view-content'
                class='strategy-view-content'
              >
                {(this.metricQueryData.length > 0 &&
                  !this.loading &&
                  !this.metricQueryData.every(item => item.metricMetaId === 'bk_monitor|event')) ||
                this.editMode === 'Source' ? (
                  [
                    <StrategyChart
                      key={'chart'}
                      aiopsChartType={this.aiopsChartType}
                      chartType={this.chartType}
                      detectionConfig={this.detectionConfig}
                      dimensions={this.editMode === 'Edit' ? this.dimensions : {}}
                      editMode={this.editMode}
                      expFunctions={this.expFunctions}
                      expression={this.expression}
                      metricData={this.metricQueryData}
                      nearNum={this.realShortcutsType === EShortcutsType.NEAR ? this.nearNum : 10}
                      shortcutsType={this.realShortcutsType}
                      sourceData={this.sourceData}
                      strategyTarget={this.strategyTarget}
                      onLogQuery={this.handleLogQuery}
                    />,
                    // 查看近20条数据
                    !!this.needNearRadio && (
                      <div class='radio-count-options'>
                        <bk-radio-group
                          value={this.shortcutsType}
                          onChange={this.handleShortcutsTypeChange}
                        >
                          {this.shortcutsList.map(sh => (
                            <bk-radio
                              key={sh.id}
                              value={sh.id}
                            >
                              {sh.id === EShortcutsType.NEAR ? (
                                <i18n
                                  class='flex-center'
                                  path='查看{0}条数据'
                                >
                                  <NumberSelect
                                    value={this.nearNum}
                                    onChange={v => {
                                      this.nearNum = v;
                                    }}
                                  />
                                </i18n>
                              ) : (
                                <span>{sh.name}</span>
                              )}
                            </bk-radio>
                          ))}
                        </bk-radio-group>
                      </div>
                    ),
                    // <monitor-divider></monitor-divider>,
                    // (this.editMode === 'Edit'
                    // && (this.shortcutsType !== 'NEAR_20' || this.hasTimeSeriesForecast)) ? <strategy-view-dimensions
                    //   class={[
                    //     'strategy-view-dimensions'
                    //   // {
                    //   //   'has-dimensions': !!this.dimensionData.length
                    //   // }
                    //   ]}
                    //   value={this.dimensions}
                    //   dimension-data={this.dimensionData}
                    //   current-dimension-map={this.currentDimensionScopeMap}
                    //   key={this.dimensionsPanelKey}
                    //   on-change={this.handleDimensionsChange}>
                    // </strategy-view-dimensions> : undefined,
                    this.editMode === 'Edit' &&
                    (this.shortcutsType !== EShortcutsType.NEAR || this.hasTimeSeriesForecast) ? (
                      <ViewDimensions
                        key={this.dimensionsPanelKey}
                        class='strategy-view-dimensions'
                        dimensionData={this.dimensionData as any}
                        value={this.dimensions}
                        onChange={this.handleDimensionsChange}
                      />
                    ) : undefined,
                  ]
                ) : (
                  <div class='chart-empty'>
                    <bk-exception
                      scene='part'
                      type='empty'
                    >
                      {this.$t('暂无数据')}
                    </bk-exception>
                  </div>
                )}
                {/* <!-- 自定义事件和日志显示日志详情 --> */}
                {this.showLogContent && (
                  <div class='strategy-view-log'>
                    <bk-alert
                      class='mb10'
                      title={this.$t('默认展示最近20条')}
                      type='info'
                    />
                    <strategy-view-log
                      v-bkloading={{ isLoading: this.isLoading }}
                      data={this.logData}
                      is-last={this.isLast}
                      on-load-more={this.handleLoadMore}
                    />
                  </div>
                )}
              </div>,
              this.needDescContent && (
                <div class={{ 'desc-content-wrap': true, 'no-padding': this.aiopsModelMdList.length > 0 }}>
                  {this.isEventMetric && <div class='desc-title'>{this.$t('系统事件说明')}</div>}
                  <div class='desc-content'>
                    {this.aiopsModelMdList.map((model, index) => (
                      <GroupPanel
                        key={index}
                        defaultExpand={true}
                        expand={index === this.activeModelMd}
                        show-expand={true}
                        title={`[${this.$tc('算法说明')}]${model.name}`}
                      >
                        {model.instruction && (
                          <div class='desc-content-doc'>
                            <div class='desc-content-doc-title'>{this.$t('方案描述')}</div>
                            <Viewer
                              class='strategy-view-desc'
                              value={model.instruction}
                            />
                          </div>
                        )}
                        {model.document && (
                          <div class='desc-content-doc'>
                            <div class='desc-content-doc-title'>{this.$t('使用说明')}</div>
                            <Viewer
                              class='strategy-view-desc'
                              value={model.document}
                            />
                          </div>
                        )}
                      </GroupPanel>
                    ))}
                    {this.isEventMetric &&
                      this.metricQueryData.map(
                        item =>
                          item.metricMetaId === 'bk_monitor|event' && (
                            <div class='strategy-view-desc'>
                              <div class='desc-name'>{item.metric_field_name}：</div>
                              {item.remarks.map((content, index) => (
                                <div
                                  key={index}
                                  class='desc-content'
                                >
                                  {index + 1}. {content}
                                </div>
                              ))}
                            </div>
                          )
                      )}
                  </div>
                </div>
              ),
              <collect-chart
                key='collect'
                collect-list={this.collect.list}
                show={this.collect.show}
                total-count={this.collect.count}
                is-single
                on-close={this.handleCloseCollect}
              />,
            ]
          : (() => {
              if (this.isMultivariateAnomalyDetection && !!this.multivariateAnomalyDetectionParams?.metrics?.length) {
                return [
                  <div
                    key={'tool-container'}
                    class='strategy-view-tool'
                  >
                    <strategy-view-tool
                      key='tool'
                      ref='tool'
                      on-change={this.handleToolPanelChange}
                      on-on-immediate-refresh={this.handleRefreshView}
                      onTimezoneChange={this.handleRefreshView}
                    />
                    <ViewDimensions
                      key={this.dimensionsPanelKey}
                      class='strategy-view-dimensions'
                      dimensionData={this.dimensionData as any}
                      value={this.dimensions}
                      onChange={this.handleMultivariateAnomalyDetectionDimensionsChange}
                    />
                  </div>,
                  <MultipleMetricView
                    key='multiple'
                    dimensions={this.dimensions}
                    metrics={this.multivariateAnomalyDetectionParams.metrics}
                    refreshKey={this.multivariateAnomalyDetectionParams.refreshKey}
                    strategyTarget={this.strategyTarget}
                    onRefreshCharKey={this.handleRefreshView}
                  />,
                  this.needDescContent && (
                    <div class={{ 'desc-content-wrap': true, 'no-padding': this.aiopsModelMdList.length > 0 }}>
                      <div class='desc-content'>
                        {this.aiopsModelMdList.map((model, index) => (
                          <GroupPanel
                            key={index}
                            defaultExpand={true}
                            expand={index === this.activeModelMd}
                            show-expand={true}
                            title={`[${this.$tc('算法说明')}]${model.name}`}
                          >
                            {model.instruction && (
                              <div class='desc-content-doc'>
                                <div class='desc-content-doc-title'>{this.$t('方案描述')}</div>
                                <Viewer
                                  class='strategy-view-desc'
                                  value={model.instruction}
                                />
                              </div>
                            )}
                            {model.document && (
                              <div class='desc-content-doc'>
                                <div class='desc-content-doc-title'>{this.$t('使用说明')}</div>
                                <Viewer
                                  class='strategy-view-desc'
                                  value={model.document}
                                />
                              </div>
                            )}
                          </GroupPanel>
                        ))}
                      </div>
                    </div>
                  ),
                ];
              }
              return (
                <div class='description-info'>
                  <div class='title'>{this.$t('使用说明')}</div>
                  {(this.isMultivariateAnomalyDetection
                    ? allDescription.filter(item => item.type === MetricType.MultivariateAnomalyDetection)
                    : allDescription
                  ).map(item => (
                    <div
                      key={item.type}
                      class={[
                        'description-item',
                        { active: item.type === this.descriptionType && !this.isMultivariateAnomalyDetection },
                      ]}
                    >
                      <div class='description-title'>{`${item.title}:`}</div>
                      <pre class='description-text'>
                        {item.description}
                        {!!DOCS_LINK_MAP.Monitor[item.type] && (
                          <a
                            class='info-url'
                            href={concatMonitorDocsUrl(DOCS_LINK_MAP.Monitor[item.type])}
                            target='blank'
                          >
                            {this.$t('相关文档查看')}
                          </a>
                        )}
                      </pre>
                    </div>
                  ))}
                </div>
              );
            })()}
      </div>
    );
  }
}
