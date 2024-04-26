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
import { PanelModel } from '../typings';
import { getMetricId } from './utils';

export const handleRelateAlert = (panel: PanelModel, timeRange: string[]) => {
  const metricIdMap = {};
  panel?.targets?.forEach(target => {
    if (target.data?.query_configs?.length) {
      target.data?.query_configs?.forEach((item: any) => {
        const metricId = getMetricId(
          item.data_source_label,
          item.data_type_label,
          item.metrics?.[0]?.field,
          item.table,
          item.index_set_id
        );
        metricIdMap[metricId] = 'true';
      });
    }
  });
  let queryString = '';
  Object.keys(metricIdMap).forEach(metricId => {
    queryString += `${queryString.length ? ' or ' : ''}指标ID : ${metricId}`;
  });
  queryString.length &&
    window.open(
      location.href.replace(
        location.hash,
        `#/event-center?queryString=${queryString}&from=${timeRange[0]}&to=${timeRange[1]}&timezone=${window.timezone}`
      )
    );
};
