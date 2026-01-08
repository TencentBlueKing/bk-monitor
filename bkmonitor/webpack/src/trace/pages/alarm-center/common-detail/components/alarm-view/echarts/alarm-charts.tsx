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

import {
  type PropType,
  computed,
  defineComponent,
  nextTick,
  onMounted,
  onUnmounted,
  provide,
  shallowRef,
  useTemplateRef,
} from 'vue';

import { get } from '@vueuse/core';
import dayjs from 'dayjs';
import { transformDataKey } from 'monitor-common/utils';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import AlarmChartEventDetail from './alarm-chart-event-detail';
import MonitorCharts from './monitor-charts';
import { useChartOperation } from '@/pages/trace-explore/components/explore-chart/use-chart-operation';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { AlarmDetail } from '@/pages/alarm-center/typings';
import type { IDataQuery, ILegendItem } from '@/plugins/typings';
import type { LegendActionType } from 'monitor-ui/chart-plugins/typings/chart-legend';

import './alarm-charts.scss';

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
  name: 'AlarmCharts',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 事件气泡详情组件 */
    const alertEventChartDetailRef =
      useTemplateRef<InstanceType<typeof AlarmChartEventDetail>>('alertEventChartDetailRef');
    /** 事件详情弹窗显示位置 */
    const eventDetailPopupPosition = shallowRef({ left: 0, top: 0 });
    /** 散点点击事件的详情数据 */
    const scatterClickEventData = shallowRef({});

    const { timeRange: defaultTimeRange } = storeToRefs(useAlarmCenterDetailStore());

    const { timeRange, showRestore, handleDataZoomChange, handleRestore } = useChartOperation(get(defaultTimeRange));
    provide('timeRange', timeRange);

    const chartParams = computed(() => {
      return !showRestore.value
        ? {
            start_time: undefined,
            end_time: undefined,
          }
        : {};
    });

    /**
     * 是否为事件或日志告警
     */
    const isEventOrLogAlarm = computed(() => {
      return props.detail?.data_type === 'event' || props.detail?.data_type === 'log';
    });

    const legendOptions = {
      [t('异常')]: {
        id: 'anomaly',
        disabled: true,
        icon: 'circle-legend',
      },
      [t('致命告警产生')]: {
        id: 'fatal_alarm',
        disabled: true,
        icon: 'icon-monitor icon-danger',
      },
      [t('告警触发阶段')]: {
        id: 'trigger_phase',
        disabled: true,
        icon: 'rect-legend',
      },
      [t('致命告警时段')]: {
        id: 'fatal_period',
        disabled: true,
        icon: 'rect-legend',
      },
    };

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
              ...chartParams.value,
            },
          },
          {
            alias: 'alertEventTs',
            datasource: 'time_series',
            dataType: 'time_series',
            api: 'alert_v2.alertEventTs',
            data: {
              bk_biz_id: props.detail.bk_biz_id,
              alert_id: props.detail.id,
            },
          },
        ],
      });
    });

    /**
     * @description 格式化图表数据，添加异常点、告警标记等辅助系列
     * @param data - 原始图表数据
     * @param {IDataQuery} target - 图表配置
     */
    const formatterData = (data, target: IDataQuery) => {
      // 事件时序接口不需要处理
      if (target.alias === 'alertEventTs') return data;
      const { graph_panel } = props.detail;
      const [{ alias }] = graph_panel.targets;

      const series = data.series.map(s => ({
        ...s,
        thresholds: [],
        alias: formatSeriesAlias(alias, { ...s, tag: s.dimensions }) || s.alias,
      }));

      const datapoints = series[0]?.datapoints;
      /** 计算Y轴的最大值 */
      const yMax = series
        .reduce((pre, cur) => [...pre, ...(cur.datapoints || [])], [])
        .reduce((prev, cur) => Math.max(prev, cur[0]), 0);
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
        /**
         * 异常告警点时间不在图表x轴上，补充告警点的时间
         * 事件和日志的告警点y轴设置为1，其他告警y轴设置为0
         */
        for (const anomaly of props.detail.anomaly_timestamps) {
          const index = datapoints.findIndex(item => Number(String(item[1]).slice(0, -3)) >= anomaly);
          if (index > -1 && Number(String(datapoints[index][1]).slice(0, -3)) !== anomaly) {
            datapoints.splice(index, 0, [isEventOrLogAlarm.value ? 1 : 0, anomaly * 1000]);
          }
        }

        /**
         * 填充不在图表时间轴上的告警面积分割点
         */
        const markAreaPoint = [firstAnomalyTimeStr, beginTimeStr, endTimeStr];
        for (const point of markAreaPoint) {
          const index = datapoints.findIndex(item => item[1] >= Number(point));
          if (index > -1 && datapoints[index][1] !== Number(point)) {
            datapoints.splice(index, 0, [0, Number(point)]);
          }
        }

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
            yAxis: yMax === 0 ? 1 : yMax,
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
     * @description 将数组值缩放到指定范围
     * @param inputArray 输入数组
     * @param minRange 最小范围
     * @param maxRange 最大范围
     */
    const scaleArrayToRange = (inputArray: number[], minRange = 4, maxRange = 16): number[] => {
      if (inputArray.length === 0) {
        return [];
      }
      const minInput = Math.min(...inputArray);
      const maxInput = Math.max(...inputArray);
      if (minInput === maxInput) {
        return inputArray.map(value => (value < 1 ? 0 : minRange));
      }
      return inputArray.map(value => {
        if (value < 1) {
          return 0;
        }
        const scaledValue = ((value - minInput) / (maxInput - minInput)) * (maxRange - minRange) + minRange;
        return Math.max(minRange, Math.min(maxRange, scaledValue));
      });
    };

    /**
     * @description 处理series， 事件和日志告警对于告警点的柱状图需要变颜色
     */
    const formatterGraphQueryCurrentSeries = series => {
      /** 事件告警 */
      if (isEventOrLogAlarm.value && series.length > 0) {
        for (const ponit of props.detail.anomaly_timestamps) {
          const index = series.datapoints.findIndex(item => Number(String(item[1]).slice(0, -3)) === ponit);
          series.data[index] = {
            ...series.data[index],
            itemStyle: { color: CHART_COLORS.ANOMALY },
          };
        }
      }
      return series;
    };

    /**
     * @description 图表series处理
     */
    const formatterSeries = seriesList => {
      return seriesList
        .map((series, i) => {
          if (i === 0) return formatterGraphQueryCurrentSeries(series);
          if (series.alias !== 'alertEventTs') return series;
          const datapoints = series.datapoints.filter(item => item[0]);
          if (!datapoints.length) return undefined;
          const scaleList = scaleArrayToRange(datapoints.map(item => item[0]));
          return {
            ...series,
            type: 'scatter',
            name: t('事件'),
            symbolSize: (_, p) => {
              const scaledSize = scaleList[p.dataIndex];
              // 确保散点有足够的点击热区，最小 8px
              return Math.max(scaledSize || 6, 6);
            },
            showSymbol: true, // 确保散点可见
            z: 10,
            emphasis: {
              scale: 1.666,
            },
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(25, 100, 150, 0.5)',
              shadowOffsetY: 5,
              color: '#49C4CC',
            },
          };
        })
        .filter(Boolean);
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

    /** 自定义图例数据 */
    const customLegendData = (legendData: ILegendItem[]): ILegendItem[] => {
      return legendData.map(legend => ({
        ...legend,
        legendId: legendOptions[legend.name]?.id,
        disabled: legendOptions[legend.name]?.disabled,
        icon: legendOptions[legend.name]?.icon,
      }));
    };

    /** 图例点击事件 */
    const handleSelectLegend = (
      actionType: LegendActionType,
      item: ILegendItem,
      legendData: ILegendItem[]
    ): ILegendItem[] => {
      let legendDataCopy = [];
      if (actionType === 'shift-click') {
        legendDataCopy = legendData.map(l => {
          if (l.name === item.name) {
            return {
              ...l,
              show: l.disabled || !l.show,
            };
          }
          return l;
        });
      } else if (actionType === 'click') {
        const hasOtherShow = legendData
          .filter(item => !item.hidden)
          .some(set => set.name !== item.name && set.show && !set.disabled);
        legendDataCopy = legendData.map(l => {
          return {
            ...l,
            show: l.disabled || l.name === item.name || !hasOtherShow,
          };
        });
      }
      /** 异常，告警致命产生，告警触发阶段，知名告警时段 图例显隐跟随'当前'图例 */
      const legendIds = ['anomaly', 'fatal_alarm', 'trigger_phase', 'fatal_period'];
      for (const legend of legendDataCopy) {
        if (legendIds.includes(legend.legendId)) {
          legend.show = legendDataCopy[0].show;
        }
      }
      console.log(legendDataCopy);
      return legendDataCopy;
    };

    /**
     * @description 处理散点点击事件
     */
    const handleScatterClick = params => {
      // 处理散点点击事件，显示事件详情弹窗
      if (params.seriesType !== 'scatter') return;
      const { name, event } = params;
      const startTime = Number(name);
      // 计算弹窗位置
      const { clientX, clientY } = event.event;
      eventDetailPopupPosition.value = {
        left: clientX + 12,
        top: clientY + 12,
      };
      // 设置事件项数据
      scatterClickEventData.value = {
        alert_id: props.detail?.id,
        start_time: startTime / 1000,
      };
    };

    /**
     * @description 点击事件详情弹窗外部区域时关闭弹窗
     * @param event 点击事件
     */
    const handleCloseEventDetailPopup = event => {
      // 弹窗未显示时跳过
      if (!eventDetailPopupPosition.value.left) return;
      const target = event.target;
      const menuEl = alertEventChartDetailRef.value?.$el;
      // 检测点击目标是否在弹窗内
      if (menuEl?.contains(target)) return;
      nextTick(() => {
        eventDetailPopupPosition.value = {
          left: 0,
          top: 0,
        };
      });
    };

    onMounted(() => {
      document.addEventListener('mousedown', handleCloseEventDetailPopup);
    });

    onUnmounted(() => {
      document.removeEventListener('mousedown', handleCloseEventDetailPopup);
    });

    return {
      monitorChartPanel,
      showRestore,
      handleDataZoomChange,
      handleRestore,
      formatterData,
      formatterSeries,
      customLegendData,
      handleSelectLegend,
      handleScatterClick,
      eventDetailPopupPosition,
      scatterClickEventData,
    };
  },
  render() {
    return (
      <div class='alarm-charts'>
        <MonitorCharts
          customLegendOptions={{
            legendData: this.customLegendData,
            legendClick: this.handleSelectLegend,
          }}
          customOptions={{
            formatterData: this.formatterData,
            options: options => {
              options.color = COLOR_LIST;
              options.grid.top = 24;
              return options;
            },
            series: this.formatterSeries,
          }}
          menuList={['screenshot', 'explore']}
          panel={this.monitorChartPanel}
          showRestore={this.showRestore}
          onClick={this.handleScatterClick}
          onDataZoomChange={this.handleDataZoomChange}
          onRestore={this.handleRestore}
        />

        {/* 散点点击事件详情弹窗 */}
        {this.eventDetailPopupPosition?.left > 0 && (
          <AlarmChartEventDetail
            ref='alertEventChartDetailRef'
            eventItem={this.scatterClickEventData}
            position={this.eventDetailPopupPosition}
          />
        )}
      </div>
    );
  },
});
