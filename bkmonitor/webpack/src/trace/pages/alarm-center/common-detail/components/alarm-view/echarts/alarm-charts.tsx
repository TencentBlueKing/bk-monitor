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
  toRef,
  useTemplateRef,
} from 'vue';

import dayjs from 'dayjs';
import { transformDataKey } from 'monitor-common/utils';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { fitPosition } from 'monitor-ui/chart-plugins/utils';
import { useI18n } from 'vue-i18n';

import { msToSeconds } from '../../../../../../utils';
import { useChartOperation } from '../../../../../trace-explore/components/explore-chart/use-chart-operation';
import { type AlarmDetail, type AlertScatterClickEvent, AlertLevelEnum } from '../../../../typings';
import AlarmChartEventDetail from './alarm-chart-event-detail';
import MonitorCharts from './monitor-charts';

import type { ChartTitleMenuType, IDataQuery, ILegendItem, IMenuItem } from '../../../../../../plugins/typings';
import type { DateValue } from '@blueking/date-picker';
import type { ExploreTableRequestParams } from 'monitor-pc/pages/event-explore/typing';
import type { LegendActionType } from 'monitor-ui/chart-plugins/typings/chart-legend';

import './alarm-charts.scss';

/** 异常点颜色 */
const ANOMALY_COLOR = '#E71818';
/** 事件散点图颜色 */
const EVENT_SCATTER_COLOR = '#49C4CC';
/** 告警产生图标配置 */
const ALARM_ICON_CONFIG = {
  [AlertLevelEnum.FATAL]: {
    alias: window.i18n.t('致命告警产生'),
    color: '#e64545',
    icon: 'icon-monitor icon-danger',
    unicode: '\ue606',
  },
  [AlertLevelEnum.WARNING]: {
    alias: window.i18n.t('预警告警产生'),
    color: '#F59500',
    icon: 'icon-monitor icon-mind-fill',
    unicode: '\ue670',
  },
  [AlertLevelEnum.REMIND]: {
    alias: window.i18n.t('提醒告警产生'),
    color: '#3A84FF',
    icon: 'icon-monitor icon-tips',
    unicode: '\ue602',
  },
} as const;
/** 告警触发阶段颜色配置 */
const TRIGGER_PHASE_COLOR_CONFIG = {
  alias: window.i18n.t('告警触发阶段'),
  timeRangeColor: 'rgba(155, 168, 194, 0.12)',
  lengthColor: '#DCDEE5',
  icon: 'rect-legend',
} as const;
/** 告警时段配置映射表 */
const TIME_RANGE_CONFIG_MAP = {
  [AlertLevelEnum.FATAL]: {
    alias: window.i18n.t('致命告警时段'),
    timeRangeColor: 'rgba(231, 24, 24, 0.12)',
    lengthColor: '#F8B4B4',
    icon: 'rect-legend',
  },
  [AlertLevelEnum.WARNING]: {
    alias: window.i18n.t('预警告警时段'),
    timeRangeColor: 'rgba(255, 184, 72, 0.12)',
    lengthColor: '#FCE5C0',
    icon: 'rect-legend',
  },
  [AlertLevelEnum.REMIND]: {
    alias: window.i18n.t('提醒告警时段'),
    timeRangeColor: 'rgba(58, 132, 255, 0.12)',
    lengthColor: '#E1ECFF',
    icon: 'rect-legend',
  },
} as const;

export default defineComponent({
  name: 'AlarmCharts',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
    /** 业务ID */
    bizId: {
      type: Number,
    },
    /** 默认时间范围 */
    defaultTimeRange: {
      type: Array as unknown as PropType<DateValue>,
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 事件气泡详情组件 */
    const alertEventChartDetailRef =
      useTemplateRef<InstanceType<typeof AlarmChartEventDetail>>('alertEventChartDetailRef');
    /** 事件查询配置 */
    const eventQueryConfig = shallowRef<ExploreTableRequestParams>(null);
    /** 事件详情弹窗显示位置 */
    const eventDetailPopupPosition = shallowRef({ left: 0, top: 0 });
    /** 散点点击事件的详情数据 */
    const scatterClickEventData = shallowRef<AlertScatterClickEvent>({});
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');
    const { timeRange, showRestore, handleDataZoomChange, handleRestore } = useChartOperation(
      toRef(props, 'defaultTimeRange')
    );
    provide('refreshImmediate', refreshImmediate);
    provide('timeRange', timeRange);

    /** 图表请求参数（框选时间范围） */
    const chartParams = computed(() => (showRestore.value ? {} : { start_time: undefined, end_time: undefined }));
    /** 是否为事件或日志类型告警 */
    const isEventOrLogAlarm = computed(() => ['event', 'log'].includes(props.detail?.data_type));
    /** 图表面板配置 */
    const monitorChartPanel = computed(() => {
      // 安全检查：确保 graph_panel 和 targets 存在且有数据
      const graphPanel = props.detail?.graph_panel;
      const firstTarget = graphPanel?.targets?.[0];
      if (!firstTarget?.data) return new PanelModel({});
      // 浅拷贝 queryConfig，避免修改原始 props 数据
      const queryConfig = { ...(firstTarget.data as Record<string, any>) };
      // 异常检测场景需要禁用采样
      if (queryConfig.extendMetricFields?.some((item: string) => item.includes('is_anomaly'))) {
        queryConfig.function = { ...queryConfig.function, max_point_number: 0 };
      }
      const [startTime, endTime] = timeRange.value;
      // // 暂定 12个 气泡
      const eventScatterInterval = Math.ceil((msToSeconds(endTime) - msToSeconds(startTime)) / 12);

      return new PanelModel({
        title: graphPanel.title || '',
        subTitle: graphPanel.subTitle || '',
        gridPos: { x: 16, y: 16, w: 8, h: 4 },
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
              ...transformDataKey(queryConfig, true),
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
              interval: eventScatterInterval,
            },
          },
        ],
      });
    });

    /** 图表菜单功能 */
    const menuList = computed<ChartTitleMenuType[]>(() => {
      if (isEventOrLogAlarm.value) {
        return ['screenshot'];
      }
      return ['screenshot', 'explore'];
    });

    /**
     * @description 格式化图表数据，添加异常点、告警标记等辅助系列
     * @param data - 原始图表数据
     * @param {IDataQuery} target - 图表配置
     */
    const formatterData = (data, target: IDataQuery) => {
      // 事件时序接口单独处理
      if (target.alias === 'alertEventTs') {
        eventQueryConfig.value = data?.query_config ?? {};
        return data;
      }

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

        // 设置标记点（异常点 + 致命告警图标）
        mainSeries.markPoints = [
          ...(isEventOrLogAlarm.value && mainSeries?.type === 'bar'
            ? []
            : datapoints
                .filter(item => props.detail.anomaly_timestamps.includes(Number(String(item[1]).slice(0, -3))))
                .map(item => ({
                  value: item[1],
                  xAxis: String(item[1]),
                  yAxis: item[0],
                  symbol: 'circle',
                  symbolSize: 5,
                  itemStyle: { color: ANOMALY_COLOR },
                }))),
          {
            value: beginTime,
            xAxis: beginTimeStr,
            yAxis: yMax || 1,
            symbol: 'circle',
            symbolSize: 0,
            label: {
              show: true,
              position: 'top',
              formatter: ALARM_ICON_CONFIG[props.detail.severity]?.unicode,
              color: ALARM_ICON_CONFIG[props.detail.severity]?.color,
              fontSize: 16,
              fontFamily: 'icon-monitor',
            },
          },
        ];
        mainSeries.markTimeRange = [
          { from: firstAnomalyTimeStr, to: beginTimeStr, color: TRIGGER_PHASE_COLOR_CONFIG.timeRangeColor },
          { from: beginTimeStr, to: endTimeStr, color: TIME_RANGE_CONFIG_MAP[props.detail.severity]?.timeRangeColor },
        ];
      }

      return {
        ...data,
        series: series,
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
      if (isEventOrLogAlarm.value && series?.type === 'bar') {
        series.itemStyle = { ...(series?.itemStyle ?? {}), color: '#3A84FF' };
        for (const ponit of props.detail.anomaly_timestamps) {
          const index = series.datapoints.findIndex(item => Number(String(item[1]).slice(0, -3)) === ponit);
          series.data[index] = {
            ...series.data[index],
            itemStyle: { color: ANOMALY_COLOR },
          };
        }
      }
      return series;
    };

    /**
     * @description 创建事件散点图series配置
     * @param series 原始series数据
     */
    const formatterEventScatterSeries = series => {
      const scaleList = scaleArrayToRange(series.datapoints.map(item => item[0]));
      return {
        ...series,
        type: 'scatter',
        name: t('事件'),
        symbolSize: (_, p) => {
          const scaledSize = scaleList[p.dataIndex];
          return scaledSize ? Math.max(scaledSize, 6) : scaledSize;
        },
        showSymbol: true,
        z: 10,
        emphasis: { scale: 1.666 },
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(25, 100, 150, 0.5)',
          shadowOffsetY: 5,
          color: EVENT_SCATTER_COLOR,
          opacity: 0.5,
        },
      };
    };

    /**
     * @description 图表series处理
     */
    const formatterSeries = seriesList => {
      return seriesList
        .map(series => {
          if (series.time_offset === 'current') return formatterGraphQueryCurrentSeries(series);
          if (series.alias === 'alertEventTs') return formatterEventScatterSeries(series);
          return series;
        })
        .filter(Boolean);
    };

    /**
     * @description 为事件散点图创建独立坐标轴
     */
    const createAxisForEventScatter = options => {
      const eventSeriesIndex = options.series.findIndex(item => item.alias === 'alertEventTs');
      if (eventSeriesIndex === -1) return;

      const eventSeries = options.series[eventSeriesIndex];
      const hasEventData = eventSeries.datapoints.some(e => e[0] > 0);
      const shouldCreateNewXAxis = eventSeries.xAxisIndex === 0;

      // 为事件散点图创建独立的x轴
      if (shouldCreateNewXAxis) {
        options.xAxis.push({
          show: false,
          type: 'category',
          data: eventSeries.datapoints.map(e => e[1]),
        });
      }
      // 为事件散点图创建独立的y轴
      options.yAxis.push({
        scale: true,
        show: hasEventData,
        position: 'right',
        max: 'dataMax',
        min: 0,
        splitNumber: 2,
        minInterval: 1,
        z: 3,
        splitLine: { show: false },
      });

      eventSeries.xAxisIndex = shouldCreateNewXAxis ? options.xAxis.length - 1 : eventSeries.xAxisIndex;
      eventSeries.yAxisIndex = options.yAxis.length - 1;
    };

    /**
     * @description 自定义图表options配置
     */
    const formatterOptions = options => {
      options.color = COLOR_LIST;
      options.grid.top = 24;
      const isBar = options.series[0].type === 'bar';

      createAxisForEventScatter(options);

      // 为x轴添加刻度线
      Object.assign(options.xAxis[0], {
        boundaryGap: isBar,
        axisTick: { show: true, alignWithLabel: true },
        axisLine: { show: true },
        splitLine: { show: true, alignWithLabel: isBar },
        axisLabel: { ...options.xAxis[0].axisLabel, align: 'center', showMinLabel: true, showMaxLabel: true },
      });

      // 为y轴添加刻度线
      for (const [index, item] of options.yAxis.entries()) {
        const isMainYAxis = index === 0;
        Object.assign(item, {
          axisTick: { show: true },
          axisLine: { show: true },
          ...(isMainYAxis && { splitLine: { show: true } }),
        });
      }

      // 检测是否存在右侧y轴
      const hasRightYAxis = options.yAxis.some(axis => axis.position === 'right');
      // 当不存在右侧y轴时，创建一个右侧y轴来显示右边框
      if (!hasRightYAxis) {
        options.yAxis.push({
          show: true,
          position: 'right',
          axisTick: { show: false },
          axisLine: { show: true },
          axisLabel: { show: false },
          splitLine: { show: false },
          z: 3,
        });
      }

      return options;
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
      let eventLegend = null;
      let legendList = legendData.reduce((prev, curr) => {
        if (curr.name === t('事件')) {
          eventLegend = curr;
          return prev;
        }
        return [...prev, curr];
      }, []);

      legendList = [
        ...legendList,
        {
          name: t('异常'),
          show: true,
          icon: 'circle-legend',
          color: ANOMALY_COLOR,
          disabled: true,
        },
        {
          name: ALARM_ICON_CONFIG[props.detail.severity]?.alias,
          show: true,
          icon: ALARM_ICON_CONFIG[props.detail.severity]?.icon,
          color: ALARM_ICON_CONFIG[props.detail.severity]?.color,
          disabled: true,
        },
        {
          name: TRIGGER_PHASE_COLOR_CONFIG.alias,
          show: true,
          icon: TRIGGER_PHASE_COLOR_CONFIG.icon,
          color: TRIGGER_PHASE_COLOR_CONFIG.lengthColor,
          disabled: true,
        },
        {
          name: TIME_RANGE_CONFIG_MAP[props.detail.severity]?.alias,
          show: true,
          icon: TIME_RANGE_CONFIG_MAP[props.detail.severity]?.icon,
          color: TIME_RANGE_CONFIG_MAP[props.detail.severity]?.lengthColor,
          disabled: true,
        },
      ];
      if (eventLegend) {
        legendList.push({
          ...eventLegend,
          disabled: true,
          icon: 'event-legend-icon',
        });
      }
      return legendList;
    };

    /** 图例点击事件处理 */
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
      return legendDataCopy;
    };

    /**
     * @description 处理散点点击事件
     */
    const handleScatterClick = params => {
      if (params.seriesType !== 'scatter') return;

      const { name, event } = params;
      const { clientX, clientY } = event.event;

      // 设置初始位置（保持原有偏移逻辑）
      const initialPosition = {
        left: clientX + 12,
        top: clientY + 12,
      };

      // 使用 fitPosition 进行边界检测和位置调整
      // 弹窗固定宽度720px，高度使用默认值200px进行初步计算
      const adjustedPosition = fitPosition(initialPosition, 720, 200);

      eventDetailPopupPosition.value = adjustedPosition;
      scatterClickEventData.value = {
        bizId: props.bizId,
        alert_id: props.detail?.id,
        start_time: Number(name) / 1000,
        query_config: eventQueryConfig.value,
      };

      // 使用 nextTick 在DOM更新后进行精确的高度调整
      nextTick(() => {
        if (alertEventChartDetailRef.value?.getComponentHeight) {
          const actualHeight = alertEventChartDetailRef.value.getComponentHeight();
          // 如果实际高度与预估高度差异较大，重新计算位置
          if (Math.abs(actualHeight - 200) > 50) {
            const refinedPosition = fitPosition(initialPosition, 720, actualHeight);
            eventDetailPopupPosition.value = refinedPosition;
          }
        }
      });
    };

    /**
     * @description 点击事件详情弹窗外部区域时关闭弹窗
     * @param event 点击事件
     */
    const handleCloseEventDetailPopup = (event: MouseEvent) => {
      // 弹窗未显示时跳过
      if (!eventDetailPopupPosition.value.left) return;
      if (alertEventChartDetailRef.value?.$el?.contains(event.target)) return;

      nextTick(() => {
        eventDetailPopupPosition.value = { left: 0, top: 0 };
      });
    };

    /** 菜单点击事件 */
    const handleMenuClick = (item: IMenuItem) => {
      switch (item.id) {
        case 'explore': {
          const targets = props.detail.graph_panel?.targets;
          if (targets) {
            // 表达式和表达因子都存在的时，默认隐藏表达因子 display: false
            if (targets[0]?.data?.query_configs && targets[0]?.data?.expression?.length > 1) {
              targets[0].data.query_configs = targets[0].data.query_configs.map(item => ({
                ...item,
                display: false,
              }));
            }
            const url = `${location.origin}${location.pathname.toString().replace('fta/', '')}?bizId=${
              props.detail.bk_biz_id
            }#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(targets))}`;
            window.open(url, '_blank');
          }
          break;
        }
      }
    };

    onMounted(() => document.addEventListener('mousedown', handleCloseEventDetailPopup));
    onUnmounted(() => document.removeEventListener('mousedown', handleCloseEventDetailPopup));

    return {
      menuList,
      monitorChartPanel,
      showRestore,
      handleDataZoomChange,
      handleRestore,
      formatterData,
      formatterSeries,
      formatterOptions,
      customLegendData,
      handleSelectLegend,
      handleScatterClick,
      eventDetailPopupPosition,
      scatterClickEventData,
      handleMenuClick,
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
            options: this.formatterOptions,
            series: this.formatterSeries,
          }}
          customMenuClick={['explore']}
          menuList={this.menuList}
          panel={this.monitorChartPanel}
          showAddMetric={false}
          showRestore={this.showRestore}
          onClick={this.handleScatterClick}
          onDataZoomChange={this.handleDataZoomChange}
          onMenuClick={this.handleMenuClick}
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
