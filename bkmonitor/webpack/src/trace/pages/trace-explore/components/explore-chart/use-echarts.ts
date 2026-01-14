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

import { type MaybeRef, type Ref, inject, watch } from 'vue';
import { shallowRef } from 'vue';
import { computed } from 'vue';

import { get } from '@vueuse/core';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/cancel';
import { random } from 'monitor-common/utils';
import { arraysEqual } from 'monitor-common/utils/equal';
import { COLOR_LIST_BAR } from 'monitor-ui/chart-plugins/constants/charts';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { useChartTooltips } from './use-chart-tooltips';
import {
  handleGetMinPrecision,
  handleSetMarkPoints,
  handleSetMarkTimeRange,
  handleSetThresholdArea,
  handleSetThresholdLine,
} from './utils';

import type { EchartSeriesItem, FormatterFunc, SeriesItem } from './types';
import type { IDataQuery } from '@/plugins/typings';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

/** 图表交互状态配置 */
export interface ChartInteractionState {
  /** 所有联动图表中存在有一个图表触发 hover 是否展示所有联动图表的 tooltip(默认 false) */
  hoverAllTooltips?: MaybeRef<boolean>;
  /** 当前鼠标是否 hover 在图表区域 */
  isMouseOver: MaybeRef<boolean>;
}
export interface CustomOptions {
  formatterData?: (formatter: any, target: IDataQuery) => any;
  options?: (options: any) => any;
  series?: (series: EchartSeriesItem[]) => EchartSeriesItem[];
}

/**
 * @function useAlertEcharts 告警图表 ECharts Hook
 * @description 用于管理告警指标图表的数据获取、配置生成和交互状态
 * @param panel - 图表面板配置，包含 targets、options 等图表配置信息
 * @param chartRef - 图表 DOM 元素引用，用于 tooltip 定位
 * @param $api - API 模块对象，用于调用后端接口获取图表数据
 * @param params - 请求参数，会与 target.data 合并后发送请求
 * @param customOptions - 数据格式化函数，用于需要自定义逻辑
 * @param interactionState - 图表交互状态配置，控制 tooltip 联动等行为
 */
export const useEcharts = (
  panel: MaybeRef<PanelModel>,
  chartRef: Ref<HTMLElement>,
  $api: Record<string, () => Promise<any>>,
  params: MaybeRef<Record<string, any>>,
  customOptions: CustomOptions,
  interactionState?: ChartInteractionState
) => {
  /** 图表id，每次重新请求会修改该值 */
  const chartId = shallowRef(random(8));
  const timeRange = inject('timeRange', DEFAULT_TIME_RANGE);
  const refreshImmediate = inject('refreshImmediate');

  const cancelTokens = [];
  const loading = shallowRef(false);
  /** 接口请求耗时 */
  const duration = shallowRef(0);
  const options = shallowRef();
  const metricList = shallowRef([]);
  const targets = shallowRef<IDataQuery[]>([]);
  const queryConfigs = computed(() => {
    return targets.value.reduce((pre, cur) => {
      if (cur.data?.query_configs) {
        pre.push(...cur.data.query_configs);
      }
      return pre;
    }, []);
  });
  const series = shallowRef([]);

  const getEchartOptions = async () => {
    const startDate = Date.now();
    loading.value = true;
    metricList.value = [];
    targets.value = [];
    const [startTime, endTime] = handleTransformToTimestamp(get(timeRange) || DEFAULT_TIME_RANGE);
    const promiseList = get(panel)?.targets?.map?.(target => {
      return $api[target.apiModule]
        [target.apiFunc](
          {
            start_time: startTime,
            end_time: endTime,
            ...target.data,
            ...(get(params) ?? {}),
          },
          {
            cancelToken: new CancelToken((cb: () => void) => cancelTokens.push(cb)),
            needMessage: false,
          }
        )
        .then(res => {
          const { series, metrics, query_config } = customOptions.formatterData?.(res, target) ?? res;
          for (const metric of metrics) {
            if (!metricList.value.some(item => item.metric_id === metric.metric_id)) {
              metricList.value.push(metric);
            }
          }
          const targetCopy = { ...target };
          if (query_config) {
            targetCopy.data = query_config;
          }
          targets.value.push(targetCopy);
          return series?.length
            ? series.map(item => ({
                ...item,
                alias: target.alias || item.alias,
                type: target.chart_type || get(panel).options?.time_series?.type || item.type || 'line',
                stack: target.data?.stack || item.stack,
                unit: item.unit || (get(panel)?.options as { unit?: string })?.unit,
              }))
            : [];
        })
        .catch(() => []);
    });
    const resList = await Promise.allSettled(promiseList ?? []).finally(() => {
      loading.value = false;
    });
    const seriesList = [];
    for (const item of resList) {
      // @ts-expect-error
      Array.isArray(item?.value) && item.value.length && seriesList.push(...item.value);
    }
    duration.value = Date.now() - startDate;
    series.value = seriesList;
    if (!seriesList.length) {
      return undefined;
    }
    const { xAxis, seriesData } = createSeries(seriesList);
    const yAxis = createYAxis(seriesData);
    const options = createOptions(xAxis, yAxis, seriesData);
    const { tooltipsOptions } = useChartTooltips(chartRef, {
      isMouseOver: interactionState?.isMouseOver ?? true,
      hoverAllTooltips: interactionState?.hoverAllTooltips ?? false,
      options,
    });
    return {
      ...options,
      tooltip: tooltipsOptions.value,
    };
  };
  const createSeries = (series: SeriesItem[]) => {
    const xAllData = new Set<number>();
    let xAxisIndex = -1;
    const xAxis = [];
    const seriesData: EchartSeriesItem[] = [];
    let preXData = [];
    for (const data of series) {
      const list = [];
      const xData = [];
      for (const point of data.datapoints) {
        xData.push(point[1]);
        xAllData.add(point[1]);
        list.push({
          value: point[0],
        });
      }
      const isEqual = preXData.length && arraysEqual(preXData, xData);

      if (!isEqual) {
        xAxisIndex += 1;
      }
      const unitFormatter = getValueFormat(data.unit);
      // 获取y轴上可设置的最小的精确度
      const precision = handleGetMinPrecision(
        list
          ?.filter?.(set => {
            const typedSet = set as { value: number | undefined };
            return typedSet && typeof typedSet.value === 'number';
          })
          .map(set => {
            const typedSet = set as { value: number | undefined };
            return typedSet.value;
          }) ?? [],
        unitFormatter,
        data.unit
      );
      // 构建基础 series 配置
      const seriesItem: EchartSeriesItem = {
        name: data.alias || data.target || '',
        data: list,
        xAxisIndex: xAxisIndex,
        type: data.type,
        stack: data.stack,
        unit: data.unit,
        // @ts-expect-error
        connectNulls: false,
        sampling: 'none',
        showAllSymbol: 'auto',
        showSymbol: false,
        smooth: 0,
        smoothMonotone: null,
        lineStyle: {
          width: 1.2,
          type: 'solid',
        },
        raw_data: {
          ...data,
          precision,
          datapoints: undefined,
          unitFormatter,
        },
        z: data.z || 3,
        ...data,
      };

      // 处理 markPoints（告警点）
      if (data.markPoints?.length && data.datapoints?.length) {
        seriesItem.markPoint = handleSetMarkPoints(data.markPoints, data.datapoints);
      }

      // 处理 markTimeRange（时间范围标记区域）
      if (data.markTimeRange?.length) {
        seriesItem.markArea = handleSetMarkTimeRange(data.markTimeRange);
      }

      // 处理 thresholds（阈值线和阈值区域）
      if (data.thresholds?.length) {
        seriesItem.markLine = handleSetThresholdLine(data.thresholds);
        const thresholdArea = handleSetThresholdArea(data.thresholds);
        if (thresholdArea) {
          seriesItem.markArea = seriesItem.markArea
            ? { ...seriesItem.markArea, data: [...(seriesItem.markArea.data || []), ...thresholdArea.data] }
            : thresholdArea;
        }
      }

      seriesData.push(seriesItem);

      if (!isEqual) {
        xAxis.push(...createXAxis(xData, { show: xAxisIndex === 0 }));
      }
      preXData = [...xData];
    }
    return {
      xData: Array.from(xAllData).sort(),
      seriesData: customOptions.series?.(seriesData) ?? seriesData,
      xAxis,
    };
  };
  const createXAxis = (
    xData: number[],
    options: { show: boolean } = {
      show: true,
    }
  ) => {
    const minXTime = xData.at(0);
    const maxXTime = xData.at(-1);
    let formatterFunc: FormatterFunc = '{value}';
    if (minXTime && maxXTime) {
      const duration = Math.abs(dayjs.tz(maxXTime).diff(dayjs.tz(minXTime), 'second'));
      formatterFunc = (v: string) => {
        if (duration < 1 * 60) {
          return dayjs.tz(+v).format('mm:ss');
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(+v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 6) {
          return dayjs.tz(+v).format('MM-DD HH:mm');
        }
        if (duration <= 60 * 60 * 24 * 30 * 12) {
          return dayjs.tz(+v).format('MM-DD');
        }
        return dayjs.tz(+v).format('YYYY-MM-DD');
      };
    }
    return [
      {
        show: !!options.show,
        position: 'bottom',
        // boundaryGap: false,
        axisTick: {
          show: false,
        },
        alignTicks: !!options.show,
        axisLine: {
          show: false,
          lineStyle: {
            color: '#ccd6eb',
            width: 1,
            type: 'solid',
          },
        },
        splitLine: {
          show: false,
        },
        minInterval: 5 * 60 * 1000,
        splitNumber: 10,
        scale: true,
        type: 'category',
        data: xData,
        axisLabel: {
          show: !!options.show,
          fontSize: 12,
          color: '#979BA5',
          showMinLabel: false,
          showMaxLabel: false,
          align: 'left',
          formatter: formatterFunc || '{value}',
        },
        z: options.show ? 3 : 0,
      },
    ];
  };
  const createYAxis = (yData: EchartSeriesItem[]) => {
    let hasBarChart = false;
    const unitSet = Array.from(
      new Set<string>(
        yData.map(item => {
          if ((!hasBarChart && item.type === 'bar') || get(panel).options?.time_series?.type === 'bar') {
            hasBarChart = true;
          }
          return item.unit?.length ? item.unit : '';
        })
      )
    );
    return unitSet.map(unit => {
      const yValueFormatter = getValueFormat(unit);
      return {
        type: 'value',
        axisLine: {
          show: false,
          lineStyle: {
            color: '#ccd6eb',
            width: 1,
            type: 'solid',
          },
        },
        axisTick: {
          show: false,
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#F0F1F5',
            type: 'dashed',
          },
        },
        z: 3,
        axisLabel: {
          color: '#979BA5',
          formatter: (v: any) => {
            if (unit !== 'none') {
              const { text, suffix } = yValueFormatter(v) || { text: v, suffix: '' };
              return `${text}${suffix}`;
            }
            return v;
          },
        },
        splitNumber: 2,
        minInterval: 1,
        scale: true,
        unit,
        max: 'dataMax',
        min: hasBarChart ? 0 : 'dataMin',
      };
    });
  };
  const createOptions = (xAxis, yAxis, series) => {
    const options = {
      useUTC: false,
      animation: false,
      animationThreshold: 2000,
      animationDurationUpdate: 0,
      animationDuration: 20,
      animationDelay: 300,
      title: {
        text: '',
        show: false,
      },
      color: COLOR_LIST_BAR,
      legend: {
        show: false,
      },
      tooltip: {
        show: true,
        trigger: 'axis',
        axisPointer: {
          type: 'cross',
          label: {
            backgroundColor: '#6a7985',
          },
        },
        transitionDuration: 0,
        alwaysShowContent: false,
        backgroundColor: 'rgba(54,58,67,.88)',
        borderWidth: 0,
        textStyle: {
          fontSize: 12,
          color: '#BEC0C6',
        },
        extraCssText: 'border-radius: 4px',
      },
      toolbox: {
        showTitle: false,
        itemSize: 0,
        iconStyle: {
          color: '#979ba5',
          borderWidth: 0,
          shadowColor: '#979ba5',
          shadowOffsetX: 0,
          shadowOffsetY: 0,
        },
        feature: {
          saveAsImage: {
            icon: 'path://',
          },
          dataZoom: {
            icon: {
              zoom: 'path://',
              back: 'path://',
            },
            show: true,
            yAxisIndex: false,
            iconStyle: {
              opacity: 0,
            },
          },
          restore: { icon: 'path://' },
        },
      },
      grid: {
        containLabel: true,
        left: 10,
        right: 10,
        top: 10,
        bottom: 10,
        backgroundColor: 'transparent',
      },
      xAxis: xAxis,
      yAxis: yAxis,
      series: series.map(item => {
        const yAxisIndex = yAxis.findIndex(axis => axis.unit === item.raw_data.unit);
        return {
          ...item,
          yAxisIndex: yAxisIndex < 1 ? 0 : yAxisIndex,
        };
      }),
    };
    return customOptions.options?.(options) ?? options;
  };
  watch(
    [timeRange, refreshImmediate, panel, params],
    async () => {
      loading.value = true;
      options.value = await getEchartOptions();
      chartId.value = random(8);
      loading.value = false;
    },
    {
      immediate: true,
    }
  );
  return {
    loading,
    options,
    metricList,
    targets,
    queryConfigs,
    duration,
    series,
    chartId,
    getEchartOptions,
  };
};
