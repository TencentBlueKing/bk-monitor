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

/**
 * 主机列表纯计算逻辑（无运行时外部依赖，供主线程 utils 使用）。
 * Web Worker 运行时代码在 workers/host-list.worker.raw.js（Blob 方式加载），逻辑与此文件保持同步。
 */

import { isObject } from 'monitor-common/utils';

import type { IValue, IWhereItem } from '../../../components/retrieval-filter/typing';
import type { IHostBaseInfo, IHostMetricInfo, IHostModule } from '../types/host';
import type { EHostQuickCategory, IHostCluster, IHostListRow } from '../types/host-list';
import type { IHostTopoTreeNode } from '../types/topo';

/** 与 constants/host-list 保持一致，内联避免 Worker 引入额外 chunk */
const HOST_METRIC_OVER_THRESHOLD = 80;
const HOST_NUMBER_FILTER_FIELDS = new Set([
  'cpu_usage',
  'mem_usage',
  'disk_in_use',
  'io_util',
  'psc_mem_usage',
  'cpu_load',
  'alarm_count',
]);
const HOST_STATUS_MAP: Record<number, { name: string }> = {
  [-1]: { name: '未知' },
  0: { name: '正常' },
  2: { name: '无Agent' },
  3: { name: '无数据上报' },
};

const isHostNode = (node: IHostTopoTreeNode): node is IHostTopoTreeNode & { bk_host_id: number } =>
  (node as { bk_host_id?: number }).bk_host_id !== undefined;

/** 从模块的 topo_link 中提取集群（set 层）信息 */
const extractClusters = (modules: IHostModule[]): IHostCluster[] => {
  const map = new Map<string, IHostCluster>();
  for (const module of modules || []) {
    const index = (module.topo_link || []).findIndex(id => id.startsWith('set'));
    if (index > -1) {
      const id = module.topo_link[index];
      const name = module.topo_link_display?.[index] || module.bk_obj_name_map?.set || id;
      if (!map.has(id)) {
        map.set(id, { id, name });
      }
    }
  }
  return [...map.values()];
};

export const createHostListRow = (row: IHostBaseInfo, metric?: IHostMetricInfo): IHostListRow => {
  const metricWithDefault = (metric ?? {}) as IHostMetricInfo;
  const modules = row.module || [];
  const bkClusters = extractClusters(modules);
  const totalAlarmCount = (metricWithDefault.alarm_count || []).reduce((pre, cur) => pre + (cur.count || 0), 0);
  return {
    ...(row ?? {}),
    ...(metricWithDefault ?? {}),
    bkClusters,
    clusterNames: bkClusters.map(c => c.name).join(','),
    moduleNames: modules.map(m => m.bk_inst_name).join(','),
    processNames: (metricWithDefault.component || []).map(c => c.display_name).join(','),
    rowId: String(row.bk_host_id ?? `${row.bk_host_innerip}|${row.bk_cloud_id}`),
    totalAlarmCount,
  };
};

export const matchTopoNode = (row: IHostListRow, node: IHostTopoTreeNode | null): boolean => {
  if (!node || node.bk_obj_id === 'biz') {
    return true;
  }
  if (isHostNode(node)) {
    return String(row.bk_host_id) === String(node.bk_host_id);
  }
  return (row.module || []).some(module => (module.topo_link || []).includes(node.id));
};

export const matchQuickCategory = (row: IHostListRow, category: '' | EHostQuickCategory): boolean => {
  switch (category) {
    case 'alarm':
      return row.totalAlarmCount > 0;
    case 'cpu':
      return (row.cpu_usage || 0) >= HOST_METRIC_OVER_THRESHOLD;
    case 'mem':
      return (row.mem_usage || 0) >= HOST_METRIC_OVER_THRESHOLD;
    case 'disk':
      return (row.disk_in_use || 0) >= HOST_METRIC_OVER_THRESHOLD;
    default:
      return true;
  }
};

export const matchKeyword = (row: IHostListRow, keyword: string): boolean => {
  const kw = keyword.trim().toLowerCase();
  if (!kw) {
    return true;
  }
  const fields = [
    row.bk_host_innerip,
    row.bk_host_innerip_v6,
    row.bk_host_outerip,
    row.bk_host_name,
    row.display_name,
    row.bk_os_name,
    row.bk_cloud_name,
    row.clusterNames,
    row.moduleNames,
    row.processNames,
  ];
  return fields.some(field => !!field && String(field).toLowerCase().includes(kw));
};

const getRowFieldValues = (row: IHostListRow, key: string): (number | string)[] => {
  switch (key) {
    case 'bk_cluster':
      return row.bkClusters.map(c => c.id);
    case 'bk_inst_name':
      return (row.module || []).map(m => m.bk_inst_name);
    case 'display_name':
      return (row.component || []).map(c => c.display_name);
    case 'status':
      return [String(row.status)];
    default:
      return [row[key as keyof IHostListRow] as number | string];
  }
};

const matchWhereItem = (row: IHostListRow, item: IWhereItem): boolean => {
  const values = item.value || [];
  if (!values.length) {
    return true;
  }
  const method = item.method || 'eq';
  if (HOST_NUMBER_FILTER_FIELDS.has(item.key)) {
    const origin = item.key === 'alarm_count' ? row.totalAlarmCount : Number(row[item.key as keyof IHostListRow] ?? 0);
    const target = Number(values[0]);
    if (Number.isNaN(target)) {
      return true;
    }
    switch (method) {
      case 'gt':
        return origin > target;
      case 'gte':
        return origin >= target;
      case 'lt':
        return origin < target;
      case 'lte':
        return origin <= target;
      default:
        return origin === target;
    }
  }
  const rowValues = getRowFieldValues(row, item.key).map(v => String(v));
  const matchValues = values.map(v => String(v));
  switch (method) {
    case 'ne':
      return !matchValues.some(v => rowValues.includes(v));
    case 'include':
      return matchValues.some(v => rowValues.some(rv => rv.includes(v)));
    case 'exclude':
      return !matchValues.some(v => rowValues.some(rv => rv.includes(v)));
    default:
      return matchValues.some(v => rowValues.includes(v));
  }
};

export const matchWhere = (row: IHostListRow, where: IWhereItem[]): boolean => {
  if (!where?.length) {
    return true;
  }
  let result = true;
  for (let index = 0; index < where.length; index += 1) {
    const item = where[index];
    const itemMatch = matchWhereItem(row, item);
    if (index === 0) {
      result = itemMatch;
    } else if (item.condition === 'or') {
      result = result || itemMatch;
    } else {
      result = result && itemMatch;
    }
  }
  return result;
};

export const computeCategoryStats = (rows: IHostListRow[]) => {
  const stats = { alarm: 0, cpu: 0, mem: 0, disk: 0 };
  for (const row of rows) {
    if (row.totalAlarmCount > 0) stats.alarm += 1;
    if ((row.cpu_usage || 0) >= HOST_METRIC_OVER_THRESHOLD) stats.cpu += 1;
    if ((row.mem_usage || 0) >= HOST_METRIC_OVER_THRESHOLD) stats.mem += 1;
    if ((row.disk_in_use || 0) >= HOST_METRIC_OVER_THRESHOLD) stats.disk += 1;
  }
  return stats;
};

export const sortRows = (rows: IHostListRow[], sort: string): IHostListRow[] => {
  if (!sort) {
    return rows;
  }
  const descending = sort.startsWith('-');
  const key = (descending ? sort.slice(1) : sort) as keyof IHostListRow;
  const getValue = (row: IHostListRow) => (key === 'alarm_count' ? row.totalAlarmCount : Number(row[key] ?? 0));
  return [...rows].sort((a, b) => (descending ? getValue(b) - getValue(a) : getValue(a) - getValue(b)));
};

export const buildFilterOptionsMap = (rows: IHostListRow[]): Map<string, IValue[]> => {
  const setMap: Record<string, Map<string, string>> = {
    bk_host_innerip: new Map(),
    bk_host_name: new Map(),
    bk_os_name: new Map(),
    bk_cloud_name: new Map(),
    status: new Map(),
    bk_cluster: new Map(),
    bk_inst_name: new Map(),
    display_name: new Map(),
  };
  for (const row of rows) {
    if (row.bk_host_innerip) setMap.bk_host_innerip.set(row.bk_host_innerip, row.bk_host_innerip);
    if (row.bk_host_name) setMap.bk_host_name.set(row.bk_host_name, row.bk_host_name);
    if (row.bk_os_name) setMap.bk_os_name.set(row.bk_os_name, row.bk_os_name);
    if (row.bk_cloud_name) setMap.bk_cloud_name.set(row.bk_cloud_name, row.bk_cloud_name);
    setMap.status.set(String(row.status), HOST_STATUS_MAP[row.status]?.name || String(row.status));
    for (const cluster of row.bkClusters) {
      setMap.bk_cluster.set(cluster.id, cluster.name);
    }
    for (const module of row.module || []) {
      if (module.bk_inst_name) setMap.bk_inst_name.set(module.bk_inst_name, module.bk_inst_name);
    }
    for (const component of row.component || []) {
      if (component.display_name) setMap.display_name.set(component.display_name, component.display_name);
    }
  }
  const result = new Map<string, IValue[]>();
  for (const [field, valueMap] of Object.entries(setMap)) {
    result.set(
      field,
      [...valueMap.entries()].map(([id, name]) => ({ id, name }))
    );
  }
  return result;
};

export const defaultFieldsSort = [
  ['bk_cloud_id', 'bk_target_cloud_id'],
  ['bk_host_id', 'bk_host_id'],
  ['ip', 'bk_target_ip'],
];

/** 根据当前请求接口数据的映射规则生成id */
export const handleCreateItemId = (
  item: object,
  isFilterDict = false,
  fieldsSort?: Array<[string, string]>,
  splitChar = '-'
) => {
  const localFieldsSort = fieldsSort || defaultFieldsSort;
  let isExist = true;
  const itemIds = [];
  for (const set of localFieldsSort) {
    const [itemKey, filterDictKey] = set;
    const key = isFilterDict ? filterDictKey : itemKey;
    let value = item[key];
    if (value === undefined && isExist) {
      isExist = false;
    }
    value = isObject(value) ? value.value : value;
    itemIds.push(value);
  }
  return isExist ? itemIds.filter(item => item !== undefined).join(splitChar) : null;
};

export const handleCreateCompares = (data: object, fieldsSort?: Array<[string, string]>): CompareTarget => {
  const localFieldsSort = fieldsSort || defaultFieldsSort;
  let isExist = true;
  const result = localFieldsSort.reduce((total, cur) => {
    const [itemKey, filterDictKey] = cur;
    let value = data?.[itemKey];
    if (value === undefined && isExist) {
      isExist = false;
    }
    value = isObject(value) ? value.value : value;
    total[filterDictKey] = value;
    return total;
  }, {});
  return isExist ? result : null;
};
