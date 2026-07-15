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

import { type MaybeRef, computed, inject, toValue, watch } from 'vue';

import dayjs from 'dayjs';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import type { EchartSeriesItem, IMarkPointDataItem } from './types';

/** 上层容器（如 HostMetric）注入的视图选项 */
export interface ChartViewOptions {
  /** 列数量 */
  columns?: number;
  /** 高亮峰谷值 */
  highlightPeak?: boolean;
  /** 关键字  */
  keyword?: string;
  /** 展示统计值 */
  showStatistics?: boolean;
}

/**
 * @description 图表视图选项 Hook
 * 负责注入并消费上层 provide 的 viewOptions，处理所有仅影响前端展示、
 * 不触发数据请求的视图操作（如高亮峰谷值、统计值展示等）。
 */
export const useChartViewOption = () => {
  const viewOptions = inject<MaybeRef<ChartViewOptions>>('viewOptions', undefined);

  /** 是否高亮峰谷值 */
  const isHighlightPeak = computed(() => toValue(viewOptions)?.highlightPeak ?? false);

  /**
   * @description 根据 X 轴时间范围构建 Max/Min 峰谷值 markPoint 数据
   * @param xData X 轴时间戳数组
   */
  const buildPeakMarkPointData = (xData: number[], unit: string): IMarkPointDataItem[] => {
    if (!xData.length) return [];

    const minXTime = xData[0];
    const maxXTime = xData[xData.length - 1];
    const duration = minXTime && maxXTime ? Math.abs(dayjs.tz(maxXTime).diff(dayjs.tz(minXTime), 'second')) : 0;

    const formatTime = (timestamp: number) => {
      if (!timestamp) return '';
      if (duration < 1 * 60) return dayjs.tz(timestamp).format('mm:ss');
      if (duration < 60 * 60 * 24 * 1) return dayjs.tz(timestamp).format('HH:mm');
      if (duration < 60 * 60 * 24 * 6) return dayjs.tz(timestamp).format('MM-DD HH:mm');
      if (duration <= 60 * 60 * 24 * 30 * 12) return dayjs.tz(timestamp).format('MM-DD');
      return dayjs.tz(timestamp).format('YYYY-MM-DD');
    };

    const label = {
      show: true,
      position: 'right',
      offset: [0, 0],
      formatter: (params: { data?: { coord?: [number, number] }; name: string; value: number }) => {
        const index = params.data?.coord?.[0];
        const time = typeof index === 'number' && xData[index] ? formatTime(xData[index]) : '';
        const { text, suffix } = getValueFormat(unit)(params.value);
        const value = unit !== 'none' ? `${text}${suffix}` : params.value;
        return `{label|${params.name}:}{value| ${value} }{time|@${time}}`;
      },
      rich: {
        label: { color: '#FFB848', fontWeight: 'bold' },
        value: { color: '#313238' },
        time: { color: '#A8B5CF' },
      },
    };

    return [
      { type: 'max', name: 'Max', symbol: 'pin', symbolSize: 10, label, itemStyle: { color: '#FF9C01' } },
      {
        type: 'min',
        name: 'Min',
        symbol: 'pin',
        symbolSize: 10,
        symbolRotate: 180,
        label: {
          ...label,
          offset: [0, 3],
        },
        itemStyle: { color: '#FF9C01' },
      },
    ];
  };

  /**
   * @description 将峰谷值标记应用到 series 数据
   * @param seriesData echarts series 数组
   * @param xData X 轴时间戳数组
   */
  const applyPeakMarkPoint = (seriesData: EchartSeriesItem[], xData: number[]) => {
    if (!isHighlightPeak.value) return;
    if (!seriesData.length) return;
    const getValues = (series: EchartSeriesItem): number[] => {
      if (!Array.isArray(series.data)) return [];
      if (!series.data.length) return [];
      if (typeof series.data[0] === 'object' && series.data[0] !== null && 'value' in series.data[0]) {
        return (series.data as { value: null | number }[])
          .map(d => d.value)
          .filter((v): v is number => v !== null && v !== undefined && !Number.isNaN(v));
      }
      return (series.data as number[]).filter(v => v !== null && v !== undefined && !Number.isNaN(v));
    };

    let globalMax = -Infinity;
    let globalMin = Infinity;
    let maxSeriesIndex = -1;
    let minSeriesIndex = -1;

    for (let i = 0; i < seriesData.length; i++) {
      const values = getValues(seriesData[i]);
      if (!values.length) continue;

      const seriesMax = Math.max(...values);
      const seriesMin = Math.min(...values);

      if (seriesMax > globalMax) {
        globalMax = seriesMax;
        maxSeriesIndex = i;
      }
      if (seriesMin < globalMin) {
        globalMin = seriesMin;
        minSeriesIndex = i;
      }
    }

    if (maxSeriesIndex === -1 && minSeriesIndex === -1) return;

    const peakData = buildPeakMarkPointData(xData, seriesData[0]?.unit);
    const maxPeakData = peakData.find(item => item.type === 'max');
    const minPeakData = peakData.find(item => item.type === 'min');

    if (maxSeriesIndex !== -1 && maxPeakData) {
      const seriesItem = seriesData[maxSeriesIndex];
      seriesItem.markPoint = seriesItem.markPoint
        ? { ...seriesItem.markPoint, data: [...(seriesItem.markPoint.data || []), maxPeakData] }
        : { data: [maxPeakData] };
    }

    if (minSeriesIndex !== -1 && minPeakData) {
      const seriesItem = seriesData[minSeriesIndex];
      seriesItem.markPoint = seriesItem.markPoint
        ? { ...seriesItem.markPoint, data: [...(seriesItem.markPoint.data || []), minPeakData] }
        : { data: [minPeakData] };
    }
  };

  /**
   * @description 监听 highlightPeak 变化
   * @param callback 变化后的回调函数
   */
  const watchHighlightPeak = (callback: () => void) => {
    watch(isHighlightPeak, callback);
  };

  return {
    viewOptions,
    isHighlightPeak,
    buildPeakMarkPointData,
    applyPeakMarkPoint,
    watchHighlightPeak,
  };
};
