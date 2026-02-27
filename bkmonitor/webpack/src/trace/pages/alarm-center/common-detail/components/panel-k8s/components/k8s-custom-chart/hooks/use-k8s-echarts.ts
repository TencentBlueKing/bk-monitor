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

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../../../../../../../components/time-range/utils';
import { useChartTooltips } from '../../../../../../../trace-explore/components/explore-chart/use-chart-tooltips';
import { handleGetMinPrecision } from '../../../../../../../trace-explore/components/explore-chart/utils';
import { type AlertK8sEchartSeriesItem, SpecialSeriesColorMap } from '../../../../../../typings';

import type { FormatterFunc, SeriesItem } from '../../../../../../../trace-explore/components/explore-chart/types';
import type {
  ChartInteractionState,
  CustomOptions,
} from '../../../../../../../trace-explore/components/explore-chart/use-echarts';
import type { IDataQuery } from '@/plugins/typings';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

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
export const useK8sEcharts = (
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

  /**
   * @method isSpecialSeries 判断是否是特殊 series
   * @param {string} name series name
   * @returns {boolean} 是否是特殊 series
   */
  const isSpecialSeries = (name: string) => {
    return ['request', 'limit', 'capacity'].includes(name);
  };

  /**
   * @method handleSeriesName 获取 series 展示的 name
   * @description 由于接口返回的 series 数据中name是不准确的，所以需要对其进行额外的处理
   * @param {IDataQuery} item panel 查询配置项 target
   * @param set 原始 series 配置
   * @returns {string} 处理后的 series name
   */
  const handleSeriesName = (item: IDataQuery, set) => {
    const { dimensions = {}, dimensions_translation: dimensionsTranslation = {} } = set;
    if (!item.alias)
      return Object.values({
        ...dimensions,
        ...dimensionsTranslation,
      }).join('|');
    const aliasFix = Object.values(dimensions).join('|');
    if (!aliasFix.length) return item.alias;
    return `${item.alias}-${aliasFix}`;
  };

  /**
   * @method _createMarkPoint 为 series 创建 markPoint
   * @param {AlertK8sEchartSeriesItem[]} seriesData 数据数组
   * @param {any[]} xAxis x 轴数据
   * @returns {AlertK8sEchartSeriesItem[]} 处理后的 series 数据
   */
  const makeMarkPointForSeries = (seriesData: AlertK8sEchartSeriesItem[], xAxis): AlertK8sEchartSeriesItem[] => {
    if (!seriesData?.length) return seriesData;
    let limitFirstY = 0;
    let requestFirstY = 0;
    let capacityFirstY = 0;
    seriesData = seriesData.map(item => {
      const isSpecial = isSpecialSeries(item.alias);
      let color = item.lineStyle?.color;
      let markPoint = {};
      const xData = xAxis?.[item?.xAxisIndex] ?? [];
      if (isSpecial) {
        const isLimit = item.name === 'limit';
        const isCapacity = item.name === 'capacity';
        const colorMap = SpecialSeriesColorMap[item.name];
        color = colorMap.color;
        const labelColor = colorMap.labelColor;
        const itemColor = colorMap.itemColor;
        const firstIndex = item.data?.findIndex(item => item.value);
        const firstValue = item.data?.[firstIndex];
        const firstValueX = xData?.data?.[firstIndex] || 0;
        const firstValueY = firstValue?.value || 0;
        if (isLimit) {
          limitFirstY = firstValueY;
        } else if (item.name === 'capacity') {
          capacityFirstY = firstValueY;
        } else {
          requestFirstY = firstValueY;
        }
        markPoint = {
          symbol: 'rect',
          symbolSize: [isLimit ? 30 : isCapacity ? 52 : 46, 16],
          symbolOffset: ['50%', 0],
          label: {
            show: true,
            color: labelColor,
            formatter: () => item.name,
          },
          itemStyle: {
            color: itemColor,
          },
          data: [
            {
              coord: [firstValueX?.toString?.(), firstValueY],
            },
          ],
          emphasis: {
            disabled: true,
          },
        };
      }
      return {
        ...item,
        color: isSpecial ? color : undefined,
        lineStyle: {
          ...(item.lineStyle ?? {}),
          type: isSpecial ? 'dashed' : 'solid',
          dashOffset: '4',
          color,
          width: 1.5,
        },
        areaStyle: isSpecial
          ? undefined
          : {
              opacity: 0.2,
              color,
            },
        markPoint,
      };
    });

    // 判断limit 与request是否重叠
    let min = 0;
    let max = 0;
    for (const item of seriesData) {
      const maxMinValues = item?.raw_data?.maxMinValues;
      const minValue = Number(maxMinValues.min);
      const maxValue = Number(maxMinValues.max);
      if (minValue < min) {
        min = minValue;
      }
      if (maxValue > max) {
        max = maxValue;
      }
    }
    const height = get(chartRef)?.clientHeight ?? 198;
    const limitEqualRequest =
      Math.abs(limitFirstY - requestFirstY) / (max - min) < 16 / (height - 26) ||
      Math.abs(capacityFirstY - requestFirstY) / (max - min) < 16 / (height - 26);
    const capacityEqualRequest = Math.abs(limitFirstY - capacityFirstY) / (max - min) < 16 / (height - 26);
    seriesData = seriesData.map(item => {
      if ((limitEqualRequest && item.name === 'request') || (capacityEqualRequest && item.name === 'capacity')) {
        return {
          ...item,
          markPoint: {},
        };
      }
      return item;
    });
    return seriesData;
  };

  const getEchartOptions = async () => {
    const startDate = Date.now();
    loading.value = true;
    metricList.value = [];
    targets.value = [];
    const [startTime, endTime] = handleTransformToTimestamp(get(timeRange));
    const promiseList = get(panel)?.targets?.map?.(target => {
      return $api[target.apiModule]
        [target.apiFunc](
          {
            ...target.data,
            ...get(params),
            start_time: startTime,
            end_time: endTime,
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
          targets.value.push({ ...target, data: query_config ?? target.data });
          return series?.length
            ? series
                .filter(item => ['extra_info', '_result_'].includes(item.alias))
                .map(item => {
                  let seriesName = handleSeriesName(target, item);
                  if (['limit', 'request', 'capacity'].includes(target?.data?.query_configs?.[0]?.alias)) {
                    seriesName = target?.data?.query_configs?.[0]?.alias;
                  }
                  seriesName = seriesName.replace(/\|/g, ':');
                  return {
                    ...item,
                    alias: seriesName ?? (target.alias || item.alias),
                    type: target.chart_type || get(panel).options?.time_series?.type || item.type || 'line',
                    stack: target.data?.stack || item.stack,
                    unit: item.unit || (get(panel)?.options as { unit?: string })?.unit,
                  };
                })
                .toSorted((a, b) => {
                  const aName = (a as { alias?: string }).alias ?? '';
                  const bName = (b as { alias?: string }).alias ?? '';
                  return bName.localeCompare?.(aName) ?? 0;
                })
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
    let seriesData: AlertK8sEchartSeriesItem[] = [];
    let preXData = [];
    for (const data of series) {
      const list = [];
      const xData = [];
      const maxMinValues = {
        max: 0,
        min: 0,
      };
      for (const point of data.datapoints) {
        const value = point[0];
        maxMinValues.max = Math.max(+maxMinValues.max, value);
        maxMinValues.min = Math.min(+maxMinValues.min, value);
        xData.push(point[1]);
        xAllData.add(point[1]);
        list.push({
          itemStyle: {
            borderWidth: 6,
            enabled: true,
            opacity: 1,
            shadowBlur: 0,
          },
          symbolSize: 6,
          value: value,
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

      seriesData.push({
        ...data,
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
          precision,
          maxMinValues,
          unitFormatter,
        },
        z: 3,
      });
      if (!isEqual) {
        xAxis.push(...createXAxis(xData, { show: xAxisIndex === 0 }));
      }
      preXData = [...xData];
    }
    seriesData = makeMarkPointForSeries(seriesData, xAxis);
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
  const createYAxis = (yData: AlertK8sEchartSeriesItem[]) => {
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
