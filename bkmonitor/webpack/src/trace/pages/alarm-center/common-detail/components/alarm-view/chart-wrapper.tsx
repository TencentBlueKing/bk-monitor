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
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { useI18n } from 'vue-i18n';

import AiopsCharts from './echarts/aiops-charts';
import MonitorCharts from './echarts/monitor-charts';

import type { AlarmDetail } from '@/pages/alarm-center/typings';
import type { LegendOptions } from '@/plugins/typings';
import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import './chart-wrapper.scss';

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

    const getShowSourceLogData = computed(() => {
      const sourceTypeLabels = [
        { sourceLabel: 'bk_log_search', typeLabel: 'time_series' },
        { sourceLabel: 'custom', typeLabel: 'event' },
        { sourceLabel: 'bk_monitor', typeLabel: 'event' },
        { sourceLabel: 'bk_log_search', typeLabel: 'log' },
        { sourceLabel: 'bk_monitor', typeLabel: 'log' },
      ];
      if (props.detail.extra_info?.strategy) {
        const { strategy } = props.detail.extra_info;
        const sourceLabel = strategy.items?.[0]?.query_configs?.[0]?.data_source_label;
        const typeLabel = strategy.items?.[0]?.query_configs?.[0]?.data_type_label;
        return sourceTypeLabels.some(item => sourceLabel === item.sourceLabel && typeLabel === item.typeLabel);
      }
      return false;
    });

    const displayDetectionRulesConfig = item => {
      const { config } = item;
      if (item.type === 'IntelligentDetect' && !config.anomaly_detect_direct) config.anomaly_detect_direct = 'all';
      const isArray = typeTools.isArray(config);
      if (isArray) return item;
      Object.keys(config).forEach(key => {
        const value = config[key];
        if (value === null) config[key] = '';
      });
      return item;
    };

    const detectionConfig = computed<IDetectionConfig>(() => {
      const strategy = props.detail.extra_info?.strategy;
      const algorithms = strategy?.items?.[0]?.algorithms;
      if (!algorithms?.length) return null;
      const result = {
        unit: algorithms[0].unit_prefix,
        unitType: strategy.items?.[0]?.query_configs?.[0]?.unit || '',
        unitList: [],
        connector: strategy.detects?.[0]?.connector,
        data: algorithms.map(({ unit_prefix, ...item }) => displayDetectionRulesConfig(item)),
        query_configs: strategy?.items?.[0]?.query_configs,
      };
      return result;
    });

    /** 是否含有智能检测算法 */
    const hasAIOpsDetection = computed(() => {
      return (
        detectionConfig.value?.data?.some?.(item => item.type === 'IntelligentDetect') &&
        detectionConfig.value?.query_configs?.[0]?.intelligent_detect?.result_table_id
      );
    });

    const showRestore = shallowRef(false);
    const dataZoomTimeRange = shallowRef(null);
    provide('timeRange', dataZoomTimeRange);

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

    const handleBuildLegend = (name, compareData = {}) => {
      if (!name) return name;
      let alias = name;
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
                : val.replace('current', t('当前'))
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
    };

    const legendOptions = computed<LegendOptions>(() => ({
      disabledLegendClick: [t('异常'), t('致命告警产生'), t('告警触发阶段'), t('致命告警时段')],
      legendIconMap: {
        [t('异常')]: 'circle-legend',
        [t('致命告警产生')]: 'icon-monitor icon-danger',
        [t('告警触发阶段')]: 'rect-legend',
        [t('致命告警时段')]: 'rect-legend',
      },
    }));

    /** 格式化数据 */
    const formatterData = data => {
      const { graph_panel } = props.detail;
      const [{ alias }] = graph_panel.targets;

      const series = data.series.map(s => ({
        ...s,
        alias: handleBuildLegend(alias, { ...s, tag: s.dimensions }) || s.alias,
      }));

      const datapoints = series[0]?.datapoints;
      const max = datapoints?.reduce((prev, cur) => Math.max(prev, cur[0]), 0);
      return {
        ...data,
        series: [
          ...series,
          {
            type: 'scatter',
            datapoints: datapoints.map(item => {
              const value = props.detail?.anomaly_timestamps.includes(Number(String(item[1]).slice(0, -3)))
                ? item[0]
                : null;
              return [value, item[1]];
            }),
            alias: t('异常'),
            symbolSize: 5,
            color: '#E71818',
            itemStyle: {
              color: '#E71818',
            },
            tooltip: {
              show: false,
            },
          },
          {
            type: 'line',
            alias: t('致命告警产生'),
            tooltip: {
              show: false,
            },
            color: '#e64545',
            lineStyle: {
              opacity: 0,
            },
            yAxisIndex: 1,
            markPoint: {
              symbol: 'circle',
              symbolSize: 0,
              label: {
                show: true,
                position: 'top',
                formatter: '\ue606',
                color: '#e64545',
                fontSize: 18,
                fontFamily: 'icon-monitor',
              },
              data: [
                {
                  coord: [String(props.detail.begin_time * 1000), max === 0 ? 1 : max],
                },
              ],
            },
            datapoints,
          },
          {
            type: 'line',
            alias: t('告警触发阶段'),
            tooltip: {
              show: false,
            },
            datapoints: datapoints.map(item => [null, item[1]]) || [],
            color: '#DCDEE5',
            markArea: {
              silent: true,
              itemStyle: {
                color: 'rgba(155, 168, 194, 0.12)',
              },
              data: [
                [
                  {
                    xAxis: String(props.detail?.first_anomaly_time * 1000),
                  },
                  {
                    xAxis: String(props.detail?.begin_time * 1000),
                  },
                ],
              ],
            },
          },
          {
            type: 'line',
            alias: t('致命告警时段'),
            tooltip: {
              show: false,
            },
            datapoints: datapoints.map(item => [null, item[1]]) || [],
            color: '#F8B4B4',
            markArea: {
              silent: true,
              itemStyle: {
                color: 'rgba(234, 54, 54, 0.12)',
              },
              data: [
                [
                  {
                    xAxis: String(props.detail?.begin_time * 1000),
                  },
                  {
                    xAxis: String(
                      props.detail?.end_time ? props.detail?.end_time * 1000 : datapoints[datapoints.length - 1][1]
                    ),
                  },
                ],
              ],
            },
            z: 1,
          },
        ],
      };
    };

    /** 格式化请求参数 */
    const formatterParams = params => {
      /** 没有框选不进行时间范围过滤 */
      if (!dataZoomTimeRange.value) {
        delete params.start_time;
        delete params.end_time;
      }
      return params;
    };

    const handleDataZoomChange = (val: any[]) => {
      dataZoomTimeRange.value = val;
      showRestore.value = true;
    };

    const handleRestore = () => {
      showRestore.value = false;
      dataZoomTimeRange.value = null;
    };

    // 事件及日志来源告警视图
    const getSeriesViewComponent = () => {
      // if (isHostAnomalyDetection.value) {
      //   return <IntelligenceScene params={props.detail} />;
      // }
      // /** 智能检测算法图表 */
      if (hasAIOpsDetection.value)
        return (
          <AiopsCharts
            detail={props.detail}
            detectionConfig={detectionConfig.value}
          />
        );
      // /** 时序预测图表 */
      // if (hasTimeSeriesForecasting.value)
      //   return (
      //     <TimeSeriesForecastingChart
      //       detail={props.detail}
      //       detectionConfig={detectionConfig.value}
      //     />
      //   );
      // if (hasOutlierDetection.value) return <OutlierDetectionChart detail={props.detail} />;
      return (
        <div class='series-view-container'>
          <MonitorCharts
            formatterOptions={{
              seriesData: formatterData,
              params: formatterParams,
            }}
            legendOptions={legendOptions.value}
            panel={monitorChartPanel.value}
            showRestore={showRestore.value}
            onDataZoomChange={handleDataZoomChange}
            onRestore={handleRestore}
          />
        </div>
      );
    };

    return {
      monitorChartPanel,
      getShowSourceLogData,
      getSeriesViewComponent,
    };
  },

  render() {
    return <div class={['alarm-view-chart-wrapper']}>{this.getSeriesViewComponent()}</div>;
  },
});
