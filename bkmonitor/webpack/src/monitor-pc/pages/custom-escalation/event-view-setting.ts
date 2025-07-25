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
// 自定义事件视图设置处理
import { COLLECT_CHART_TYPE } from '../../constant/constant';

import type { hideOptions } from '../collector-config/collector-view/log-handle';
import type { metric } from '../collector-config/collector-view/type';

interface IEventInfoList {
  dimension_list?: { dimension_name: string }[];
}
interface IMetricDimension {
  dimensionList: metric[]; // 维度列表

  metricList: { id: string; metrics: metric[]; result_table_id?: string }[]; // 指标列表(自定义事件没有)
  variableParams?: any; // 查询预览值api参数
}
// 自定义事件不区分维度所属所有图表可用
// 自定义事件维度和指标分组只有一个暂设置为base
const eventDimensions = (tableId: string, eventInfoList: IEventInfoList[], variableParams) => {
  const metricDimension: IMetricDimension = {
    variableParams,
    metricList: [
      {
        id: 'base',
        result_table_id: tableId,
        metrics: [
          {
            englishName: 'event.count', // 自定义事件指标名固定为event.count
            dimension_list: [],
          },
        ],
      },
    ],
    dimensionList: [],
  };
  if (eventInfoList.length) {
    const dimensions = [];
    eventInfoList.forEach(item => {
      item.dimension_list.forEach(dim => {
        if (!dimensions.includes(dim.dimension_name) && dim.dimension_name !== 'target') {
          dimensions.push(dim.dimension_name);
        }
      });
    });
    metricDimension.dimensionList = dimensions.map(item => ({
      aliaName: item,
      englishName: item,
      groupId: 'base',
    }));
    metricDimension.metricList[0].metrics[0].dimension_list = dimensions.map(item => ({
      id: item,
      name: item,
    }));
  }
  return metricDimension;
};

const eventInit = (): hideOptions => {
  localStorage.setItem(COLLECT_CHART_TYPE, '0');
  return {
    chartTypeHide: true,
    viewSortHide: true,
    compareHide: true,
    searchHide: true,
    dashboardHide: true,
    convergeHide: true,
  };
};

export { eventDimensions, eventInit, type IMetricDimension };
