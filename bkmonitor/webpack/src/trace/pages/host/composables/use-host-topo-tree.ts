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

import { type ShallowRef, computed, onMounted, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';

import { getHostTopoTreeByBizId } from '../services/host-service';
import { handleCreateCompares, handleCreateItemId } from '../utils/host-list-core';
import { isHostNode } from '../utils/topo-tree';
import { useHostTopoTreeWorker } from './use-host-topo-tree-worker';
import { useHostStore } from '@/store/modules/host';

import type { IHostTopoHostNode, IHostTopoTreeNode } from '../types';
import type { IHostTopoViewRow } from './use-host-topo-tree-worker';

const TOPO_ROW_HEIGHT = 32;
const VIEW_OVERSCAN = 10;

/**
 * @description 主机拓扑树业务编排：数据加载、搜索、隐藏无主机节点、展开收起、选中与对比来源。
 * 视图层（host-topo-tree）只消费这里暴露的状态与方法，保证 MVC 分层。
 */
export const useHostTopoTree = (nodeId: ShallowRef<string>) => {
  const { metricAggregationState } = useHostStore();
  const topoTreeWorker = useHostTopoTreeWorker();
  const isAllExpand = shallowRef(false);
  /** 加载状态 */
  const loading = shallowRef(false);
  /** 原始树数据（接口/ mock 原样数据） */
  const rawTreeData = shallowRef<IHostTopoTreeNode[]>([]);
  const searchValue = shallowRef('');
  /** 隐藏无主机节点，默认勾选 */
  const hideEmptyNode = shallowRef(true);
  /** 当前选中的节点或主机 */
  const selectedNode = shallowRef<IHostTopoTreeNode | null>(null);
  /** Worker 返回的当前可视区节点切片 */
  const visibleRows = shallowRef<IHostTopoViewRow[]>([]);
  /** 可视切片在完整扁平列表中的起始下标 */
  const visibleStart = shallowRef(0);
  /** 当前展开 / 搜索状态下的扁平节点总数 */
  const totalRows = shallowRef(0);
  /** 通知视图将滚动位置重置到顶部 */
  const viewportResetKey = shallowRef(0);
  /** 视口高度 */
  let viewportHeight = 0;
  /** 视口滚动位置 */
  let viewportScrollTop = 0;
  /** 已加载的开始下标 */
  let loadedStart = 0;
  /** 已加载的结束下标 */
  let loadedEnd = 0;
  /** 视图请求版本 */
  let viewRequestVersion = 0;
  /** 是否已初始化 */
  let initialized = false;
  let scrollEl: HTMLElement = null;

  const updateFilter = useDebounceFn(async () => {
    if (!initialized) {
      return;
    }
    resetViewport();
    const { start, end } = getRange();
    const version = ++viewRequestVersion;
    const result = await topoTreeWorker.setFilter(hideEmptyNode.value, searchValue.value, start, end);
    applyViewResult(result, start, end, version);
  }, 500);

  watch([searchValue, hideEmptyNode], updateFilter);

  /** 对比候选只随原始树重建，避免每次选中节点都重新遍历百万级数据。 */
  const compareHostList = computed<IHostTopoHostNode[]>(() => {
    const hostMap = new Map<string, IHostTopoHostNode>();
    const stack = [...rawTreeData.value];
    while (stack.length) {
      const item = stack.pop();
      if (!item) {
        continue;
      }
      if (isHostNode(item)) {
        const id = handleCreateItemId(item);
        if (!hostMap.has(id)) {
          hostMap.set(id, { ...item, id });
        }
      } else {
        for (const child of item.children) {
          stack.push(child);
        }
      }
    }
    return [...hostMap.values()];
  });

  /** 当前选中的是否为主机（决定 hover 其他主机时是否出现「对比」按钮） */
  const selectedIsHost = computed(() => !!selectedNode.value && isHostNode(selectedNode.value));

  const compareType = computed(() => metricAggregationState.compareType);

  const compareTargets = computed(() => metricAggregationState.compareTargets);

  /** 受控选中态 */
  const selectedIds = computed<string[]>(() => (selectedNode.value ? [selectedNode.value.id] : []));

  const getRange = () => {
    const firstVisible = Math.floor(viewportScrollTop / TOPO_ROW_HEIGHT);
    const visibleCount = Math.ceil(viewportHeight / TOPO_ROW_HEIGHT);
    return {
      end: Math.max(firstVisible + visibleCount + VIEW_OVERSCAN, VIEW_OVERSCAN * 2),
      start: Math.max(0, firstVisible - VIEW_OVERSCAN),
    };
  };

  const applyViewResult = (
    result: { rows: IHostTopoViewRow[]; total: number },
    start: number,
    end: number,
    version: number
  ) => {
    if (version !== viewRequestVersion) {
      return;
    }
    visibleRows.value = result.rows;
    visibleStart.value = start;
    totalRows.value = result.total;
    loadedStart = start;
    loadedEnd = Math.min(end, result.total);
  };

  const refreshVisibleRange = async (force = false) => {
    if (!initialized) {
      return;
    }
    const { start, end } = getRange();
    const firstVisible = Math.floor(viewportScrollTop / TOPO_ROW_HEIGHT);
    const lastVisible = firstVisible + Math.ceil(viewportHeight / TOPO_ROW_HEIGHT);
    if (!force && firstVisible >= loadedStart && lastVisible <= loadedEnd) {
      return;
    }
    const version = ++viewRequestVersion;
    const result = await topoTreeWorker.getRange(start, end);
    applyViewResult(result, start, end, version);
  };

  const handleViewportChange = (scrollTop: number, height: number, element: HTMLElement) => {
    scrollEl = element;
    viewportScrollTop = scrollTop;
    viewportHeight = height;
    refreshVisibleRange();
  };

  const resetViewport = () => {
    viewportScrollTop = 0;
    viewportResetKey.value += 1;
  };

  /** 加载拓扑树并在 Worker 中建立扁平索引、主机计数和可见节点计数。 */
  const loadTopoTree = async () => {
    loading.value = true;
    try {
      const data = await getHostTopoTreeByBizId();
      rawTreeData.value = data;
      await handleSelectNodeOfNodeId();
    } finally {
      loading.value = false;
    }
  };

  /** 根据 nodeId 在已有拓扑树数据中定位并聚焦目标节点（展开路径 + 滚动到位） */
  const handleSelectNodeOfNodeId = async () => {
    // 存在有子节点的根节点时，默认对第一个有子节点的根节点展开第一级子列表（Worker 消费 isOpen）
    if (nodeId.value) {
      // 存在 nodeId 时，展开从根到目标节点的完整路径，确保目标节点可见
      const expandToNode = (nodes: IHostTopoTreeNode[], targetId: string): boolean => {
        let found = false;
        for (const node of nodes) {
          if (node.id === targetId) {
            found = true;
            break;
          }
          if ('children' in node && Array.isArray(node.children) && node.children.length > 0) {
            if (expandToNode(node.children, targetId)) {
              (node as IHostTopoTreeNode & { isOpen?: boolean }).isOpen = true;
              found = true;
              break;
            }
          }
        }
        return found;
      };
      expandToNode(rawTreeData.value, nodeId.value);
    } else {
      for (const root of rawTreeData.value) {
        if ('children' in root && Array.isArray(root.children) && root.children.length > 0) {
          (root as IHostTopoTreeNode & { isOpen?: boolean }).isOpen = true;
          break;
        }
      }
    }
    const result = await topoTreeWorker.init(rawTreeData.value, hideEmptyNode.value, searchValue.value, nodeId.value);
    selectedNode.value = result.selectedNode;
    totalRows.value = result.total;
    let scrollTop = 0;
    // 有目标节点偏移量时滚动到目标位置，否则重置到顶部
    if (result.selectedNodeOffset >= 0) {
      viewportScrollTop = result.selectedNodeOffset * TOPO_ROW_HEIGHT;
      scrollTop = viewportScrollTop;
      viewportResetKey.value += 1;
    } else {
      resetViewport();
    }
    initialized = true;
    await refreshVisibleRange(true);
    if (scrollEl) {
      scrollEl.scrollTop = scrollTop;
    }
  };

  const handleRefresh = () => {
    loadTopoTree();
  };

  /** 选中节点 / 主机 */
  const handleSelectNode = (row: IHostTopoViewRow) => {
    selectedNode.value = row as unknown as IHostTopoTreeNode;
  };

  /** 点击内容时只负责展开关闭节点；收起仍只能点击箭头。 */
  const handleExpandNode = async (row: IHostTopoViewRow, expanded = true) => {
    if (!row.hasChildren || row.isExpanded === expanded) {
      return;
    }
    const { start, end } = getRange();
    const version = ++viewRequestVersion;
    const result = await topoTreeWorker.toggle(row.id, expanded, start, end);
    applyViewResult(result, start, end, version);
  };

  /** 主机对比 */
  const handleCompare = (payload: { source: IHostTopoHostNode; target: IHostTopoHostNode }) => {
    const hostId = handleCreateItemId(payload.target);
    const item = compareHostList.value.find(item => item.id === hostId);
    const value = handleCreateCompares(item);
    metricAggregationState.compareTargets = [...metricAggregationState.compareTargets, value];
  };

  /**
   * 全部展开/收起
   * 全部收起通过清空 Worker 展开集合完成，无需逐节点调用组件实例方法。
   * */
  const handleExpandAll = async () => {
    isAllExpand.value = !isAllExpand.value;
    let result = null;
    const { start, end } = getRange();
    const version = ++viewRequestVersion;
    resetViewport();
    if (isAllExpand.value) {
      result = await topoTreeWorker.expandAll(start, end);
    } else {
      result = await topoTreeWorker.collapseAll(start, end);
    }
    applyViewResult(result, start, end, version);
  };

  onMounted(() => {
    loadTopoTree();
  });

  return {
    isAllExpand,
    loading,
    searchValue,
    hideEmptyNode,
    selectedNode,
    selectedIsHost,
    selectedIds,
    compareHostList,
    visibleRows,
    visibleStart,
    totalRows,
    rowHeight: TOPO_ROW_HEIGHT,
    viewportResetKey,
    compareType,
    compareTargets,
    loadTopoTree,
    handleRefresh,
    handleSelectNode,
    handleExpandNode,
    handleViewportChange,
    handleExpandAll,
    handleSelectNodeOfNodeId,
    handleCompare,
  };
};

export type HostTopoTreeContext = ReturnType<typeof useHostTopoTree>;
