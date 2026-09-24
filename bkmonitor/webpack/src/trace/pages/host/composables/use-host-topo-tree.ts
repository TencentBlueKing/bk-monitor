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

import { type ShallowRef, computed, onMounted, onScopeDispose, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { useRoute } from 'vue-router';

import { getHostInfoPage, getHostTopoTreeByBizId } from '../services/host-service';
import { handleCreateCompares, handleCreateItemId } from '../utils/host-list-core';
import { createHostTarget, resolveInitialHostScope } from '../utils/share-scope';
import { isHostNode } from '../utils/topo-tree';
import { useHostTopoTreeWorker } from './use-host-topo-tree-worker';
import { useAppStore } from '@/store/modules/app';
import { useHostStore } from '@/store/modules/host';

import type { IHostBaseInfo, IHostTopoHostNode, IHostTopoTreeNode } from '../types';
import type { IHostTopoViewRow } from './use-host-topo-tree-worker';

const TOPO_ROW_HEIGHT = 32;
const VIEW_OVERSCAN = 10;

/** 分页基础信息已由后端按主机范围解析，可用于主机指标目标。 */
const toHostNode = (host: IHostBaseInfo): IHostTopoHostNode => ({
  bk_biz_id: host.bk_biz_id,
  bk_cloud_id: host.bk_cloud_id,
  bk_host_id: host.bk_host_id,
  bk_host_innerip: host.bk_host_innerip,
  bk_host_innerip_v6: '',
  bk_host_name: host.bk_host_name,
  alias_name: host.bk_host_name,
  display_name: host.display_name,
  id: String(host.bk_host_id),
  ip: host.bk_host_innerip,
  name: host.bk_host_name,
  os_type: host.bk_os_type,
});

/**
 * @description 主机拓扑树业务编排：数据加载、搜索、隐藏无主机节点、展开收起、选中与对比来源。
 * 视图层（host-topo-tree）只消费这里暴露的状态与方法，保证 MVC 分层。
 */
export const useHostTopoTree = (nodeId: ShallowRef<string>, readonly = false) => {
  const route = useRoute();
  const appStore = useAppStore();
  const { metricAggregationState } = useHostStore();
  const topoTreeWorker = useHostTopoTreeWorker();
  const isAllExpand = shallowRef(false);
  /** 加载状态 */
  const loading = shallowRef(false);
  /** 拓扑加载失败状态 */
  const loadError = shallowRef(false);
  /** 原始树数据（接口/ mock 原样数据） */
  const rawTreeData = shallowRef<IHostTopoTreeNode[]>([]);
  const searchValue = shallowRef('');
  /** 隐藏无主机节点，默认勾选 */
  const hideEmptyNode = shallowRef(true);
  /** 当前选中的节点或主机 */
  const initialScope = computed(() =>
    resolveInitialHostScope(readonly, route.query, nodeId.value, Number(appStore.bizId))
  );
  const scopeError = computed(() => initialScope.value === null);
  const selectedNode = shallowRef<IHostTopoTreeNode | null>(
    createHostTarget(initialScope.value, Number(appStore.bizId))
  );
  const hostMetadataError = shallowRef(false);
  let hostMetadataVersion = 0;
  const fullTreeReady = shallowRef(false);
  const fullTreeLoading = shallowRef(false);
  const fullTreeError = shallowRef(false);
  const loadedHosts = shallowRef<IHostTopoHostNode[]>([]);
  const modulePages = new Map<string, { loading: boolean; page: number }>();
  let fullArrived = false;
  let fullRequestVersion = 0;
  let disposed = false;
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
  /** 拓扑加载请求版本 */
  let loadRequestVersion = 0;
  /** 是否已初始化 */
  let initialized = false;
  let scrollEl: HTMLElement = null;

  const shareScope = computed(() => (readonly ? initialScope.value : {}));
  const scopeKey = computed(() => JSON.stringify([Number(appStore.bizId), shareScope.value]));

  /** URL 主机直达无需等待完整拓扑，但图表仍需要真实 IP / 管控区域。 */
  const loadHostMetadata = async () => {
    const version = ++hostMetadataVersion;
    hostMetadataError.value = false;
    const target = selectedNode.value;
    if (!target || !isHostNode(target) || !target.metadataPending) return;
    const isCurrent = () => !disposed && version === hostMetadataVersion && selectedNode.value === target;
    try {
      const result = await getHostInfoPage({
        bk_biz_id: target.bk_biz_id,
        bk_host_id: target.bk_host_id,
        page: 1,
        page_size: 1,
      });
      if (!isCurrent()) return;
      const host = result.items.find(item => item.bk_host_id === target.bk_host_id);
      if (!host) throw new Error('Host metadata unavailable');
      selectedNode.value = toHostNode(host);
    } catch {
      if (isCurrent()) hostMetadataError.value = true;
    }
  };

  watch(
    [scopeKey, () => (selectedNode.value && isHostNode(selectedNode.value) ? selectedNode.value.bk_host_id : null)],
    loadHostMetadata,
    { immediate: true }
  );

  const updateFilter = useDebounceFn(async () => {
    if (!initialized || !fullTreeReady.value) {
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
    const hostMap = new Map<string, IHostTopoHostNode>(loadedHosts.value.map(host => [host.id, host]));
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
    if (disposed || version !== viewRequestVersion) {
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

  const applyTree = async (tree: IHostTopoTreeNode[], complete: boolean, version: number) => {
    if (disposed || version !== loadRequestVersion || (!complete && fullArrived)) return;
    const preserve = initialized;
    const anchorScrollTop = viewportScrollTop;
    const firstVisible = Math.floor(anchorScrollTop / TOPO_ROW_HEIGHT);
    const anchorId = visibleRows.value[firstVisible - visibleStart.value]?.id || '';
    const currentId = selectedNode.value?.id || nodeId.value;
    if (!preserve && tree[0]) (tree[0] as IHostTopoTreeNode & { isOpen?: boolean }).isOpen = true;
    const result = await topoTreeWorker.init(
      tree,
      hideEmptyNode.value,
      complete ? searchValue.value : '',
      currentId,
      complete,
      preserve,
      anchorId
    );
    if (disposed || version !== loadRequestVersion || (!complete && fullArrived)) return;
    rawTreeData.value = tree;
    initialized = true;
    if (selectedNode.value?.id === currentId && result.selectedNode) selectedNode.value = result.selectedNode;
    totalRows.value = result.total;
    if (preserve && result.anchorOffset >= 0 && viewportScrollTop === anchorScrollTop) {
      viewportScrollTop = result.anchorOffset * TOPO_ROW_HEIGHT + (viewportScrollTop % TOPO_ROW_HEIGHT);
      if (scrollEl) scrollEl.scrollTop = viewportScrollTop;
    } else if (!preserve && currentId) {
      await handleSelectNodeOfNodeId();
    }
    if (disposed || version !== loadRequestVersion || (!complete && fullArrived)) return;
    viewportScrollTop = Math.min(viewportScrollTop, Math.max(0, result.total * TOPO_ROW_HEIGHT - viewportHeight));
    if (scrollEl) scrollEl.scrollTop = viewportScrollTop;
    loading.value = false;
    loadError.value = false;
    await refreshVisibleRange(true);
  };

  const loadFullTree = async (version = loadRequestVersion) => {
    if (scopeError.value || disposed) return;
    const request = ++fullRequestVersion;
    fullTreeLoading.value = true;
    fullTreeError.value = false;
    try {
      const tree = await getHostTopoTreeByBizId(appStore.bizId, shareScope.value);
      if (disposed || version !== loadRequestVersion || request !== fullRequestVersion) return;
      fullArrived = true;
      await applyTree(tree, true, version);
      if (disposed || version !== loadRequestVersion || request !== fullRequestVersion) return;
      fullTreeReady.value = true;
      modulePages.clear();
      loadedHosts.value = [];
    } catch {
      if (!disposed && version === loadRequestVersion && request === fullRequestVersion) {
        fullArrived = false;
        fullTreeError.value = true;
        if (!initialized) loadError.value = true;
      }
    } finally {
      if (!disposed && version === loadRequestVersion && request === fullRequestVersion) {
        fullTreeLoading.value = false;
        if (!initialized) loading.value = false;
      }
    }
  };

  /** Skeleton and complete tree are independent; the latter supplies global search and exact counts. */
  const loadTopoTree = async () => {
    const version = ++loadRequestVersion;
    if (scopeError.value) {
      loadError.value = true;
      return;
    }
    loading.value = !initialized;
    loadError.value = false;
    fullArrived = false;
    fullTreeReady.value = false;
    modulePages.clear();
    loadedHosts.value = [];
    // A host-only share has no host leaf in the skeleton response.
    const skeleton =
      shareScope.value?.bk_host_id !== undefined
        ? null
        : getHostTopoTreeByBizId(appStore.bizId, shareScope.value, false);
    void loadFullTree(version);
    if (!skeleton) return;
    try {
      const tree = await skeleton;
      await applyTree(tree, false, version);
    } catch {
      if (!disposed && version === loadRequestVersion && !fullArrived && !initialized) loadError.value = true;
    } finally {
      if (!disposed && version === loadRequestVersion && (initialized || !fullTreeLoading.value)) loading.value = false;
    }
  };

  const handleSelectNodeOfNodeId = async () => {
    const version = loadRequestVersion;
    const target = resolveInitialHostScope(readonly, route.query, nodeId.value, Number(appStore.bizId));
    if (!target) return;
    const requested = createHostTarget(target, Number(appStore.bizId));
    if (selectedNode.value?.id !== requested.id) selectedNode.value = requested;
    if (!initialized) return;
    const result = await topoTreeWorker.select(requested.id);
    if (disposed || version !== loadRequestVersion || selectedNode.value?.id !== requested.id) return;
    if (result.selectedNode) selectedNode.value = result.selectedNode;
    if (result.selectedNodeOffset >= 0) {
      viewportScrollTop = result.selectedNodeOffset * TOPO_ROW_HEIGHT;
      if (scrollEl) scrollEl.scrollTop = viewportScrollTop;
    }
    await refreshVisibleRange(true);
  };

  const updateModule = async (
    id: string,
    children: IHostTopoHostNode[],
    page: { done?: boolean; status: 'error' | 'idle' | 'loading' | 'more'; total?: number }
  ) => {
    const version = loadRequestVersion;
    const scrollTop = viewportScrollTop;
    const anchor = visibleRows.value[Math.floor(scrollTop / TOPO_ROW_HEIGHT) - visibleStart.value]?.id || '';
    const result = await topoTreeWorker.upsertChildren(id, children, page, anchor);
    if (disposed || version !== loadRequestVersion || fullArrived) return;
    if (scrollTop === viewportScrollTop && result.anchorOffset >= 0) {
      viewportScrollTop = result.anchorOffset * TOPO_ROW_HEIGHT + (scrollTop % TOPO_ROW_HEIGHT);
      if (scrollEl) scrollEl.scrollTop = viewportScrollTop;
    }
  };

  const loadModulePage = async (id: string) => {
    if (disposed || fullArrived || fullTreeReady.value || !initialized) return;
    const match = /^module\|(\d+)$/.exec(id);
    if (!match) return;
    const state = modulePages.get(id) || { page: 0, loading: false };
    if (state.loading) return;
    state.loading = true;
    modulePages.set(id, state);
    const version = loadRequestVersion;
    const isCurrent = () => !disposed && version === loadRequestVersion && !fullArrived;
    try {
      await updateModule(id, [], { status: 'loading' });
      await refreshVisibleRange(true);
      if (!isCurrent()) return;
      const result = await getHostInfoPage({
        bk_biz_id: appStore.bizId,
        bk_obj_id: 'module',
        bk_inst_id: Number(match[1]),
        page: state.page + 1,
        page_size: 100,
      });
      if (!isCurrent()) return;
      const children = result.items.map(toHostNode);
      state.page = result.page;
      loadedHosts.value = [...new Map([...loadedHosts.value, ...children].map(host => [host.id, host])).values()];
      await updateModule(id, children, {
        status: 'more',
        total: result.total,
        done: result.page * result.page_size >= result.total,
      });
    } catch {
      if (isCurrent()) await updateModule(id, [], { status: 'error' });
    } finally {
      state.loading = false;
      if (isCurrent()) await refreshVisibleRange(true);
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
    if (!row.hasChildren) {
      return;
    }
    const { start, end } = getRange();
    const version = ++viewRequestVersion;
    const result = await topoTreeWorker.toggle(row.id, expanded, start, end);
    applyViewResult(result, start, end, version);
    if (expanded && 'bk_obj_id' in row && row.bk_obj_id === 'module' && !modulePages.has(row.id)) {
      void loadModulePage(row.id);
    }
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

  watch(
    scopeKey,
    (_, previous) => {
      viewRequestVersion += 1;
      const previousBiz = JSON.parse(previous)[0];
      if (!readonly && String(previousBiz) !== String(appStore.bizId)) nodeId.value = '';
      initialized = false;
      visibleRows.value = [];
      totalRows.value = 0;
      rawTreeData.value = [];
      fullTreeLoading.value = false;
      fullTreeError.value = false;
      selectedNode.value = createHostTarget(initialScope.value, Number(appStore.bizId));
      resetViewport();
      void loadTopoTree();
    },
    { flush: 'sync' }
  );

  watch(nodeId, () => {
    const target = createHostTarget(initialScope.value, Number(appStore.bizId));
    if (target?.id !== selectedNode.value?.id) void handleSelectNodeOfNodeId();
  });

  onMounted(() => {
    loadTopoTree();
  });

  onScopeDispose(() => {
    disposed = true;
    loadRequestVersion += 1;
    fullRequestVersion += 1;
    hostMetadataVersion += 1;
  });

  return {
    hostMetadataError,
    loadHostMetadata,
    scopeError,
    scopeKey,
    fullTreeReady,
    fullTreeLoading,
    fullTreeError,
    loadFullTree: () => loadFullTree(),
    loadModulePage,
    isAllExpand,
    loading,
    loadError,
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
