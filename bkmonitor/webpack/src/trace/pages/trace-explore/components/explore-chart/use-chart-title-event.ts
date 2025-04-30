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

// import { handleAddStrategy } from '@/plugins/utls/menu';
import { useTraceExploreStore } from '@/store/modules/explore';
import { get } from '@vueuse/core';

import type { IMenuItem, ITitleAlarm } from '@/plugins/typings/chart-title';
import type { IExtendMetricData } from '@/plugins/typings/metric';
import type { MaybeRef } from 'vue';

export const useChartTitleEvent = (metrics: MaybeRef<Array<Record<string, any>>>) => {
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
    // const variablesService = new VariablesService({ ...viewOptions });
    switch (item.id) {
      case 'explore':
        // handleExplore(props.panel!, viewOptions!.value, timeRange!.value);
        return;
      case 'relate-alert':
        // props.panel?.targets?.forEach(target => {
        //   if (target.data?.query_configs?.length) {
        //     let queryConfig = deepClone(target.data.query_configs);
        //     queryConfig = variablesService.transformVariables(queryConfig);

        //     target.data.query_configs = queryConfig;
        //   }
        // });
        // handleRelateAlert(props.panel!, timeRange!.value);
        return;
      case 'screenshot':
        // 300ms 关闭动画
        // setTimeout(() => handleStoreImage(props.panel!.title, timeSeriesRef.value!), 300);
        return;
      case 'export-csv': {
        // if (csvSeries.length) {
        //   const { tableThArr, tableTdArr } = transformSrcData(csvSeries);
        //   const csvString = transformTableDataToCsvStr(tableThArr, tableTdArr);
        //   downCsvFile(csvString, props.panel!.title);
      }
    }
    return;
  }

  function handleMetricClick(metric: IExtendMetricData | null) {
    console.info(metric);
    // handleAddStrategy(props.panel!, metric, viewOptions!.value, timeRange!.value);
  }

  return {
    handleAlarmClick,
    handleMenuClick,
    handleMetricClick,
  };
};
