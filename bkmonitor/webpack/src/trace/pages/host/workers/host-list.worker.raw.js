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
 * 主机列表 Web Worker 运行时代码（纯 JS，无 import）。
 * 由主线程以 Blob URL 方式加载，避免微前端场景 webpack worker chunk / 跨域问题。
 * 逻辑与 utils/host-list-core.ts 保持同步。
 */

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
const HOST_STATUS_MAP = {
  '-1': { name: '未知' },
  0: { name: '正常' },
  2: { name: '无Agent' },
  3: { name: '无数据上报' },
};

const isHostNode = node => node.bk_host_id !== undefined;

const extractClusters = modules => {
  const map = new Map();
  for (const module of modules || []) {
    const index = (module.topo_link || []).findIndex(id => id.startsWith('set'));
    if (index > -1) {
      const id = module.topo_link[index];
      const name =
        (module.topo_link_display && module.topo_link_display[index]) ||
        (module.bk_obj_name_map && module.bk_obj_name_map.set) ||
        id;
      if (!map.has(id)) {
        map.set(id, { id, name });
      }
    }
  }
  return [...map.values()];
};

const createHostListRow = (row, metric = {}) => {
  const modules = row.module || [];
  const bkClusters = extractClusters(modules);
  const totalAlarmCount = (metric.alarm_count || []).reduce((pre, cur) => pre + (cur.count || 0), 0);
  return Object.assign({}, row || {}, metric || {}, {
    id: `${row.bk_host_innerip}`, // 使用内网 IP 作为唯一标识
    bkClusters,
    clusterNames: bkClusters.map(c => c.name).join(','),
    moduleNames: modules.map(m => m.bk_inst_name).join(','),
    processNames: (metric.component || []).map(c => c.display_name).join(','),
    rowId: String(row.bk_host_id != null ? row.bk_host_id : `${row.bk_host_innerip}|${row.bk_cloud_id}`),
    totalAlarmCount,
  });
};

const matchTopoNode = (row, node) => {
  if (!node || node.bk_obj_id === 'biz') {
    return true;
  }
  if (isHostNode(node)) {
    return String(row.bk_host_id) === String(node.bk_host_id);
  }
  return (row.module || []).some(module => (module.topo_link || []).includes(node.id));
};

const matchQuickCategory = (row, category) => {
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

const matchKeyword = (row, keyword) => {
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

const getRowFieldValues = (row, key) => {
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
      return [row[key]];
  }
};

const matchWhereItem = (row, item) => {
  const values = item.value || [];
  if (!values.length) {
    return true;
  }
  const method = item.method || 'eq';
  if (HOST_NUMBER_FILTER_FIELDS.has(item.key)) {
    const origin = item.key === 'alarm_count' ? row.totalAlarmCount : Number(row[item.key] != null ? row[item.key] : 0);
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
  // 集群模块字段：行数据 module.topo_link 为拓扑路径数组，候选项值为 JSON 编码的路径数组，需解析后逐条包含匹配
  if (['cluster_module'].includes(item.key)) {
    const curValue = item.value.map(v => {
      try {
        return JSON.parse(v);
      } catch (_e) {
        return [];
      }
    });
    const originValue = row?.module?.map(r => r.topo_link);
    return curValue.some(val => {
      return originValue.some(a => {
        return val.every(v => a.includes(v));
      });
    });
  }
  // 主机 ID / IP 类文本字段：使用 includes 包含模糊匹配（而非枚举精确匹配）
  if (
    ['bk_host_id', 'bk_host_innerip_v6', 'bk_host_outerip_v6', 'bk_host_innerip', 'bk_host_outerip'].includes(item.key)
  ) {
    const curValue = row?.[item.key];
    if (curValue && ['number', 'string'].includes(typeof curValue)) {
      return `${curValue}`.includes(item.value?.[0] || '');
    }
    return false;
  }
  // 通配符 key '*'：对整行做全文关键字搜索
  if (item.key === '*') {
    return matchKeyword(row, item.value?.[0] || '');
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

const matchWhere = (row, where) => {
  if (!where || !where.length) {
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

const computeCategoryStats = rows => {
  const stats = { alarm: 0, cpu: 0, mem: 0, disk: 0 };
  for (const row of rows) {
    if (row.totalAlarmCount > 0) stats.alarm += 1;
    if ((row.cpu_usage || 0) >= HOST_METRIC_OVER_THRESHOLD) stats.cpu += 1;
    if ((row.mem_usage || 0) >= HOST_METRIC_OVER_THRESHOLD) stats.mem += 1;
    if ((row.disk_in_use || 0) >= HOST_METRIC_OVER_THRESHOLD) stats.disk += 1;
  }
  return stats;
};

const sortRows = (rows, sort) => {
  if (!sort) {
    return rows;
  }
  const descending = sort.startsWith('-');
  const key = descending ? sort.slice(1) : sort;
  const getValue = row => (key === 'alarm_count' ? row.totalAlarmCount : Number(row[key] != null ? row[key] : 0));
  return [...rows].sort((a, b) => (descending ? getValue(b) - getValue(a) : getValue(a) - getValue(b)));
};

const buildFilterOptionsMap = rows => {
  const setMap = {
    bk_host_innerip: new Map(),
    bk_host_name: new Map(),
    bk_os_name: new Map(),
    bk_cloud_name: new Map(),
    status: new Map(),
    bk_cluster: new Map(),
    bk_inst_name: new Map(),
    display_name: new Map(),
  };

  /** 拓扑节点 ID → 名称 映射（用于去重合并） */
  const topoNameMap = {};
  /** 每行主机对应的拓扑路径列表（二维数组） */
  const topoList = [];

  for (const row of rows) {
    if (row.bk_host_innerip) setMap.bk_host_innerip.set(row.bk_host_innerip, row.bk_host_innerip);
    if (row.bk_host_name) setMap.bk_host_name.set(row.bk_host_name, row.bk_host_name);
    if (row.bk_os_name) setMap.bk_os_name.set(row.bk_os_name, row.bk_os_name);
    if (row.bk_cloud_name) setMap.bk_cloud_name.set(row.bk_cloud_name, row.bk_cloud_name);
    const statusConfig = HOST_STATUS_MAP[row.status] || HOST_STATUS_MAP[String(row.status)];
    setMap.status.set(String(row.status), (statusConfig && statusConfig.name) || String(row.status));
    for (const cluster of row.bkClusters) {
      setMap.bk_cluster.set(cluster.id, cluster.name);
    }
    for (const module of row.module || []) {
      if (module.bk_inst_name) {
        setMap.bk_inst_name.set(module.bk_inst_name, module.bk_inst_name);
      }
      const topo = module.topo_link.map((id, index) => {
        topoNameMap[id] = module.topo_link_display[index];
        return {
          id,
          name: module.topo_link_display[index],
        };
      });
      topoList.push(topo);
    }
    for (const component of row.component || []) {
      if (component.display_name) setMap.display_name.set(component.display_name, component.display_name);
    }
  }
  const result = new Map();
  for (const [field, valueMap] of Object.entries(setMap)) {
    result.set(
      field,
      [...valueMap.entries()].map(([id, name]) => ({ id, name }))
    );
  }
  // 处理集群模块
  const clusterModuleTreeList = [];
  /** 拓扑节点 ID → 树节点 映射（用于去重合并相同路径的节点） */
  const nodeMap = {};
  /** 创建树节点（id + name + children） */
  const createNode = data => ({
    id: data.id,
    name: data.name,
    children: [],
  });
  for (let i = 0; i < topoList.length; i++) {
    const pathList = topoList[i];
    let parentNode = null;

    for (let j = 0; j < pathList.length; j++) {
      const nodeData = pathList[j];
      if (!nodeMap[nodeData.id]) {
        nodeMap[nodeData.id] = createNode(nodeData);
        if (parentNode) {
          parentNode.children.push(nodeMap[nodeData.id]);
        } else {
          clusterModuleTreeList.push(nodeMap[nodeData.id]);
        }
      }
      parentNode = nodeMap[nodeData.id];
    }
  }

  // 追加集群模块字段的选项树
  result.set('cluster_module', clusterModuleTreeList);
  return result;
};

let rawRows = [];
let filterOptionsMap = new Map();

const optionsMapToRecord = map => {
  const record = {};
  for (const [key, value] of map.entries()) {
    record[key] = value;
  }
  return record;
};

/** 快捷分类 + where + keyword 过滤 */
const filterByConditions = (rows, params) =>
  rows.filter(
    row =>
      matchQuickCategory(row, params.activeCategory) &&
      matchWhere(row, params.where) &&
      matchKeyword(row, params.keyword)
  );

/** 拓扑 + 条件过滤后的全量行（不含分页） */
const getFilteredRows = params => {
  const nodeScopedRows = rawRows.filter(row => matchTopoNode(row, params.selectedNode));
  return filterByConditions(nodeScopedRows, params);
};

const runCompute = params => {
  const nodeScopedRows = rawRows.filter(row => matchTopoNode(row, params.selectedNode));
  const categoryStats = computeCategoryStats(nodeScopedRows);
  const filteredRows = filterByConditions(nodeScopedRows, params);
  const sortedRows = sortRows(filteredRows, params.sortInfo);
  const total = sortedRows.length;
  const start = (params.page - 1) * params.pageSize;
  const pagedRows = sortedRows.slice(start, start + params.pageSize);
  return { categoryStats, pagedRows, total };
};

self.onmessage = event => {
  const message = event.data;
  switch (message.type) {
    case 'INIT_BASE': {
      rawRows = message.baseList.map(row => createHostListRow(row));
      filterOptionsMap = buildFilterOptionsMap(rawRows);
      self.postMessage({
        filterOptionsMap: optionsMapToRecord(filterOptionsMap),
        rawRowCount: rawRows.length,
        requestId: message.requestId,
        type: 'INIT_BASE_DONE',
      });
      break;
    }
    case 'MERGE_METRICS': {
      const metricListMap = message.metricListMap;
      rawRows = rawRows.map(row => createHostListRow(row, metricListMap[row.bk_host_id]));
      filterOptionsMap = buildFilterOptionsMap(rawRows);
      self.postMessage({
        filterOptionsMap: optionsMapToRecord(filterOptionsMap),
        requestId: message.requestId,
        type: 'MERGE_METRICS_DONE',
      });
      break;
    }
    case 'COMPUTE': {
      const result = runCompute(message.params);
      self.postMessage({
        categoryStats: result.categoryStats,
        pagedRows: result.pagedRows,
        total: result.total,
        requestId: message.requestId,
        type: 'COMPUTE_DONE',
      });
      break;
    }
    case 'GET_FILTER_OPTIONS': {
      const list = filterOptionsMap.get(message.field) || [];
      const search = (message.search || '').toLowerCase();
      const filtered = search ? list.filter(item => String(item.name).toLowerCase().includes(search)) : list;
      self.postMessage({
        requestId: message.requestId,
        result: {
          count: filtered.length,
          list: filtered.slice(0, message.limit || 200),
        },
        type: 'GET_FILTER_OPTIONS_DONE',
      });
      break;
    }
    case 'GET_SELECTED_IPS': {
      const keySet = new Set(message.rowKeys.map(String));
      // 表格 rowKey 为 id（内网 IP），同时兼容历史 rowId
      const ips = rawRows
        .filter(row => keySet.has(String(row.id)) || keySet.has(String(row.rowId)))
        .map(row => row.bk_host_innerip)
        .filter(Boolean);
      self.postMessage({
        ips,
        requestId: message.requestId,
        type: 'GET_SELECTED_IPS_DONE',
      });
      break;
    }
    // 返回完整 filterOptionsMap，供主线程构建字段展示名称映射
    case 'GET_FILTER_OPTIONS_MAP': {
      self.postMessage({
        filterOptionsMap: optionsMapToRecord(filterOptionsMap),
        requestId: message.requestId,
        type: 'GET_FILTER_OPTIONS_MAP_DONE',
      });
      break;
    }
    case 'GET_FILTERED_ROW_KEYS': {
      // 跨页全选：返回当前过滤条件下的全量行 key（与表格 rowKey=id 一致）
      const rowKeys = getFilteredRows(message.params).map(row => row.id);
      self.postMessage({
        requestId: message.requestId,
        rowKeys,
        type: 'GET_FILTERED_ROW_KEYS_DONE',
      });
      break;
    }
    default:
      break;
  }
};
