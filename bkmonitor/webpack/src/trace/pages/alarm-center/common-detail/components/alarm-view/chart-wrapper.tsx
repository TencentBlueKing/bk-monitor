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
import { type PropType, computed, defineComponent, provide, shallowRef } from 'vue';

import dayjs from 'dayjs';
import { transformDataKey, typeTools } from 'monitor-common/utils';
import { type IDetectionConfig, MetricType } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { useI18n } from 'vue-i18n';

import AiopsCharts from './echarts/aiops-charts';
import IntelligenceScene from './echarts/intelligence-scene';
import MonitorCharts from './echarts/monitor-charts';
import OutlierDetectionChart from './echarts/outlier-detection-chart';
import TimeSeriesForecastingChart from './echarts/time-series-forecasting-chart';

import type { AlarmDetail } from '@/pages/alarm-center/typings';
import type { LegendOptions } from '@/plugins/typings';

import './chart-wrapper.scss';

/** 算法类型常量 */
const ALGORITHM_TYPES = {
  INTELLIGENT_DETECT: 'IntelligentDetect',
  ABNORMAL_CLUSTER: 'AbnormalCluster',
  TIME_SERIES_FORECASTING: 'TimeSeriesForecasting',
} as const;

/** 图表颜色常量 */
const CHART_COLORS = {
  ANOMALY: '#E71818',
  FATAL_ALARM: '#e64545',
  TRIGGER_PHASE: '#DCDEE5',
  FATAL_PERIOD: '#F8B4B4',
  TRIGGER_PHASE_BG: 'rgba(155, 168, 194, 0.12)',
  FATAL_PERIOD_BG: 'rgba(234, 54, 54, 0.12)',
} as const;

export default defineComponent({
  name: 'ChartWrapper',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 图表划选后的时间范围 */
    const dataZoomTimeRange = shallowRef(null);
    provide('timeRange', dataZoomTimeRange);

    /** 是否为主机智能场景检测视图 */
    const isHostAnomalyDetection = computed(() => {
      return props.detail?.extra_info?.strategy?.items?.[0]?.algorithms?.[0].type === MetricType.HostAnomalyDetection;
    });

    const detectionConfig = computed<IDetectionConfig>(() => {
      const strategy = props.detail.extra_info?.strategy;
      const algorithms = strategy?.items?.[0]?.algorithms;
      if (!algorithms?.length) return null;
      const result = {
        unit: algorithms[0].unit_prefix,
        // @ts-expect-error
        unitType: strategy.items?.[0]?.query_configs?.[0]?.unit || '',
        unitList: [],
        connector: strategy.detects?.[0]?.connector as 'and' | 'or',
        data: algorithms.map(({ unit_prefix, ...item }) => displayDetectionRulesConfig(item)),
        query_configs: strategy?.items?.[0]?.query_configs,
      };
      return result;
    });

    /** 是否含有智能检测算法 */
    const hasAIOpsDetection = computed(
      () =>
        hasAlgorithmType(ALGORITHM_TYPES.INTELLIGENT_DETECT) &&
        detectionConfig.value?.query_configs?.[0]?.intelligent_detect?.result_table_id
    );

    /** 是否含有离群检测算法 */
    const hasOutlierDetection = computed(() => hasAlgorithmType(ALGORITHM_TYPES.ABNORMAL_CLUSTER));

    /** 是否含有时序预测算法 */
    const hasTimeSeriesForecasting = computed(() => hasAlgorithmType(ALGORITHM_TYPES.TIME_SERIES_FORECASTING));

    const monitorChartPanel = computed(() => {
      const { graph_panel } = props.detail;
      if (!graph_panel) return null;
      const [{ data: queryConfig }] = graph_panel.targets;
      if (queryConfig.extendMetricFields?.some(item => item.includes('is_anomaly'))) {
        queryConfig.function = { ...queryConfig.function, max_point_number: 0 };
      }
      const chartQueryConfig = transformDataKey(queryConfig, true);
      return new PanelModel({
        title: graph_panel.title || '',
        subTitle: graph_panel.subTitle || '',
        gridPos: {
          x: 16,
          y: 16,
          w: 8,
          h: 4,
        },
        id: 'alarm-trend-chart',
        type: 'graph',
        options: {},
        targets: [
          {
            datasource: 'time_series',
            dataType: 'time_series',
            api: 'alert_v2.alertGraphQuery',
            data: {
              bk_biz_id: props.detail.bk_biz_id,
              id: props.detail.id,
              ...chartQueryConfig,
            },
          },
        ],
      });
    });

    const legendOptions = computed<LegendOptions>(() => ({
      disabledLegendClick: [t('异常'), t('致命告警产生'), t('告警触发阶段'), t('致命告警时段')],
      legendIconMap: {
        [t('异常')]: 'circle-legend',
        [t('致命告警产生')]: 'icon-monitor icon-danger',
        [t('告警触发阶段')]: 'rect-legend',
        [t('致命告警时段')]: 'rect-legend',
      },
    }));

    /**
     * @description 检查是否包含指定类型的算法
     * @param {string} type 算法类型
     * @returns 是否包含该类型算法
     */
    const hasAlgorithmType = (type: string) => detectionConfig.value?.data?.some?.(item => item.type === type);

    /**
     * @description 处理检测规则配置，对配置项进行标准化处理
     * @param item 检测算法配置项
     * @returns 处理后的配置项
     */
    const displayDetectionRulesConfig = item => {
      const { config } = item;
      if (item.type === ALGORITHM_TYPES.INTELLIGENT_DETECT && !config.anomaly_detect_direct) {
        config.anomaly_detect_direct = 'all';
      }
      if (typeTools.isArray(config)) return item;

      for (const key of Object.keys(config)) {
        if (config[key] === null) config[key] = '';
      }
      return item;
    };

    /**
     * @description 格式化系列别名
     * @param {string} name 原始系列名称(可能存在占位变量，如：$time_offset)
     * @param {Record<string, any>} compareData 替换数据源
     * @returns 格式化后的系列名称
     */
    const formatSeriesAlias = (name: string, compareData: Record<string, any> = {}) => {
      if (!name) return name;
      let alias = name;

      for (const [key, val] of Object.entries(compareData)) {
        if (!val) continue;

        if (key === 'time_offset' && alias.includes('$time_offset')) {
          const timeMatch = val.match(/(-?\d+)(\w+)/);
          const replacement =
            timeMatch?.length > 2
              ? dayjs.tz().add(-timeMatch[1], timeMatch[2]).fromNow().replace(/\s*/g, '')
              : val.replace('current', t('当前'));
          alias = alias.replaceAll('$time_offset', replacement);
        } else if (typeof val === 'object') {
          for (const valKey of Object.keys(val).sort((a, b) => b.length - a.length)) {
            alias = alias.replaceAll(`$${key}_${valKey}`, val[valKey]);
          }
        } else {
          alias = alias.replaceAll(`$${key}`, val);
        }
      }

      return alias.replace(/(\|\s*)+\|/g, '|').replace(/\|$/g, '');
    };

    /**
     * @description 格式化图表数据，添加异常点、告警标记等辅助系列
     * @param data - 原始图表数据
     * @returns 包含异常标记、告警阶段等辅助系列的完整图表数据
     */
    const formatterData = data => {
      const { graph_panel } = props.detail;
      const [{ alias }] = graph_panel.targets;

      const series = data.series.map(s => ({
        ...s,
        alias: formatSeriesAlias(alias, { ...s, tag: s.dimensions }) || s.alias,
      }));

      const datapoints = series[0]?.datapoints;
      const max = datapoints?.reduce((prev, cur) => Math.max(prev, cur[0]), 0);
      const emptyDatapoints = datapoints?.map(item => [null, item[1]]) || [];
      const beginTime = props.detail.begin_time * 1000;
      const beginTimeStr = String(beginTime);
      const firstAnomalyTimeStr = String(props.detail.first_anomaly_time * 1000);
      const endTimeStr = String(
        props.detail.end_time ? props.detail.end_time * 1000 : datapoints[datapoints.length - 1][1]
      );

      // 为主要系列添加 markPoints 和 markTimeRange，利用 use-monitor-echarts 的处理逻辑
      if (series.length > 0) {
        const mainSeries = series[0];
        mainSeries.markPoints = [
          // 异常点
          ...datapoints
            .filter(item => props.detail.anomaly_timestamps.includes(Number(String(item[1]).slice(0, -3))))
            .map(item => ({
              value: item[1],
              xAxis: String(item[1]),
              yAxis: item[0],
              symbol: 'circle',
              symbolSize: 5,
              itemStyle: { color: CHART_COLORS.ANOMALY },
            })),
          // 致命告警产生点
          {
            value: beginTime,
            xAxis: beginTimeStr,
            yAxis: max === 0 ? 1 : max,
            symbol: 'circle',
            symbolSize: 0,
            label: {
              show: true,
              position: 'top',
              formatter: '\ue606',
              color: CHART_COLORS.FATAL_ALARM,
              fontSize: 18,
              fontFamily: 'icon-monitor',
            },
          },
        ];
        mainSeries.markTimeRange = [
          {
            from: firstAnomalyTimeStr,
            to: beginTimeStr,
            color: CHART_COLORS.TRIGGER_PHASE_BG,
          },
          {
            from: beginTimeStr,
            to: endTimeStr,
            color: CHART_COLORS.FATAL_PERIOD_BG,
          },
        ];
      }

      return {
        ...data,
        series: [
          ...series,
          // 辅助系列用于图例（透明线条）
          {
            type: 'line',
            alias: t('异常'),
            tooltip: { show: false },
            datapoints: emptyDatapoints,
            color: CHART_COLORS.ANOMALY,
            lineStyle: { opacity: 0 },
          },
          {
            type: 'line',
            alias: t('致命告警产生'),
            tooltip: { show: false },
            datapoints: emptyDatapoints,
            color: CHART_COLORS.FATAL_ALARM,
            lineStyle: { opacity: 0 },
          },
          {
            type: 'line',
            alias: t('告警触发阶段'),
            tooltip: { show: false },
            datapoints: emptyDatapoints,
            color: CHART_COLORS.TRIGGER_PHASE,
            lineStyle: { opacity: 0 },
          },
          {
            type: 'line',
            alias: t('致命告警时段'),
            tooltip: { show: false },
            datapoints: emptyDatapoints,
            color: CHART_COLORS.FATAL_PERIOD,
            lineStyle: { opacity: 0 },
            z: 1,
          },
        ],
      };
    };

    /**
     * @description 处理图表框选缩放事件
     * @param {[number, number]} val - 框选的时间范围
     */
    const handleDataZoomChange = (val: [number, number]) => {
      dataZoomTimeRange.value = val;
    };

    /**
     * @description 处理图表复位按钮点击回调事件
     */
    const handleRestore = () => {
      dataZoomTimeRange.value = null;
    };

    /**
     * @description 根据告警类型获取对应的图表组件
     * @returns 对应的图表组件 JSX
     */
    const getSeriesViewComponent = () => {
      // 主机智能场景检测
      if (isHostAnomalyDetection.value) {
        console.log('主机智能场景检测');
        return <IntelligenceScene detail={props.detail} />;
      }
      // 智能检测算法图表
      if (hasAIOpsDetection.value) {
        console.log('智能检测算法图表');
        return (
          <AiopsCharts
            detail={props.detail}
            detectionConfig={detectionConfig.value}
          />
        );
      }
      // 时序预测图表
      if (hasTimeSeriesForecasting.value) {
        console.log('时序预测图表');
        return (
          <TimeSeriesForecastingChart
            detail={props.detail}
            detectionConfig={detectionConfig.value}
          />
        );
      }
      if (hasOutlierDetection.value) {
        console.log('离群检测算法');
        return <OutlierDetectionChart detail={props.detail} />;
      }
      console.log('dddddddddddddd');
      return (
        <div class='series-view-container'>
          <MonitorCharts
            params={
              !dataZoomTimeRange.value
                ? {
                    start_time: undefined,
                    end_time: undefined,
                  }
                : {}
            }
            formatterData={formatterData}
            legendOptions={legendOptions.value}
            panel={monitorChartPanel.value}
            showRestore={dataZoomTimeRange.value}
            onDataZoomChange={handleDataZoomChange}
            onRestore={handleRestore}
          />
        </div>
      );
    };

    return {
      monitorChartPanel,
      getSeriesViewComponent,
    };
  },

  render() {
    return <div class={['alarm-view-chart-wrapper']}>{this.getSeriesViewComponent()}</div>;
  },
});
