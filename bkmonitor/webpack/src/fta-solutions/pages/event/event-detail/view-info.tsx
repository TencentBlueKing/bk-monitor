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
/* eslint-disable camelcase */
import { Component, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { alertGraphQuery } from '../../../../monitor-api/modules/alert';
import { logQuery } from '../../../../monitor-api/modules/grafana';
import { fetchItemStatus } from '../../../../monitor-api/modules/strategies';
import { transformDataKey, typeTools } from '../../../../monitor-common/utils/utils';
import { TimeRangeType } from '../../../../monitor-pc/components/time-range/time-range';
import {
  IDetectionConfig,
  MetricType
} from '../../../../monitor-pc/pages/strategy-config/strategy-config-set-new/typings';
import MonitorEchart from '../../../../monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import AiopsChartEvent, { createAutoTimerange } from './aiops-chart';
import IntelligenceScene from './intelligence-scene';
import LoadingBox from './loading-box';
import OutlierDetectionChart from './outlier-detection-chart';
import TimeSeriesForecastingChart from './time-series-forecasting-chart';
import { IDetail } from './type';

import './view-info.scss';

const { i18n } = window;
interface IViewInfoProp {
  show: boolean;
  isScrollEnd?: boolean;
  alertId?: number | string;
  detail?: IDetail;
}

interface ILogData {
  time: string;
  content: string;
}

interface IDataZoomTimeRange {
  timeRange: TimeRangeType | [];
}
@Component({
  name: 'ViewInfo'
})
export default class ViewInfo extends tsc<IViewInfoProp> {
  @InjectReactive('dataZoomTimeRange') dataZoomTimeRange: IDataZoomTimeRange;
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Boolean, default: false }) isScrollEnd: boolean;
  @Prop({ type: [Number, String], default: 0 }) alertId: number | string;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  // bizId
  @ProvideReactive('bkBizId') bkBizId = null;
  public logData: ILogData[] = [];
  public logDataPage = 0;
  public logDataPageSize = 20;
  public logDataEnd = false;
  public showLoadingBox = false;
  public tableHeight = 300;
  public noGraphCode = [3314003, 3314004, 3308005];
  public logDataOffset = 0;
  public chart = {
    width: 0,
    colors: ['#FDB980'],
    first: true,
    key: 0,
    renderChart: true,
    selectForFetch: true,
    observeIntersection: true,
    emptyText: i18n.t('暂无数据'),
    title: '',
    subtitle: '',
    chartType: 'line'
  };
  public hasTraceSeries = false;
  /** 是否是自身缩放，解决自身缩放触发2次刷新，因为监听了aiops dataZoomTimeRange*/
  zoomFlag = false;
  traceInfoTimeRange = {};
  errorMsg = '';

  /* 是否为智能场景检测视图 */
  isMultivariateAnomalyDetection = false;

  @Watch('detail', { immediate: true })
  handleDetailChange() {
    this.bkBizId = this.detail.bk_biz_id;
  }
  get getShowSourceLogData() {
    const sourceTypeLabels = [
      { sourceLabel: 'bk_log_search', typeLabel: 'time_series' },
      { sourceLabel: 'custom', typeLabel: 'event' },
      { sourceLabel: 'bk_log_search', typeLabel: 'log' },
      { sourceLabel: 'bk_monitor', typeLabel: 'log' }
    ];
    if (this.detail.extra_info?.strategy) {
      const { strategy } = this.detail.extra_info;
      const sourceLabel = strategy.items?.[0]?.query_configs?.[0]?.data_source_label;
      const typeLabel = strategy.items?.[0]?.query_configs?.[0]?.data_type_label;
      return sourceTypeLabels.some(item => sourceLabel === item.sourceLabel && typeLabel === item.typeLabel);
    }
    return false;
  }

  get chartOption() {
    if (this.chart.chartType === 'bar') {
      return {
        tool: { list: ['screenshot', 'set'] }
      };
    }
    return {
      tool: { list: ['screenshot', 'set', 'area', 'explore'] }
    };
  }
  /** 检测算法数据 */
  get detectionConfig(): IDetectionConfig {
    const strategy = this.detail.extra_info?.strategy;
    const algorithms = strategy?.items?.[0]?.algorithms;
    if (!algorithms?.length) return null;
    const result = {
      unit: algorithms[0].unit_prefix,
      unitType: strategy.items?.[0]?.query_configs?.[0]?.unit || '',
      unitList: [],
      connector: strategy.detects?.[0]?.connector,
      data: algorithms.map(({ unit_prefix, ...item }) => this.displayDetectionRulesConfig(item)),
      query_configs: strategy?.items?.[0]?.query_configs
    };
    return result;
  }
  /** 是否含有智能检测算法 */
  get hasAIOpsDetection() {
    return (
      this.detectionConfig?.data?.some?.(item => item.type === 'IntelligentDetect') &&
      this.detectionConfig?.query_configs?.[0]?.intelligent_detect?.result_table_id
    );
  }

  /** 是否含有离群检测算法 */
  get hasOutlierDetection() {
    return this.detectionConfig?.data?.some?.(item => item.type === 'AbnormalCluster');
  }

  /** 是否含有时序预测算法 */
  get hasTimeSeriesForecasting() {
    return this.detectionConfig?.data?.some?.(item => item.type === 'TimeSeriesForecasting');
  }

  displayDetectionRulesConfig(item) {
    const { config } = item;
    if (item.type === 'IntelligentDetect' && !config.anomaly_detect_direct) config.anomaly_detect_direct = 'all';
    const isArray = typeTools.isArray(config);
    if (isArray) return item;
    Object.keys(config).forEach(key => {
      const value = config[key];
      if (value === null) config[key] = '';
    });
    return item;
  }

  @Watch('isScrollEnd')
  async handleIsScrollEnd(v) {
    if (v && !this.showLoadingBox && !this.logDataEnd && this.logData.length && this.show) {
      if (this.getShowSourceLogData) {
        this.showLoadingBox = true;
        await this.getSourceLogData();
      }
    }
  }
  @Watch('dataZoomTimeRange.timeRange')
  handleChangeDataZoom(val) {
    const [startTime, endTime] = val;
    /** 自身缩放不加载，直接消费掉 */
    if (this.zoomFlag) {
      this.zoomFlag = false;
      return;
    }
    this.$refs.monitorEchart && (this.$refs.monitorEchart as any).handleSeriesData(startTime, endTime);
  }
  @Watch('show')
  handleShow(v) {
    if (v) {
      this.isMultivariateAnomalyDetection =
        this.detail?.extra_info?.strategy?.items?.[0]?.algorithms?.[0].type === MetricType.MultivariateAnomalyDetection;
      if (!this.logData.length) {
        this.getData();
      }
    }
  }

  getData() {
    if (this.logDataEnd) return;
    if (this.getShowSourceLogData) {
      this.getSourceLogData();
    }
  }
  /** 缩放等 */
  dataZoom(timeRang) {
    this.zoomFlag = true;
    this.dataZoomTimeRange.timeRange = timeRang || [];
  }
  async getSourceLogData() {
    const { strategy } = this.detail.extra_info;
    const { extend_info } = this.detail;
    const sourceLabel = strategy.items[0].query_configs[0].data_source_label;
    const typeLabel = strategy.items[0].query_configs[0].data_type_label;
    this.logDataPageInit();
    if (this.logDataEnd) {
      this.showLoadingBox = false;
      return;
    }
    const params = {
      data_source_label: sourceLabel,
      data_type_label: typeLabel,
      end_time: this.detail.end_time || dayjs.tz().unix(),
      start_time: this.detail.begin_time,
      limit: this.logDataPageSize,
      offset: this.logDataOffset,
      query_string: extend_info.query_string,
      index_set_id: extend_info.index_set_id,
      result_table_id: extend_info?.result_table_id || undefined,
      where: this.detail?.graph_panel?.targets?.[0]?.data?.query_configs?.[0]?.where || [],
      filter_dict: {},
      bk_biz_id: this.detail.bk_biz_id
    };
    const data = await logQuery(params).finally(() => (this.showLoadingBox = false));
    this.logData.push(...data);
    if (this.logData?.length) {
      this.tableHeight = this.logData.length * 42 + 60;
    }
  }
  // 源日志分页
  logDataPageInit() {
    this.logDataPage += 1;
    const len = this.logData.length;
    if (len < this.logDataPageSize * (this.logDataPage - 1) && len !== 0) {
      this.logDataEnd = true;
      return;
    }
    this.logDataOffset = len;
  }

  // 获取告警状态信息
  async getAlarmStatus(id) {
    const data = await fetchItemStatus({ metric_ids: [id] }).catch(() => ({ [id]: 0 }));
    return data?.[id];
  }

  handleBuildLegend(alia, compareData = {}) {
    if (!alia) return alia;
    let alias = alia;
    Object.keys(compareData).forEach(key => {
      const val = compareData[key] || {};
      if (key === 'time_offset') {
        if (val && alias.match(/\$time_offset/g)) {
          const timeMatch = val.match(/(-?\d+)(\w+)/);
          const hasMatch = timeMatch && timeMatch.length > 2;
          alias = alias.replace(
            /\$time_offset/g,
            hasMatch
              ? dayjs.tz().add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
              : val.replace('current', this.$t('当前'))
          );
        }
      } else if (typeof val === 'object') {
        Object.keys(val)
          .sort((a, b) => b.length - a.length)
          .forEach(valKey => {
            const variate = `$${key}_${valKey}`;
            alias = alias.replace(new RegExp(`\\${variate}`, 'g'), val[valKey]);
          });
      } else {
        alias = alias.replace(`$${key}`, val);
      }
    });
    while (/\|\s*\|/g.test(alias)) {
      alias = alias.replace(/\|\s*\|/g, '|');
    }
    return alias.replace(/\|$/g, '');
  }

  async handleGetSeriesData(startTime = '', endTime = '', range = false) {
    const { graph_panel } = this.detail;
    const params: any = {
      bk_biz_id: this.detail.bk_biz_id,
      id: this.detail.id
    };
    if (range && startTime && endTime) {
      params.start_time = dayjs.tz(startTime).unix();
      params.end_time = dayjs.tz(endTime).unix();
    }
    if (graph_panel) {
      const [{ data: queryConfig, alias }] = graph_panel.targets;
      this.chart.title = graph_panel.title || '';
      this.chart.subtitle = graph_panel.subTitle || '';
      this.chart.chartType = graph_panel.type === 'bar' ? 'bar' : 'line';
      if (queryConfig.extendMetricFields?.some(item => item.includes('is_anomaly'))) {
        queryConfig.function = { ...queryConfig.function, max_point_number: 0 };
      }
      const chartQueryConfig = transformDataKey(queryConfig, true);
      this.errorMsg = '';
      const res = await alertGraphQuery(
        { ...chartQueryConfig, ...params },
        { needRes: true, needMessage: false }
      ).catch(err => {
        if (err && this.noGraphCode.includes(err.code)) {
          this.chart.selectForFetch = false;
          this.chart.observeIntersection = false;
          this.chart.emptyText = err.message;
        } else {
          // this.$bkMessage({
          //   message: err.message,
          //   theme: 'error',
          //   ellipsisLine: 0
          // });
        }
        this.errorMsg = err.message || err.msg;
      });
      this.chart.first = false;
      const { severity } = this.detail;
      const series = res?.data?.series || [];
      const traceSeries = res?.data?.trace_series || [];
      this.hasTraceSeries = !!traceSeries.length && this.chart.chartType === 'line';
      // const algorithmValue = algorithmList?.find(item => item?.level === level)?.algorithmConfig?.sensitivityValue
      // 异常检测图表转换
      // eslint-disable-next-line camelcase
      if (chartQueryConfig?.extend_fields?.intelligent_detect?.result_table_id && series.length) {
        const chartSeries = series.find(
          item => item?.metric?.metric_field === 'value' && item?.time_offset === 'current'
        );
        if (!chartSeries) return [];
        // 智能异常检测算法 边界画图设置
        const { dimensions } = chartSeries;
        const coverList = [];
        const algorithm2Level = {
          1: 15,
          2: 14,
          3: 13
        };
        const upBoundary =
          series
            ?.find(
              item =>
                item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
                item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
                item.metric.metric_field === 'upper_bound'
            )
            ?.datapoints?.map(item => [item[1], item[0]]) || [];
        const lowBoundary =
          series
            ?.find(
              item =>
                item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
                item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
                item.metric.metric_field === 'lower_bound'
            )
            ?.datapoints.map(item => [item[1], item[0]]) || [];
        const coverData = series?.find(
          item =>
            item.dimensions.bk_target_ip === dimensions.bk_target_ip &&
            item.dimensions.bk_target_cloud_id === dimensions.bk_target_cloud_id &&
            item.metric.metric_field === 'is_anomaly'
        )?.datapoints;
        if (coverData?.length) {
          coverList.push({
            data: coverData.map((item, index) => [
              chartSeries?.datapoints[index][1],
              item[0] > 0 ? chartSeries?.datapoints[index][0] : null
            ]),
            color: '#ea3636',
            z: algorithm2Level[severity] + 10,
            name: `${severity}-cover`
          });
        }
        const allData = series
          .filter(item => item?.metric?.metric_field === 'value')
          .map(({ target, datapoints, ...setData }) => {
            const item = {
              datapoints,
              ...setData,
              target:
                this.handleBuildLegend(alias, {
                  ...setData,
                  tag: setData.dimensions,
                  metric: setData.metric,
                  // formula: params.method,
                  ...params
                }) || target
            };
            if (setData.time_offset === 'current') {
              return {
                ...item,
                boundary: [
                  {
                    upBoundary,
                    lowBoundary,
                    color: '#e6e6e6',
                    stack: `${severity}-boundary-${item.target}`,
                    z: algorithm2Level[severity]
                  }
                ],
                coverSeries: coverList.map(set => ({ ...set, name: `${set.name}-${item.target}` }))
              };
            }
            return item;
          });

        return allData;
      }
      const result = series.map(({ target, datapoints, ...setData }) => ({
        datapoints,
        ...setData,
        target:
          this.handleBuildLegend(alias, {
            ...setData,
            tag: setData.dimensions,
            metric: setData.metric,
            // formula: params.method,
            ...params
          }) || target
      }));
      if (this.hasTraceSeries) {
        const interval = this.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
        const { startTime, endTime } = createAutoTimerange(this.detail.begin_time, this.detail.end_time, interval);
        this.traceInfoTimeRange = {
          start_time: dayjs.tz(startTime).unix(),
          end_time: dayjs.tz(endTime).unix()
        };
        /* 需要降低trace散点图的密度 */
        const allMaxMinTimeStamp = [];
        const viewWidth = this.$el.querySelector('.series-view-container').clientWidth;
        series.forEach(s => {
          if (s.datapoints.length) {
            allMaxMinTimeStamp.push(s.datapoints[0][1]);
            allMaxMinTimeStamp.push(s.datapoints[s.datapoints.length - 1][1]);
          }
        });
        traceSeries.forEach(t => {
          const timeIndex = t.columns.findIndex(name => name === 'bk_trace_timestamp');
          const valueIndex = t.columns.findIndex(name => name === 'bk_trace_value');
          /* 过滤时间戳与值为空的数据 */
          const dataPoints = t.data_points.filter(item => !!item[timeIndex] && typeof item[valueIndex] === 'number');
          if (dataPoints.length) {
            allMaxMinTimeStamp.push(dataPoints[0][timeIndex]);
            allMaxMinTimeStamp.push(dataPoints[dataPoints.length - 1][timeIndex]);
          }
        });
        const allMaxMinTimeStampSort = allMaxMinTimeStamp.sort((a, b) => a - b);
        const minTimeStamp = allMaxMinTimeStampSort[0];
        const maxTimeStamp = allMaxMinTimeStampSort[allMaxMinTimeStampSort.length - 1];
        /* 一个像素点占用多少ms */
        const poinitMs = (maxTimeStamp - minTimeStamp) / viewWidth;
        /* 一个散点占用的ms */
        const traceMaxPointMs = poinitMs * 8;
        const traceReduceDensityFn = (data: any[][], timeIndex: number, valueIndex: number) => {
          const temp = [];
          data.forEach(d => {
            const tempStamp = d[timeIndex];
            const tempValue = d[valueIndex];
            if (temp.length) {
              if (
                tempStamp - temp[temp.length - 1][timeIndex] > traceMaxPointMs ||
                (tempStamp === temp[temp.length - 1][timeIndex] && tempValue !== temp[temp.length - 1][valueIndex])
              ) {
                temp.push(d);
              }
            } else {
              temp.push(d);
            }
          });
          return temp;
        };
        traceSeries.forEach(item => {
          const valueIndex = item.columns.findIndex(name => name === 'bk_trace_value');
          const timeIndex = item.columns.findIndex(name => name === 'bk_trace_timestamp');
          /* 过滤时间戳与值为空的数据 */
          const dataPointsFilter = item.data_points.filter(
            item => !!item[timeIndex] && typeof item[valueIndex] === 'number'
          );
          const datapoints = traceReduceDensityFn(dataPointsFilter, timeIndex, valueIndex);
          result.push({
            ...item,
            data_points: datapoints,
            datapoints: datapoints.map(d => [d[valueIndex], d[timeIndex]]),
            type: 'scatter'
          });
        });
      }
      return result;
    }
    return [];
  }
  /** 告警时间切换 */
  handleChangeTimeRange() {}
  /** 跳转数据检索 */
  handleToDataRetrieval() {
    const targets = this.detail.graph_panel?.targets;
    if (!!targets) {
      const { bizId } = this.$store.getters;
      const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
        this.detail.bk_biz_id || bizId
      }#/data-retrieval/?targets=${JSON.stringify(targets)}`;
      window.open(url, '__blank');
    }
  }

  // 事件及日志来源告警视图
  getSeriesViewComponent() {
    if (this.isMultivariateAnomalyDetection) {
      return <IntelligenceScene params={this.detail}></IntelligenceScene>;
    }
    /** 智能检测算法图表 */
    if (this.hasAIOpsDetection)
      return (
        <AiopsChartEvent
          detail={this.detail}
          detectionConfig={this.detectionConfig}
        />
      );
    /** 时序预测图表 */
    if (this.hasTimeSeriesForecasting)
      return (
        <TimeSeriesForecastingChart
          detail={this.detail}
          detectionConfig={this.detectionConfig}
        />
      );
    if (this.hasOutlierDetection) return <OutlierDetectionChart detail={this.detail} />;
    return (
      <div class='series-view-container'>
        <MonitorEchart
          ref='monitorEchart'
          height={220}
          title={this.chart.title}
          subtitle={this.chart.subtitle}
          key={this.detail.id}
          options={this.chartOption}
          errorMsg={this.errorMsg}
          empty-text={this.errorMsg?.length ? this.$t('查询数据错误') : this.$t('无数据')}
          chart-type={this.chart.chartType}
          hasTraceInfo={this.hasTraceSeries}
          curBizId={this.detail.bk_biz_id}
          traceInfoTimeRange={this.traceInfoTimeRange}
          on-data-zoom={this.dataZoom}
          get-alarm-status={this.getAlarmStatus}
          get-series-data={this.handleGetSeriesData}
          on-export-data-retrieval={this.handleToDataRetrieval}
        ></MonitorEchart>
      </div>
    );
  }

  // 源日志
  getSourceLogComponent() {
    const contentSlots = {
      default: props => props.row?.content || props.row?.['event.content'] || ''
    };
    const timeSlots = {
      default: props => dayjs.tz(props.row.time * 1000).format('YYYY-MM-DD HH:mm:ss')
    };
    return (
      <div class='source-log'>
        <div class='source-log-title'>{this.$t('源日志')}</div>
        <div class='source-log-tip'>
          <span class='icon-monitor icon-hint'></span>
          <span class='tip-text'>{this.$t('默认显示最近20条')}</span>
        </div>
        <div style={{ height: `${this.tableHeight}px` }}>
          <bk-table data={this.logData}>
            <bk-table-column
              label={this.$t('时间')}
              width={260}
              scopedSlots={timeSlots}
            ></bk-table-column>
            <bk-table-column
              label={this.$t('日志')}
              scopedSlots={contentSlots}
              showOverflowTooltip={true}
            ></bk-table-column>
          </bk-table>
        </div>
        {this.showLoadingBox ? (
          <div class='source-log-loading'>
            <LoadingBox></LoadingBox>
          </div>
        ) : undefined}
      </div>
    );
  }

  render() {
    return (
      <div class={['event-detail-viewinfo', { displaynone: !this.show }]}>
        {this.getSeriesViewComponent()}
        {this.getShowSourceLogData ? this.getSourceLogComponent() : undefined}
      </div>
    );
  }
}
