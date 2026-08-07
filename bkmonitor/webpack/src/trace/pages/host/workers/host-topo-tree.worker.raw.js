/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 主机拓扑树 Web Worker（纯 JS，无 import）。
 *
 * Worker 只向主线程返回当前可视区附近的扁平节点。即使树包含百万个节点，
 * 主线程也无需构建整棵树的组件状态或持有完整的可见节点列表。
 */

/** 节点列表 */
let nodes = [];
/** 根节点列表 */
let roots = [];
/** 节点索引 */
let nodeIndexById = new Map();
/** 展开的节点 ID 集合 */
let expandedIds = new Set();
/** 搜索折叠的节点 ID 集合 */
let searchCollapsedIds = new Set();
/** 搜索展开的节点 ID 集合 */
let searchExpandedIds = new Set();
/** 搜索折叠所有节点 */
let searchCollapseAll = false;
/** 隐藏空节点 */
let hideEmptyNode = true;
/** 搜索值 */
let searchValue = '';
/** 范围缓存 */
let rangeCache = null;

/** 判断是否为主机节点 */
const isHostNode = node => node.bk_host_id !== undefined;

/** 获取搜索文本 */
const getSearchText = node => {
  const fields = isHostNode(node)
    ? [node.ip, node.bk_host_innerip, node.bk_host_name, node.alias_name, node.display_name]
    : [node.name, node.bk_inst_name];
  return fields
    .filter(Boolean)
    .map(value => String(value).toLowerCase())
    .join('\n');
};

/** 构建索引 */
const buildIndex = treeData => {
  nodes = [];
  roots = [];
  nodeIndexById = new Map();
  expandedIds = new Set();
  searchCollapsedIds = new Set();
  searchExpandedIds = new Set();
  searchCollapseAll = false;

  const stack = [];
  for (let index = treeData.length - 1; index >= 0; index -= 1) {
    stack.push({ depth: 0, node: treeData[index], parentIndex: -1 });
  }

  while (stack.length) {
    const current = stack.pop();
    const source = current.node;
    const children = Array.isArray(source.children) ? source.children : [];
    const data = source;
    delete data.children;

    const nodeIndex = nodes.length;
    const entry = {
      children: children.length ? [] : null,
      data,
      depth: current.depth,
      directMatch: false,
      hasMatchingDescendant: false,
      hostCount: isHostNode(source) ? 1 : 0,
      included: true,
      isHost: isHostNode(source),
      parentIndex: current.parentIndex,
      searchText: getSearchText(source),
      visibleCount: 1,
    };
    nodes.push(entry);
    nodeIndexById.set(String(source.id), nodeIndex);

    if (source.isOpen) {
      expandedIds.add(String(source.id));
    }
    if (current.parentIndex === -1) {
      roots.push(nodeIndex);
    } else {
      nodes[current.parentIndex].children.push(nodeIndex);
    }

    for (let index = children.length - 1; index >= 0; index -= 1) {
      stack.push({
        depth: current.depth + 1,
        node: children[index],
        parentIndex: nodeIndex,
      });
    }
  }

  for (let index = nodes.length - 1; index >= 0; index -= 1) {
    const entry = nodes[index];
    if (!entry.isHost) {
      for (const childIndex of entry.children || []) {
        entry.hostCount += nodes[childIndex].hostCount;
      }
    }
  }
};

/** 判断节点是否展开 */
const isBranchExpanded = entry => {
  if (!entry.children?.length) {
    return false;
  }
  const id = String(entry.data.id);
  if (searchValue) {
    return searchCollapseAll ? searchExpandedIds.has(id) : !searchCollapsedIds.has(id);
  }
  return expandedIds.has(id);
};

/** 计算可见节点数量 */
const calculateVisibleCount = index => {
  const entry = nodes[index];
  if (!entry.included) {
    entry.visibleCount = 0;
    return 0;
  }
  let count = 1;
  if (isBranchExpanded(entry)) {
    for (const childIndex of entry.children || []) {
      count += nodes[childIndex].visibleCount;
    }
  }
  entry.visibleCount = count;
  return count;
};

/** 重新计算可见性 */
const recomputeVisibility = () => {
  const keyword = searchValue.trim().toLowerCase();
  for (let index = nodes.length - 1; index >= 0; index -= 1) {
    const entry = nodes[index];
    const baseVisible = !hideEmptyNode || entry.isHost || entry.hostCount > 0;
    entry.directMatch = !!keyword && baseVisible && entry.searchText.includes(keyword);
    entry.hasMatchingDescendant = entry.directMatch;
    if (baseVisible) {
      for (const childIndex of entry.children || []) {
        entry.hasMatchingDescendant ||= nodes[childIndex].hasMatchingDescendant;
      }
    }
  }
  const stack = roots.map(index => ({ ancestorMatched: false, index })).reverse();
  while (stack.length) {
    const { ancestorMatched, index } = stack.pop();
    const entry = nodes[index];
    const baseVisible = !hideEmptyNode || entry.isHost || entry.hostCount > 0;
    entry.included = baseVisible && (!keyword || ancestorMatched || entry.hasMatchingDescendant);
    const childAncestorMatched = ancestorMatched || entry.directMatch;
    const children = entry.children || [];
    for (let childIndex = children.length - 1; childIndex >= 0; childIndex -= 1) {
      stack.push({ ancestorMatched: childAncestorMatched, index: children[childIndex] });
    }
  }
  for (let index = nodes.length - 1; index >= 0; index -= 1) {
    calculateVisibleCount(index);
  }
};

/** 获取总节点数量 */
const getTotal = () => roots.reduce((total, index) => total + nodes[index].visibleCount, 0);

/** 转换为视图行 */
const toViewRow = entry => ({
  ...entry.data,
  depth: entry.depth,
  hasChildren: !!entry.children?.length,
  hostCount: entry.hostCount,
  isExpanded: isBranchExpanded(entry),
});

/** 创建迭代器 */
const createIterator = () => ({
  offset: 0,
  stack: [{ indices: roots, position: 0 }],
});

/**
 * 迭代下一个可见节点。跳过折叠子树时使用 visibleCount 整段前进，
 * 同级节点按游标逐个推进，避免把百万个 child index 一次性压入临时栈。
 */
const nextVisibleNode = (iterator, targetOffset) => {
  while (iterator.stack.length) {
    const frame = iterator.stack[iterator.stack.length - 1];
    if (frame.position >= frame.indices.length) {
      iterator.stack.pop();
      continue;
    }
    const index = frame.indices[frame.position];
    frame.position += 1;
    const entry = nodes[index];
    if (!entry.visibleCount) {
      continue;
    }
    if (iterator.offset + entry.visibleCount <= targetOffset) {
      iterator.offset += entry.visibleCount;
      continue;
    }

    const nodeOffset = iterator.offset;
    iterator.offset += 1;
    if (isBranchExpanded(entry)) {
      iterator.stack.push({ indices: entry.children, position: 0 });
    }
    if (nodeOffset >= targetOffset) {
      return toViewRow(entry);
    }
  }
  return null;
};

/** 无效化范围缓存 */
const invalidateRangeCache = () => {
  rangeCache = null;
};

/** 获取范围 */
const getRange = (start, end) => {
  if (rangeCache && start >= rangeCache.start && start <= rangeCache.end) {
    while (rangeCache.end < end) {
      const row = nextVisibleNode(rangeCache.iterator, rangeCache.end);
      if (!row) {
        break;
      }
      rangeCache.rows.push(row);
      rangeCache.end += 1;
    }
    const result = rangeCache.rows.slice(start - rangeCache.start, end - rangeCache.start);
    const trimCount = start - rangeCache.start;
    if (trimCount > 0) {
      rangeCache.rows.splice(0, trimCount);
      rangeCache.start = start;
    }
    return result;
  }

  const iterator = createIterator();
  const rows = [];
  while (start + rows.length < end) {
    const row = nextVisibleNode(iterator, start + rows.length);
    if (!row) {
      break;
    }
    rows.push(row);
  }
  rangeCache = {
    end: start + rows.length,
    iterator,
    rows: [...rows],
    start,
  };
  return rows;
};

/** 刷新祖先计数 */
const refreshAncestorCounts = index => {
  let currentIndex = index;
  while (currentIndex >= 0) {
    calculateVisibleCount(currentIndex);
    currentIndex = nodes[currentIndex].parentIndex;
  }
};

/** 切换节点展开状态 */
const toggleNode = (id, expanded) => {
  const index = nodeIndexById.get(String(id));
  if (index === undefined) {
    return;
  }
  const entry = nodes[index];
  const targetExpanded = expanded === undefined ? !isBranchExpanded(entry) : expanded;
  const idKey = String(id);
  if (searchValue) {
    if (searchCollapseAll) {
      if (targetExpanded) {
        searchExpandedIds.add(idKey);
      } else {
        searchExpandedIds.delete(idKey);
      }
    } else if (targetExpanded) {
      searchCollapsedIds.delete(idKey);
    } else {
      searchCollapsedIds.add(idKey);
    }
  } else if (targetExpanded) {
    expandedIds.add(idKey);
  } else {
    expandedIds.delete(idKey);
  }
  refreshAncestorCounts(index);
  invalidateRangeCache();
};

/** 发送状态 */
const postState = (requestId, start, end, type) => {
  self.postMessage({
    requestId,
    rows: getRange(start, end),
    total: getTotal(),
    type,
  });
};

/** 获取节点在可视列表中的偏移量 */
const getNodeOffset = targetId => {
  const targetIndex = nodeIndexById.get(String(targetId));
  if (targetIndex === undefined) return -1;
  const iterator = createIterator();
  let offset = 0;
  while (iterator.stack.length) {
    const frame = iterator.stack[iterator.stack.length - 1];
    if (frame.position >= frame.indices.length) {
      iterator.stack.pop();
      continue;
    }
    const index = frame.indices[frame.position];
    frame.position += 1;
    const entry = nodes[index];
    if (!entry.visibleCount) continue;
    if (index === targetIndex) return offset;
    offset += 1;
    if (isBranchExpanded(entry)) {
      iterator.stack.push({ indices: entry.children, position: 0 });
    }
  }
  return -1;
};

self.onmessage = event => {
  const message = event.data;
  switch (message.type) {
    case 'INIT': {
      hideEmptyNode = message.hideEmptyNode;
      searchValue = message.searchValue || '';
      buildIndex(message.treeData || []);
      recomputeVisibility();
      invalidateRangeCache();
      const selectedIndex = nodeIndexById.get(String(message.selectedId || ''));
      const fallbackIndex = roots[0];
      const targetIndex = selectedIndex === undefined ? fallbackIndex : selectedIndex;
      const selectedNodeOffset = getNodeOffset(message.selectedId);
      self.postMessage({
        nodeCount: nodes.length,
        requestId: message.requestId,
        selectedNode: targetIndex === undefined ? null : nodes[targetIndex].data,
        selectedNodeOffset,
        total: getTotal(),
        type: 'INIT_DONE',
      });
      break;
    }
    case 'GET_RANGE':
      postState(message.requestId, message.start, message.end, 'GET_RANGE_DONE');
      break;
    case 'SET_FILTER':
      hideEmptyNode = message.hideEmptyNode;
      searchValue = message.searchValue || '';
      searchCollapsedIds.clear();
      searchExpandedIds.clear();
      searchCollapseAll = false;
      recomputeVisibility();
      invalidateRangeCache();
      postState(message.requestId, message.start, message.end, 'SET_FILTER_DONE');
      break;
    case 'TOGGLE':
      toggleNode(message.id, message.expanded);
      postState(message.requestId, message.start, message.end, 'TOGGLE_DONE');
      break;
    case 'COLLAPSE_ALL':
      expandedIds.clear();
      searchCollapsedIds.clear();
      searchExpandedIds.clear();
      searchCollapseAll = true;
      recomputeVisibility();
      invalidateRangeCache();
      postState(message.requestId, message.start, message.end, 'COLLAPSE_ALL_DONE');
      break;
    case 'EXPAND_ALL':
      expandedIds.clear();
      searchCollapsedIds.clear();
      searchExpandedIds.clear();
      searchCollapseAll = false;
      for (let index = 0; index < nodes.length; index += 1) {
        const entry = nodes[index];
        if (entry.children?.length) {
          expandedIds.add(String(entry.data.id));
        }
      }
      recomputeVisibility();
      invalidateRangeCache();
      postState(message.requestId, message.start, message.end, 'EXPAND_ALL_DONE');
      break;
    default:
      break;
  }
};
