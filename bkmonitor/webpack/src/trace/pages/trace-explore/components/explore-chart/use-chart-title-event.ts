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

import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';

import { handleAddStrategy, handleExplore, handleRelateAlert, handleStoreImage } from './menu';
import {
  type IUnifyQuerySeriesItem,
  downCsvFile,
  transformSrcData,
  transformTableDataToCsvStr,
} from '@/plugins/utls/menu';
// import { handleAddStrategy } from '@/plugins/utls/menu';
import { useTraceExploreStore } from '@/store/modules/explore';

import type { IDataQuery } from '@/plugins/typings';
import type { IMenuItem, ITitleAlarm } from '@/plugins/typings/chart-title';
import type { IExtendMetricData } from '@/plugins/typings/metric';

export const useChartTitleEvent = (
  metrics: MaybeRef<Array<Record<string, any>>>,
  targets: MaybeRef<IDataQuery[]>,
  title?: string,
  seriesData?: MaybeRef<IUnifyQuerySeriesItem[]>,
  chartRef?: MaybeRef<HTMLElement>
) => {
  const store = useTraceExploreStore();
  /** 处理点击左侧响铃图标 跳转策略的逻辑 */
  function handleAlarmClick(alarmStatus: ITitleAlarm) {
    const metricIds = get(metrics).map(item => item.metric_id);
    switch (alarmStatus.status) {
      case 0:
        // this.handleAddStrategy(props.panel, null, viewOptions?.value, true);
        break;
      case 1:
        window.open(location.href.replace(location.hash, `#/strategy-config?metricId=${JSON.stringify(metricIds)}`));
        break;
      case 2:
        window.open(
          location.href.replace(
            location.hash,
            `#/event-center?queryString=${metricIds.map(item => `metric : "${item}"`).join(' AND ')}&from=${
              store.timeRange?.[0]
            }&to=${store.timeRange?.[1]}`
          )
        );
        break;
    }
  }
  function handleMenuClick(item: IMenuItem) {
    switch (item.id) {
      case 'explore':
        handleExplore(get(targets), store.timeRange);
        return;
      case 'relate-alert':
        handleRelateAlert(get(targets), store.timeRange);
        return;
      case 'screenshot':
        // 300ms 关闭动画
        chartRef && setTimeout(() => handleStoreImage(title, get(chartRef)), 300);
        return;
      case 'export-csv': {
        if (seriesData && get(seriesData).length) {
          const { tableThArr, tableTdArr } = transformSrcData(get(seriesData));
          const csvString = transformTableDataToCsvStr(tableThArr, tableTdArr);
          downCsvFile(csvString, title);
        }
      }
    }
    return;
  }

  function handleMetricClick(metric: IExtendMetricData | null) {
    handleAddStrategy(get(targets), metric);
  }

  return {
    handleAlarmClick,
    handleMenuClick,
    handleMetricClick,
  };
};
