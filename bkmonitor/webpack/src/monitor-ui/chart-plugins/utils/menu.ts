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
import { getMetricId } from './utils';

import type { PanelModel } from '../typings';

export const handleRelateAlert = (panel: PanelModel, timeRange: string[]) => {
  const metricIdMap = {};
  const promqlSet = new Set<string>();
  if (panel?.targets?.length) {
    for (const target of panel.targets) {
      if (target.data?.query_configs?.length) {
        for (const item of target.data.query_configs) {
          if (item.promql) {
            promqlSet.add(JSON.stringify(item.promql));
          } else {
            const metricId = getMetricId(
              item.data_source_label,
              item.data_type_label,
              item.metrics?.[0]?.field,
              item.table,
              item.index_set_id
            );
            if (metricId) {
              metricIdMap[metricId] = 'true';
            }
          }
        }
      }
    }
  }
  let queryString = '';
  for (const metricId of Object.keys(metricIdMap)) {
    queryString += `${queryString.length ? ' OR ' : ''}指标ID : ${metricId}`;
  }
  let promqlString = '';
  for (const promql of promqlSet) {
    promqlString = `promql=${promql}`;
  }
  (queryString.length || promqlString) &&
    window.open(
      location.href.replace(
        location.hash,
        `#/event-center?from=${timeRange[0]}&to=${timeRange[1]}&timezone=${window.timezone}&${promqlString || `queryString=${queryString}`}`
      )
    );
};
