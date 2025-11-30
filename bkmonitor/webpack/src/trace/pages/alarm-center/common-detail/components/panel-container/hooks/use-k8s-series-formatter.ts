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
    const { dimensions = {}, dimensions_translation = {} } = set;
    if (!item.alias)
      return Object.values({
        ...dimensions,
        ...dimensions_translation,
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
   * @returns {ITimeSeriesItem[]} 处理后的 series 数据
   */
  const handleTransformSeries = (series: AlertK8SSeriesItem[], colors?: string[]) => {
    const specialSeriesCount = series.filter(item => item.name in SpecialSeriesColorMap)?.length || 0;
    const transformSeries = series.map((item, index) => {
      const colorList = COLOR_LIST;
      const color = item.color || (colors || colorList)[Math.max(index - specialSeriesCount, 0) % colorList.length];
      let showSymbol = false;
      const data = item.data?.map?.((seriesItem: any, seriesIndex: number) => {
        if (!seriesItem?.length || typeof seriesItem[1] !== 'number') return seriesItem;
        // 当前点数据
        const pre = item.data[seriesIndex - 1] as [number, number];
        const next = item.data[seriesIndex + 1] as [number, number];
        // 是否为孤立的点
        const hasNoBrother =
          (!pre && !next) || (pre && next && pre.length && next.length && pre[1] === null && next[1] === null);
        if (hasNoBrother) {
          showSymbol = true;
        }
        return {
          symbolSize: hasNoBrother ? 10 : 6,
          value: [seriesItem[0], seriesItem[1]],
          itemStyle: {
            borderWidth: hasNoBrother ? 10 : 6,
            enabled: true,
            shadowBlur: 0,
            opacity: 1,
          },
        } as any;
      });
      // // 获取y轴上可设置的最小的精确度
      const precision = handleGetMinPrecision(
        item?.data?.filter?.((set: any) => typeof set[1] === 'number').map((set: any[]) => set[1]),
        getValueFormat(item.unit || ''),
        item.unit
      );
      return {
        ...item,
        color,
        // type: 'line',
        data,
        showSymbol,
        symbol: 'circle',
        z: 4,
        smooth: 0,
        precision: precision || 4,
        lineStyle: {
          width: 2,
        },
      };
    });
    return transformSeries;
  };

  /**
   * @method formatterSeriesData 格式化 series 数据
   * @param seriesData 原始接口返回的 series 数据
   * @param {IDataQuery} target panel 查询配置项 target
   * @param {PanelModel} panel panel 模型
   * @returns {object} 格式化后的 series 数据
   */
  const formatterSeriesData = (seriesData, target: IDataQuery, panel: PanelModel) => {
    const { series: sourceSeries, ...rest } = seriesData;
    let series = sourceSeries;
    if (series?.length) {
      series = series
        .filter(item => ['extra_info', '_result_'].includes(item.alias))
        .map(set => {
          let name = handleSeriesName(target, set);
          if (['limit', 'request', 'capacity'].includes(target?.data?.query_configs?.[0]?.alias)) {
            name = target?.data?.query_configs?.[0]?.alias;
          }
          name = name.replace(/\|/g, ':');
          return {
            ...set,
            name,
            // @ts-expect-error
            unit: set.unit || panel?.options?.unit,
            alias: name,
            precision: 2,
          };
        });
      series = series.toSorted((a, b) => b.name?.localeCompare?.(a?.name));
      series = handleTransformSeries(series);
    }
    return { series, ...rest };
  };

  return { formatterSeriesData };
};
