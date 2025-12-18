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
import deepmerge from 'deepmerge';
import { CancelToken } from 'monitor-api/cancel';
import { random } from 'monitor-common/utils';
import { arraysEqual } from 'monitor-common/utils/equal';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants/charts';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '@/components/time-range/utils';
import { useChartTooltips } from '@/pages/trace-explore/components/explore-chart/use-chart-tooltips';

import type { FormatterOptions } from './monitor-charts';
import type { EchartSeriesItem, FormatterFunc, SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';
import type { IDataQuery } from '@/plugins/typings';
import type { IPlotBand, PanelModel } from 'monitor-ui/chart-plugins/typings';
export const useMonitorEcharts = (
  panel: MaybeRef<PanelModel>,
  chartRef: Ref<HTMLElement>,
  $api: Record<string, () => Promise<any>>,
  params: MaybeRef<Record<string, any>>,
  formatterOptions: FormatterOptions
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
      const resultParams = {
        ...target.data,
        ...get(params),
        start_time: startTime,
        end_time: endTime,
      };

      return $api[target.apiModule]
        [target.apiFunc](formatterOptions.params?.(resultParams) || resultParams, {
          cancelToken: new CancelToken((cb: () => void) => cancelTokens.push(cb)),
          needMessage: false,
        })
        .then(res => {
          const { series, metrics, query_config } = formatterOptions.seriesData?.(res) || res;
          for (const metric of metrics) {
            if (!metricList.value.some(item => item.metric_id === metric.metric_id)) {
              metricList.value.push(metric);
            }
          }
          targets.value.push({ ...target, data: query_config });
          return series?.length
            ? series.map(item => ({
                ...item,
                alias: target.alias || item.alias,
                type: target.chart_type || get(panel).options?.time_series?.type || item.type || 'line',
                stack: target.data?.stack || item.stack,
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
      isMouseOver: true,
      hoverAllTooltips: false,
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
      const minXTime = xData.at(0);
      const maxXTime = xData.at(-1);

      if (!isEqual) {
        xAxisIndex += 1;
      }
      const unitFormatter = getValueFormat(data.unit);
      seriesData.push({
        ...data,
        name: data.alias || data.target || '',
        data: list,
        xAxisIndex,
        type: data.type,
        stack: data.stack,
        unit: data.unit,
        /** 区域标记 */
        markArea: createMarkArea(data, minXTime, maxXTime),
        markPoint: createMarkPointData(data, series),
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
          datapoints: undefined,
          unitFormatter,
        },
        z: 3,
      });
      if (!isEqual) {
        xAxis.push(...createXAxis(xData, { show: xAxisIndex === 0 }));
      }
      preXData = [...xData];
    }
    return {
      xData: Array.from(xAllData).sort(),
      seriesData,
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
        // boundaryGap: true,
        // alignTicks: true,
        // nameGap: 0,
        // nameLocation: 'center',
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
    return {
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
      color: COLOR_LIST,
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
  };

  /** 设置事件中心告警区域 */
  const handleSetThresholdBand = (plotBands: IPlotBand[], minXTime, maxXTime) => {
    return {
      silent: true,
      show: true,
      data: plotBands.map(item => [
        {
          xAxis: item.from < minXTime ? String(minXTime) : String(item.from),
          itemStyle: {
            color: item.color || '#FFF5EC',
            borderWidth: 1,
            borderColor: item.borderColor || '#FFE9D5',
            shadowColor: item.shadowColor || '#FFF5EC',
            borderType: item.borderType || 'solid',
            shadowBlur: 0,
          },
        },
        {
          xAxis: item.to ? (item.to > maxXTime ? String(maxXTime) : String(item.to)) : 'max',
          itemStyle: {
            color: item.color || '#FFF5EC',
            borderWidth: 1,
            borderColor: item.borderColor || '#FFE9D5',
            shadowColor: item.shadowColor || '#FFF5EC',
            borderType: item.borderType || 'solid',
            shadowBlur: 0,
          },
        },
      ]),
      opacity: 0.1,
    };
  };

  /** 创建标记区域 */
  const createMarkArea = (item, minXTime, maxXTime) => {
    /** 阈值区域 */
    const thresholdsMarkArea = get(panel).options?.time_series?.markArea || {};
    let alertMarkArea = {};
    /** 告警区域 */
    if (item.markTimeRange?.length) {
      alertMarkArea = handleSetThresholdBand(item.markTimeRange.slice(), minXTime, maxXTime);
    }
    return deepmerge(alertMarkArea, thresholdsMarkArea);
  };

  /** 获取告警点数据 */
  const createMarkPointData = (item, series) => {
    let data = [];
    /** 获取is_anomaly的告警点数据 */
    const currentDataPoints = item.datapoints;
    const currentDataPointsMap = new Map();
    const currentDimensions = item.dimensions || [];
    const getDimStr = dim => `${dim.bk_target_ip}-${dim.bk_target_cloud_id}`;
    const currentDimStr = getDimStr(currentDimensions);
    const currentIsAnomalyData = series.find(
      item => item.alias === 'is_anomaly' && currentDimStr === getDimStr(item.dimensions)
    );
    let markPointData = [];
    if (currentIsAnomalyData) {
      for (const item of currentDataPoints) {
        currentDataPointsMap.set(item[0], item[1]);
      }
      const currentIsAnomalyPoints = currentIsAnomalyData.datapoints;
      markPointData = currentIsAnomalyPoints.reduce((total, cur) => {
        const key = cur[1];
        const val = currentDataPointsMap.get(key);
        const isExit = currentDataPointsMap.has(key) && cur[0];
        /** 测试条件 */
        // const isExit = currentDataPointsMap.has(key) && val > 31.51;
        isExit && total.push([key, val]);
        return total;
      }, []);
    }
    /** 红色告警点 */
    data = markPointData.map(item => ({
      itemStyle: {
        color: '#EA3636',
      },
      xAxis: item[0],
      yAxis: item[1],
    }));

    item.markPoints?.length &&
      data.push(
        ...item.markPoints.map(item => ({
          xAxis: item[1] ? String(item[1]) : item[1],
          yAxis: item[0],
          symbolSize: 12,
        }))
      );
    /** 事件中心告警开始点 */
    const markPoint = {
      data,
      zlevel: 0,
      symbol: 'circle',
      symbolSize: 6,
      z: 10,
      label: {
        show: false,
      },
    };
    return markPoint;
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
