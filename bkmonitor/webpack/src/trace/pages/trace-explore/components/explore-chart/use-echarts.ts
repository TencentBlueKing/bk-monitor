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

import { type MaybeRef, type Ref, watch } from 'vue';
import { shallowRef } from 'vue';

import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { useTraceExploreStore } from '@/store/modules/explore';
import { get } from '@vueuse/core';
import dayjs from 'dayjs';
import { CancelToken } from 'monitor-api/index';
import { arraysEqual } from 'monitor-common/utils/equal';
import { COLOR_LIST_BAR } from 'monitor-ui/chart-plugins/constants/charts';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

import { useChartTooltips } from './use-chart-tooltips';

import type { EchartSeriesItem, FormatterFunc, SeriesItem } from './types';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

export const useEcharts = (
  panel: MaybeRef<PanelModel>,
  chartRef: Ref<Element>,
  $api: Record<string, () => Promise<any>>
) => {
  const traceStore = useTraceExploreStore();
  const cancelTokens = [];
  const loading = shallowRef(false);
  const options = shallowRef();
  const metricList = shallowRef([]);
  // const queryConfigs = shallowRef([]);
  // const series = shallowRef([]);

  const getEchartOptions = async () => {
    loading.value = true;
    metricList.value = [];
    const [startTime, endTime] = handleTransformToTimestamp(traceStore.timeRange);
    const promiseList = get(panel).targets.map(target => {
      return $api[target.apiModule]
        [target.apiFunc](
          {
            ...target.data,
            start_time: startTime,
            end_time: endTime,
            app_name: traceStore.appName,
          },
          {
            cancelToken: new CancelToken((cb: () => void) => cancelTokens.push(cb)),
            needMessage: false,
          }
        )
        .then(({ series, metrics }) => {
          for (const metric of metrics) {
            if (!metricList.value.some(item => item.metric_id === metric.metric_id)) {
              metricList.value.push(metric);
            }
          }
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
    const resList = await Promise.allSettled(promiseList).finally(() => {
      loading.value = false;
    });
    const seriesList = [];
    for (const item of resList) {
      Array.isArray(item?.value) && item.value.length && seriesList.push(...item.value);
    }
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
    const preXData = [];
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
      seriesData.push({
        name: data.alias || data.target || '',
        data: list,
        xAxisIndex: xAxisIndex,
        type: data.type,
        stack: data.stack,
        unit: data.unit,
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
      preXData.push(...xData);
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
          return dayjs.tz(v).format('mm:ss');
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 6) {
          return dayjs.tz(v).format('MM-DD HH:mm');
        }
        if (duration <= 60 * 60 * 24 * 30 * 12) {
          return dayjs.tz(v).format('MM-DD');
        }
        return dayjs.tz(v).format('YYYY-MM-DD');
      };
    }
    return [
      {
        show: !!options.show,
        // boundaryGap: false,
        axisTick: {
          show: false,
        },
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
          fontSize: 12,
          color: '#979BA5',
          showMinLabel: false,
          showMaxLabel: false,
          align: 'left',
          formatter: formatterFunc || '{value}',
        },
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
        splitNumber: 4,
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
      color: COLOR_LIST_BAR,
      legend: {
        show: false,
      },
      tooltip: {
        show: true,
        trigger: 'axis',
        axisPointer: {
          type: 'line',
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
        left: 16,
        right: 16,
        top: 10,
        bottom: 10,
        backgroundColor: 'transparent',
      },
      xAxis: xAxis,
      markLine: [
        {
          z: 100, // markLine markArea不支持单独设置层级
        },
      ],
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
  watch(
    [() => traceStore.timeRange, () => traceStore.refreshImmediate, panel],
    async () => {
      console.info(panel, '========');
      loading.value = true;
      options.value = await getEchartOptions();
      setTimeout(() => {
        console.info(options.value, metricList.value, '______-');
      }, 2000);
      loading.value = false;
    },
    {
      immediate: true,
      flush: 'post',
    }
  );
  return {
    loading,
    options,
    metricList,
    getEchartOptions,
  };
};
