/*
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

import type { IRouteItem } from './type';
/* 搜索内容的类型 */
export enum ESearchPopoverType {
  // 历史搜索
  localHistoryList = 'localHistoryList',
  // 接口搜索结果
  searchList = 'searchList',
}
/* 搜索的类型 */
export enum ESearchType {
  // alert: 告警
  alert = 'alert',
  // apm_application: APM应用
  apm_application = 'apm_application',
  // bcs集群
  bcs_cluster = 'bcs_cluster',
  // host: 主机
  host = 'host',
  // strategy: 策略
  strategy = 'strategy',
  // trace: Trace
  trace = 'trace',
}
export interface IDataItem {
  [key: string]: any;
}
/* status */
export const EStatusType = {
  deleted: '已删除',
  disabled: '已停用',
  shielded: '已屏蔽',
};
/* 严重程度 */
export const DEFAULT_SEVERITY_LIST = ['FATAL', 'WARNING', 'INFO'];

/* 告警级别 */
export enum EAlertLevel {
  FATAL = 1,
  WARNING = 2,
  // eslint-disable-next-line perfectionist/sort-enums
  INFO = 3,
}

/* functionName */
export const EFunctionNameType = {
  dashboard: '仪表盘',
  apm_service: '服务',
  log_retrieve: '日志检索',
  metric_retrieve: '指标集',
  // TODO
};
export const RECENT_FAVORITE_LIST_KEY = 'recent_favorite_list_key'.toLocaleUpperCase();
export const RECENT_ALARM_TIME_RANGE_KEY = 'recent_alarm_time_range_key'.toLocaleUpperCase();
export const RECENT_ALARM_SEVERITY_KEY = 'recent_alarm_severity_key'.toLocaleUpperCase();
/**
 * @description: 处理树形结构的数据，将数据统一为平级的数据
 * @param {IRouteItem[]} tree
 * @return {*}
 */
export function flattenRoute(tree: IRouteItem[]) {
  const result = [];
  const traverse = node => {
    if (!node) return;
    result.push(node);
    if (node.children && node.children.length > 0) {
      node.children.map(child => traverse(child));
    }
  };
  tree.map(rootNode => traverse(rootNode));
  return result;
}
/**
 * @description: 在图表数据没有单位或者单位不一致时则不做单位转换 y轴label的转换用此方法做计数简化
 * @param {number} num
 * @return {*}
 */
export function handleYAxisLabelFormatter(num: number): string {
  const si = [
    { value: 1, symbol: '' },
    { value: 1e3, symbol: 'K' },
    { value: 1e6, symbol: 'M' },
    { value: 1e9, symbol: 'G' },
    { value: 1e12, symbol: 'T' },
    { value: 1e15, symbol: 'P' },
    { value: 1e18, symbol: 'E' },
  ];
  const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
  let i: number;
  for (i = si.length - 1; i > 0; i--) {
    if (num >= si[i].value) {
      break;
    }
  }
  return (num / si[i].value).toFixed(3).replace(rx, '$1') + si[i].symbol;
}

/**
 * @description 输入字段匹配字段高亮
 * @param searchValue 输入的字段
 * @param listData
 * @param dataKeys 需要匹配的key列表
 * @returns
 */
export function highLightContent(searchValue: string, listData: IDataItem[], dataKeys: string[]) {
  const searchKey = searchValue.trim().split(' ');
  return listData.map(data => {
    const copyData = JSON.parse(JSON.stringify(data));
    dataKeys.map(key => {
      copyData[`${key}Search`] = searchKey[0]
        ? data[key].replace(new RegExp(`(${searchKey.join('|')})`, 'gi'), `<span class="highlight">$1</span>`)
        : data[key];
    });
    return copyData;
  });
}
