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
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants/charts';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats/valueFormats';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../../../../../components/time-range/utils';
import { useChartTooltips } from '../../../../../trace-explore/components/explore-chart/use-chart-tooltips';

import type { IDataQuery } from '../../../../../../plugins/typings';
import type { EchartSeriesItem, FormatterFunc } from '../../../../../trace-explore/components/explore-chart/types';
import type { IMarkTimeRange, IThreshold, MonitorSeriesItem } from '../../../../typings';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

export const useMonitorEcharts = (
  panel: MaybeRef<PanelModel>,
  chartRef: Ref<HTMLElement>,
  $api: Record<string, () => Promise<any>>,
  params: MaybeRef<Record<string, any>>,
  formatterSeriesData = res => res
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

  /**
   * 处理阈值线
   * @param thresholds 阈值配置数组
   */
  const handleSetThresholdLine = (thresholds: IThreshold[]) => {
    if (!thresholds?.length) return undefined;
    return {
      symbol: [],
      label: {
        show: true,
        position: 'insideStartTop',
      },
      lineStyle: {
        color: '#FD9C9C',
        type: 'dashed',
        distance: 3,
        width: 1,
      },
      emphasis: {
        label: {
          show: true,
          formatter: (v: any) => `${v.name || ''}: ${v.value}`,
        },
      },
      data: thresholds.map(item => ({
        ...item,
        label: {
          show: true,
          formatter: () => '',
        },
      })),
    };
  };

  /**
   * 处理阈值区域数据
   * @param thresholds 阈值配置数组
   */
  const handleSetThresholdAreaData = (thresholds: IThreshold[]) => {
    const threshold = thresholds.filter(item => item.method && !['eq', 'neq'].includes(item.method));
    const openInterval = ['gte', 'gt'];
    const closedInterval = ['lte', 'lt'];
    const data: any[] = [];

    for (let index = 0; index < threshold.length; index++) {
      const current = threshold[index];
      const nextThreshold = threshold[index + 1];
      let yAxis: number | string | undefined;

      if (
        openInterval.includes(current.method!) &&
        nextThreshold?.condition === 'and' &&
        closedInterval.includes(nextThreshold.method!) &&
        nextThreshold.yAxis >= current.yAxis
      ) {
        yAxis = nextThreshold.yAxis;
        index += 1;
      } else if (openInterval.includes(current.method!)) {
        yAxis = 'max';
      } else if (closedInterval.includes(current.method!)) {
        yAxis = current.yAxis < 0 ? current.yAxis : 0;
      }

      if (yAxis !== undefined) {
        data.push([{ ...current }, { yAxis, y: yAxis === 'max' ? '0%' : '' }]);
      }
    }
    return data;
  };

  /**
   * @description 处理阈值区域
   * @param thresholds 阈值配置数组
   */
  const handleSetThresholdArea = (thresholds: IThreshold[]) => {
    if (!thresholds?.length) return undefined;
    const data = handleSetThresholdAreaData(thresholds);
    if (!data.length) return undefined;
    return {
      silent: true,
      label: {
        show: false,
      },
      itemStyle: {
        color: 'rgba(255, 157, 157, 0.1)',
        borderWidth: 0,
      },
      data,
    };
  };

  /**
   * @description 处理时间范围标记区域
   * @param markTimeRange 时间范围数组
   */
  const handleSetMarkTimeRange = (markTimeRange: IMarkTimeRange[]) => {
    if (!markTimeRange?.length) return undefined;
    return {
      silent: true,
      show: true,
      data: markTimeRange.map(item => [
        {
          xAxis: String(item.from),
          y: 'max',
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
          xAxis: item.to || 'max',
          y: '0%',
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
      z: 10,
    };
  };

  /**
   * @description 处理 markPoints，返回 markPoint 数据数组
   * @param markPoints markPoints 数组
   * @param point 数据点 [value, timestamp]
   */
  const handleSetMarkPoints = (markPoints: any[], point: [number, number]) => {
    const [value, timestamp] = point;
    const result: { xAxis: string; yAxis: number }[] = [];
    const filteredMarkPoints = markPoints?.filter(
      (mp: any) => mp[1] === timestamp || mp === timestamp || mp?.value === timestamp
    );
    if (filteredMarkPoints?.length) {
      for (const mp of filteredMarkPoints) {
        if (typeof mp === 'object' && mp !== null && !Array.isArray(mp)) {
          // 如果 markPoint 是对象格式，使用默认值合并自定义属性
          result.push({
            xAxis: String(timestamp),
            yAxis: value,
            ...(mp as any),
          });
        } else if (Array.isArray(mp) && mp.length >= 2) {
          // 如果是数组格式 [yAxis, xAxis]，使用数组中的值
          result.push({
            xAxis: String(mp[1]),
            yAxis: mp[0],
          });
        } else {
          // 如果是值格式，使用默认 yAxis
          result.push({
            xAxis: String(timestamp),
            yAxis: value,
          });
        }
      }
    }
    return result;
  };

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
            ...target.data,
            start_time: startTime,
            end_time: endTime,
            ...get(params),
          },
          {
            cancelToken: new CancelToken((cb: () => void) => cancelTokens.push(cb)),
            needMessage: false,
          }
        )
        .then(res => {
          const { series, metrics, query_config } = formatterSeriesData(res);
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
      isMouseOver: true,
      hoverAllTooltips: false,
      options,
    });
    return {
      ...options,
      tooltip: tooltipsOptions.value,
    };
  };
  const createSeries = (series: MonitorSeriesItem[]) => {
    const xAllData = new Set<number>();
    let xAxisIndex = -1;
    const xAxis = [];
    const seriesData: EchartSeriesItem[] = [];
    let preXData = [];
    for (const data of series) {
      const list = [];
      const xData = [];
      // 收集告警点数据 (markPoints: [value, timestamp][])
      const markPointData: { xAxis: string; yAxis: number }[] = [];

      for (const point of data.datapoints) {
        const [value, timestamp] = point;
        xData.push(point[1]);
        xAllData.add(point[1]);
        // 处理 markPoints
        markPointData.push(...handleSetMarkPoints(data?.markPoints, point));

        list.push({ value });
      }

      const isEqual = preXData.length && arraysEqual(preXData, xData);
      if (!isEqual) {
        xAxisIndex += 1;
      }

      const unitFormatter = getValueFormat(data.unit);

      // 构建 series 配置
      const seriesItem: EchartSeriesItem = {
        name: data.alias || data.target || '',
        data: list,
        xAxisIndex,
        type: data.type || 'line',
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
          datapoints: undefined,
          unitFormatter,
        },
        z: data.z || 3,
        ...data,
      };

      // 处理 markPoints（告警点）
      if (markPointData.length) {
        seriesItem.markPoint = {
          symbol: 'circle',
          symbolSize: 6,
          z: 10,
          label: {
            show: false,
          },
          data: markPointData,
        };
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
        top: 30,
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
