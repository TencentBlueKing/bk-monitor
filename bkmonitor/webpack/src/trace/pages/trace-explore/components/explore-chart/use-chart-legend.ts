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

import { type ShallowRef, shallowRef, watch } from 'vue';

import type { ILegendItem, LegendActionType, ValueFormatter } from './types';

export const useChartLegend = (options: ShallowRef<any, any>) => {
  const legendData = shallowRef([]);
  const seriesList = shallowRef([]);

  function getLegendData(series: any[]) {
    seriesList.value = series;
    const legendDataTemp = [];
    let index = -1;
    for (const seriesItem of series) {
      index += 1;
      const legendItem: ILegendItem = {
        name: seriesItem.name,
        max: 0,
        min: '',
        avg: 0,
        total: 0,
        color: seriesItem?.color || options.value.color[index],
        show: true,
        minSource: 0,
        maxSource: 0,
        avgSource: 0,
        totalSource: 0,
        metricField: seriesItem.metric_field,
      };
      for (const dataValue of seriesItem.data) {
        const y = dataValue.value;
        // 设置图例数据
        legendItem.max = Math.max(+legendItem.max, y);
        legendItem.min = legendItem.min === '' ? y : Math.min(+legendItem.min, y);
        legendItem.total = +legendItem.total + y;
      }
      legendItem.avg = +(+legendItem.total / (seriesItem.data.length || 1)).toFixed(2);
      legendItem.total = Number(legendItem.total).toFixed(2);
      // 获取y轴上可设置的最小的精确度
      const precision = handleGetMinPrecision(
        seriesItem.data.filter((set: any) => typeof set.value === 'number').map(set => set.value),
        seriesItem.raw_data.unitFormatter,
        seriesItem.unit
      );
      if (seriesItem.name) {
        for (const key in legendItem) {
          if (['min', 'max', 'avg', 'total'].includes(key)) {
            const val = (legendItem as any)[key];
            (legendItem as any)[`${key}Source`] = val;
            const set: any = seriesItem.raw_data.unitFormatter(
              val,
              seriesItem.unit !== 'none' && precision < 1 ? 2 : precision
            );
            (legendItem as any)[key] = set.text + (set.suffix || '');
          }
        }
        legendDataTemp.push(legendItem);
      }
    }
    legendData.value = legendDataTemp;
  }
  function handleGetMinPrecision(data: number[], formatter: ValueFormatter, unit: string) {
    if (!data || data.length === 0) {
      return 0;
    }
    data.sort();
    const len = data.length;
    if (data[0] === data[len - 1]) {
      if (unit === 'none') return 0;
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
        (pre as any)[formatter(cur, precision).text] = 1;
        return pre;
      }, {});
      if (Object.keys(samp).length >= sampling.length) {
        return precision;
      }
      precision += 1;
    }
    return precision;
  }

  function handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    if (legendData.value.length < 2) {
      return;
    }
    const setSeriesFilter = () => {
      // const copyOptions = { ...options.value };
      const showNames = [];
      for (const l of legendData.value) {
        l.show && showNames.push(l.name);
      }
      options.value = {
        ...options.value,
        series: seriesList.value?.filter(s => showNames.includes(s.name)),
      };
    };
    if (actionType === 'shift-click') {
      legendData.value = legendData.value.map(l => {
        if (l.name === item.name) {
          return {
            ...l,
            show: !l.show,
          };
        }
        return l;
      });
      setSeriesFilter();
    } else if (actionType === 'click') {
      const hasOtherShow = legendData.value
        .filter(item => !item.hidden)
        .some(set => set.name !== item.name && set.show);
      legendData.value = legendData.value.map(l => {
        return {
          ...l,
          show: l.name === item.name || !hasOtherShow,
        };
      });
      setSeriesFilter();
    }
  }

  const { stop } = watch(
    () => options.value,
    v => {
      if (v?.series) {
        getLegendData(v.series);
        stop();
      }
    },
    {
      immediate: true,
    }
  );
  return {
    legendData,
    handleSelectLegend,
  };
};
