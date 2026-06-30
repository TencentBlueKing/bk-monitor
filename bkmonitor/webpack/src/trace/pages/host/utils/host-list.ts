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

import { ECondition } from '../../../components/retrieval-filter/typing';
import { HOST_METRIC_OVER_THRESHOLD, HOST_NUMBER_FILTER_FIELDS, HOST_STATUS_MAP } from '../constants/host-list';
import { isHostNode } from './topo-tree';

import type { IValue, IWhereItem } from '../../../components/retrieval-filter/typing';
import type { EHostQuickCategory, IHostCluster, IHostListRow } from '../types/host-list';
import type { IHostBaseInfo, IHostMetricInfo, IHostModule } from '../types/host';
import type { IHostTopoTreeNode } from '../types/topo';

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

/**
 * @description 在原始主机数据上计算前端派生字段，生成表格行。
 * 派生字段用于排序、模糊搜索、快捷过滤与唯一标识，避免渲染时重复计算。
 */
export const createHostListRow = (raw: IHostBaseInfo | IHostMetricInfo): IHostListRow => {
  const metric = raw as IHostMetricInfo;
  const modules = raw.module || [];
  const bkClusters = extractClusters(modules);
  const totalAlarmCount = (metric.alarm_count || []).reduce((pre, cur) => pre + (cur.count || 0), 0);
  return {
    ...(metric as IHostMetricInfo),
    bkClusters,
    clusterNames: bkClusters.map(c => c.name).join(','),
    moduleNames: modules.map(m => m.bk_inst_name).join(','),
    processNames: (metric.component || []).map(c => c.display_name).join(','),
    rowId: String(raw.bk_host_id ?? `${raw.bk_host_innerip}|${raw.bk_cloud_id}`),
    totalAlarmCount,
  };
};

/** 判断主机是否归属选中的拓扑节点（节点：按 topo_link 命中；主机：按 bk_host_id 命中） */
export const matchTopoNode = (row: IHostListRow, node: IHostTopoTreeNode | null): boolean => {
  if (!node || node.bk_obj_id === 'biz') {
    // 业务根节点 / 未选中 → 不过滤
    return true;
  }
  if (isHostNode(node)) {
    return String(row.bk_host_id) === String(node.bk_host_id);
  }
  return (row.module || []).some(module => (module.topo_link || []).includes(node.id));
};

/** 判断主机是否命中快捷过滤分类 */
export const matchQuickCategory = (row: IHostListRow, category: EHostQuickCategory | ''): boolean => {
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

/** 关键字模糊匹配（覆盖 IP / 主机名 / OS / 管控区域 / 集群 / 模块 / 进程） */
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

/** 取出某过滤字段在行上的可比较值集合 */
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

/** 单个 where 条件匹配 */
const matchWhereItem = (row: IHostListRow, item: IWhereItem): boolean => {
  const values = item.value || [];
  if (!values.length) {
    return true;
  }
  const method = item.method || 'eq';
  // 数值类比较（> >= < <= =）
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
      // eq：行命中所选任一值
      return matchValues.some(v => rowValues.includes(v));
  }
};

/** retrieval-filter where 条件匹配（按条件项的 and/or 顺序组合） */
export const matchWhere = (row: IHostListRow, where: IWhereItem[]): boolean => {
  if (!where?.length) {
    return true;
  }
  let result = true;
  where.forEach((item, index) => {
    const itemMatch = matchWhereItem(row, item);
    if (index === 0) {
      result = itemMatch;
    } else if (item.condition === ECondition.or) {
      result = result || itemMatch;
    } else {
      result = result && itemMatch;
    }
  });
  return result;
};

/** 统计各快捷过滤分类命中的主机数 */
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

/** 按排序规则排序（sort 为 tdesign 字符串格式：`-key` 倒序 / `key` 正序） */
export const sortRows = (rows: IHostListRow[], sort: string): IHostListRow[] => {
  if (!sort) {
    return rows;
  }
  const descending = sort.startsWith('-');
  const key = (descending ? sort.slice(1) : sort) as keyof IHostListRow;
  const getValue = (row: IHostListRow) => (key === 'alarm_count' ? row.totalAlarmCount : Number(row[key] ?? 0));
  return [...rows].sort((a, b) => (descending ? getValue(b) - getValue(a) : getValue(a) - getValue(b)));
};

/**
 * @description 基于全量数据构建过滤候选项映射（供 retrieval-filter 的 getValueFn 消费）。
 * 旧版主机监控的过滤选项即由前端全量数据组合生成，这里沿用该思路。
 */
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
