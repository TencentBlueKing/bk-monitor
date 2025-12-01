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

import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import { SpecialSeriesColorMap } from '../../../../typings/constants';

import type { IDataQuery, PanelModel } from '../../../../../../plugins/typings';
import type { ValueFormatter } from '../../../../../trace-explore/components/explore-chart/types';
import type { AlertK8SSeriesItem } from '../../../../typings';

/**
 * 图例数据项结构
 */
interface ILegendItem {
  avg: number | string;
  avgSource: number;
  color: string;
  dimensions?: Record<string, string>;
  lineStyleType?: string;
  max: number | string;
  maxSource: number;
  metricField?: string;
  min: number | string;
  minSource: number;
  name: string;
  show: boolean;
  silent?: boolean;
  total: number | string;
  totalSource: number;
}

/**
 * @method useK8sSeriesFormatter 容器图表数据格式化处理hooks
 * @description k8s 图表接口返回 series 数据处理
 */
export const useK8sSeriesFormatter = () => {
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
   * @method handleGetMinPrecision 获取数据的最小精度
   * @param {number[]} data 数据数组
   * @param {ValueFormatter} formatter 数值格式化函数
   * @param {string} unit 单位
   * @returns {number} 最小精度
   */
  const handleGetMinPrecision = (data: number[], formatter: ValueFormatter, unit: string) => {
    if (!data || data.length === 0) {
      return 0;
    }
    data.sort((a, b) => a - b);
    const len = data.length;
    if (data[0] === data[len - 1]) {
      if (['none', ''].includes(unit) && !data[0].toString().includes('.')) return 0;
      const setList = String(data[0]).split('.');
      return !setList || setList.length < 2 ? 2 : setList[1].length;
    }
    let precision = 0;
    let sampling = [];
    const middle = Math.ceil(len / 2);
    sampling.push(data[0]);
    sampling.push(data[Math.ceil(middle / 2)]);
    sampling.push(data[middle]);
    sampling.push(data[middle + Math.floor((len - middle) / 2)]);
    sampling.push(data[len - 1]);
    sampling = Array.from(new Set(sampling.filter(n => n !== undefined)));
    while (precision < 5) {
      const samp = sampling.reduce((pre, cur) => {
        pre[Number(formatter(cur, precision).text)] = 1;
        return pre;
      }, {});
      if (Object.keys(samp).length >= sampling.length) {
        return precision;
      }
      precision += 1;
    }
    return precision;
  };

  /**
   * @method handleTransformSeries 处理 series 数据
   * @param series series 数据
   * @param {string[]} colors 颜色数组
   * @param {number} chartHeight 图表高度，用于计算线段重叠
   * @returns {object} 处理后的 series 数据和图例数据
   */
  const handleTransformSeries = (series: AlertK8SSeriesItem[], colors?: string[], chartHeight = 240) => {
    const legendData: ILegendItem[] = [];
    const specialSeriesCount = series.filter(item => item.name in SpecialSeriesColorMap)?.length || 0;

    // 用于检测特殊线段的首个值
    let limitFirstY = 0;
    let requestFirstY = 0;
    let capacityFirstY = 0;

    const transformSeries = series.map((item, index) => {
      const colorList = COLOR_LIST;
      const color = item.color || (colors || colorList)[Math.max(index - specialSeriesCount, 0) % colorList.length];
      let showSymbol = false;

      // 初始化图例项
      const legendItem: ILegendItem = {
        avg: 0,
        avgSource: 0,
        color,
        dimensions: item.dimensions ?? {},
        lineStyleType: 'solid',
        max: 0,
        maxSource: 0,
        metricField: item.metricField,
        min: '',
        minSource: 0,
        name: String(item.name),
        show: true,
        silent: false,
        total: 0,
        totalSource: 0,
      };

      // 动态单位转换
      const unitFormatter = !['', 'none', undefined, null].includes(item.unit)
        ? getValueFormat(item.unit || '')
        : (v: unknown) => ({ text: v });

      let hasValueLength = 0;

      const data =
        item.data?.map?.((seriesItem: unknown, seriesIndex: number) => {
          const typedItem = seriesItem as [number, null | number] | undefined;
          if (!typedItem?.length || typeof typedItem[1] !== 'number') return typedItem;

          // 当前点数据
          const pre = item.data[seriesIndex - 1] as [number, null | number] | undefined;
          const next = item.data[seriesIndex + 1] as [number, null | number] | undefined;
          const y = +typedItem[1];
          hasValueLength += 1;

          // 设置图例数据
          legendItem.max = Math.max(+(legendItem.max as number), y);
          legendItem.min = legendItem.min === '' ? y : Math.min(+(legendItem.min as number), y);
          legendItem.total = +(legendItem.total as number) + y;

          // 是否为孤立的点
          const hasNoBrother =
            (!pre && !next) || (pre && next && pre.length && next.length && pre[1] === null && next[1] === null);
          if (hasNoBrother) {
            showSymbol = true;
          }

          return {
            itemStyle: {
              borderWidth: hasNoBrother ? 10 : 6,
              enabled: true,
              opacity: 1,
              shadowBlur: 0,
            },
            symbolSize: hasNoBrother ? 10 : 6,
            value: [typedItem[0], typedItem[1]],
          };
        }) ?? [];

      // 计算统计数据
      legendItem.avg = +(+(legendItem.total as number) / (hasValueLength || 1)).toFixed(2);
      legendItem.total = Number(legendItem.total as number).toFixed(2);

      // 获取y轴上可设置的最小的精确度
      const precision = handleGetMinPrecision(
        item?.data
          ?.filter?.((set: unknown) => {
            const typedSet = set as [number, null | number] | undefined;
            return typedSet && typeof typedSet[1] === 'number';
          })
          .map((set: unknown) => {
            const typedSet = set as [number, number];
            return typedSet[1];
          }) ?? [],
        getValueFormat(item.unit || ''),
        item.unit
      );

      // 处理特殊系列（limit, request, capacity）
      const isSpecialSeries = ['request', 'limit', 'capacity'].includes(item.name);
      let markPoint = {};

      if (isSpecialSeries) {
        const colorMap = SpecialSeriesColorMap[item.name];
        const isLimit = item.name === 'limit';
        const isCapacity = item.name === 'capacity';

        const firstValue = data?.find((d: unknown) => {
          const typedData = d as [number, number] | { value?: [number, number] };
          return Array.isArray(typedData) ? typedData[1] : (typedData as { value?: [number, number] }).value?.[1];
        });
        const firstValueY = Array.isArray(firstValue)
          ? firstValue[1]
          : ((firstValue as { value?: [number, number] })?.value?.[1] ?? 0);

        if (item.name === 'limit') {
          limitFirstY = firstValueY;
        } else if (item.name === 'capacity') {
          capacityFirstY = firstValueY;
        } else {
          requestFirstY = firstValueY;
        }

        const labelColor = colorMap.labelColor;
        const itemColor = colorMap.itemColor;

        markPoint = {
          data: [
            {
              coord: Array.isArray(firstValue)
                ? firstValue
                : ((firstValue as { value?: [number, number] })?.value ?? undefined),
            },
          ],
          emphasis: {
            disabled: true,
          },
          itemStyle: {
            color: itemColor,
          },
          label: {
            color: labelColor,
            formatter: () => item.name,
            show: true,
          },
          symbol: 'rect',
          symbolOffset: ['50%', 0],
          symbolSize: [isLimit ? 30 : isCapacity ? 52 : 46, 16],
        };

        legendItem.color = colorMap.color;
        legendItem.lineStyleType = 'dashed';
        legendItem.silent = true;
      }

      // 格式化图例数据
      if (item.name) {
        for (const key of ['min', 'max', 'avg', 'total']) {
          const val = legendItem[key as keyof ILegendItem];
          legendItem[`${key}Source` as keyof ILegendItem] = val as unknown as number;
          const formattedVal: { suffix?: string; text: string } = unitFormatter(
            val,
            item.unit !== 'none' && precision < 1 ? 2 : precision
          );
          legendItem[key as keyof ILegendItem] = (formattedVal.text + (formattedVal.suffix || '')) as unknown;
        }
        legendData.push(legendItem);
      }

      return {
        ...item,
        color,
        data,
        lineStyle: {
          width: 2,
        },
        markPoint,
        precision: precision || 4,
        showSymbol,
        smooth: 0,
        symbol: 'circle',
        unitFormatter,
        z: 4,
      };
    });

    // 检测线段重叠
    let minValue = 0;
    let maxValue = 0;
    for (const item of legendData) {
      const minV = Number(item.minSource);
      const maxV = Number(item.maxSource);
      if (minV < minValue) {
        minValue = minV;
      }
      if (maxV > maxValue) {
        maxValue = maxV;
      }
    }

    const limitEqualRequest =
      Math.abs(limitFirstY - requestFirstY) / (maxValue - minValue) < 16 / (chartHeight - 26) ||
      Math.abs(capacityFirstY - requestFirstY) / (maxValue - minValue) < 16 / (chartHeight - 26);
    const capacityEqualRequest =
      Math.abs(limitFirstY - capacityFirstY) / (maxValue - minValue) < 16 / (chartHeight - 26);

    // 处理重叠时的标记点隐藏
    const finalSeries = transformSeries.map(item => {
      if ((limitEqualRequest && item.name === 'request') || (capacityEqualRequest && item.name === 'capacity')) {
        return {
          ...item,
          markPoint: {},
        };
      }
      return item;
    });

    return { series: finalSeries, legendData };
  };

  /**
   * @method formatterSeriesData 格式化 series 数据
   * @param seriesData 原始接口返回的 series 数据
   * @param {IDataQuery} target panel 查询配置项 target
   * @param {PanelModel} panel panel 模型
   * @param {number} chartHeight 图表高度
   * @returns {object} 格式化后的 series 数据
   */
  const formatterSeriesData = (seriesData: unknown, target: IDataQuery, panel: PanelModel, chartHeight = 198) => {
    const data = seriesData as { series?: unknown[] };
    const { series: sourceSeries, ...rest } = data;
    let series = sourceSeries;
    let legendData: ILegendItem[] = [];

    if (series?.length) {
      series = (series as Array<{ alias?: string; dimensions?: Record<string, string>; unit?: string }>)
        .filter(item => ['extra_info', '_result_'].includes(item.alias))
        .map(set => {
          let name = handleSeriesName(target, set);
          if (['limit', 'request', 'capacity'].includes(target?.data?.query_configs?.[0]?.alias)) {
            name = target?.data?.query_configs?.[0]?.alias;
          }
          name = name.replace(/\|/g, ':');
          return {
            ...set,
            alias: name,
            name,
            unit: set.unit || (panel?.options as { unit?: string })?.unit,
          };
        });
      series = series.toSorted((a, b) => {
        const aName = (a as { name?: string }).name ?? '';
        const bName = (b as { name?: string }).name ?? '';
        return bName.localeCompare?.(aName) ?? 0;
      });
      const transformed = handleTransformSeries(series as AlertK8SSeriesItem[], undefined, chartHeight);
      series = transformed.series;
      legendData = transformed.legendData;
    }

    return { legendData, series, ...rest };
  };

  return { formatterSeriesData };
};
