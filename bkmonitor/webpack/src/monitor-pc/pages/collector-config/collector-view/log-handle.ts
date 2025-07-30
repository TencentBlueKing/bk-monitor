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
// 日志采集特殊处理
import { COLLECT_CHART_TYPE } from '../../../constant/constant';
import { selectAllItemKey } from './variable-settings.tsx';

import type { IFilterCondition } from '../../data-retrieval/typings/index';

interface hideOptions {
  chartTypeHide?: boolean; // 切换一行多图隐藏
  compareHide?: boolean; // 对比隐藏
  convergeHide?: boolean; // 汇聚隐藏
  dashboardHide?: boolean; // 通用图表隐藏
  searchHide?: boolean; // 搜索隐藏
  viewSortHide?: boolean; // 视图设置隐藏
}
/**
 * @description: 日志采集特殊处理(隐藏不需要的功能)
 * @param {string} collectType
 * @return {*}
 */
const logCollectInit = (collectType: string): hideOptions => {
  if (collectType === 'Log') {
    localStorage.setItem(COLLECT_CHART_TYPE, '0');
    return {
      chartTypeHide: true,
      viewSortHide: true,
      compareHide: true,
      searchHide: true,
      dashboardHide: true,
    };
  }
  return {
    chartTypeHide: false,
    viewSortHide: false,
    compareHide: false,
    searchHide: false,
    dashboardHide: false,
  };
};

/**
 * @description: 日志table图表变量替换
 * @param {*} targetData
 * @param {object} variableResult
 * @return {*}
 */
const tablePanelGroupByChange = (targetData, variableResult: { key: string; name: string; value: string[] }[]) => {
  const groupBy: string[] = [];
  const filterDict = {};
  variableResult.forEach(variable => {
    if (variable.value.length) {
      if (variable.value[0] === selectAllItemKey) {
        groupBy.push(variable.key);
      } else {
        groupBy.push(variable.key);
        filterDict[variable.key] = [...variable.value, ''];
      }
    }
  });
  if (groupBy.length) {
    targetData.group_by = groupBy;
    targetData.filter_dict = filterDict;
    return targetData;
  }
  targetData.group_by = groupBy;
  return targetData;
};

/**
 * @description: 传入事件检索类型图表参数
 * @param {*} handleGroupsData
 * @param {*} Method
 * @return {*}
 */
const logEventRetrievalParams = (handleGroupsData, variableData, Method = 'AVG'): IFilterCondition.VarParams | null => {
  let params = null;
  if (handleGroupsData?.length) {
    const LogPanels = handleGroupsData.filter(group => group.panels.length)[0].panels;
    const timeSeriesParams = LogPanels.find(p => p.type === 'graph').targets[0].data.query_configs;
    const logParms = LogPanels.find(p => p.type === 'table')?.targets[0].data;
    if (logParms && timeSeriesParams[0]) {
      params = compileVariableData(
        {
          data_source_label: timeSeriesParams[0].data_source_label,
          data_type_label: timeSeriesParams[0].data_type_label,
          metric_field: timeSeriesParams[0].metrics[0].field,
          query_string: logParms.query_string,
          result_table_id: logParms.result_table_id,
          group_by: timeSeriesParams[0].group_by,
          filter_dict: timeSeriesParams[0].filter_dict,
          method: Method,
          where: timeSeriesParams[0].where,
        },
        variableData
      );
    }
  }
  return params;
};

// 变量替换
const compileVariableData = (data, variableData) => {
  let params = JSON.stringify(data);
  variableData &&
    Object.keys(variableData).forEach(key => {
      params = params.replace(new RegExp(`\\${key}`, 'g'), variableData[key]);
    });
  params = JSON.parse(params);
  return params;
};

export { type hideOptions, logCollectInit, logEventRetrievalParams, tablePanelGroupByChange };
