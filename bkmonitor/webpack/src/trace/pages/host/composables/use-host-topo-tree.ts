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

import { computed, shallowRef } from 'vue';

import { getHostTopoTreeByBizId } from '../services/host-service';
import { handleCreateItemId } from '../utils/host-list-core';
import { isHostNode, matchTreeNode, pruneEmptyNodes } from '../utils/topo-tree';

import type { IHostTopoHostNode, IHostTopoTreeNode } from '../types';

/** bk-tree 实例上本 composable 需要调用的最小方法集 */
interface ITreeInstance {
  getData: (newTree?: boolean) => { data: IHostTopoTreeNode[] };
  setOpen: (item: IHostTopoTreeNode, isOpen?: boolean, autoOpenParents?: boolean) => void;
}

/**
 * @description 主机拓扑树业务编排：数据加载、搜索、隐藏无主机节点、展开收起、选中与对比来源。
 * 视图层（host-topo-tree）只消费这里暴露的状态与方法，保证 MVC 分层。
 */
export const useHostTopoTree = () => {
  /** bk-tree 组件实例引用，用于调用展开/收起等命令式方法 */
  const treeRef = shallowRef<ITreeInstance | null>(null);
  const loading = shallowRef(false);
  /** 原始树数据（接口/ mock 原样数据） */
  const rawTreeData = shallowRef<IHostTopoTreeNode[]>([]);
  const searchValue = shallowRef('');
  /** 隐藏无主机节点，默认勾选 */
  const hideEmptyNode = shallowRef(true);
  /** 当前选中的节点或主机 */
  const selectedNode = shallowRef<IHostTopoTreeNode | null>(null);

  /** 视图实际渲染的数据：根据「隐藏无主机节点」开关裁剪 */
  const displayTreeData = computed<IHostTopoTreeNode[]>(() =>
    hideEmptyNode.value ? pruneEmptyNodes(rawTreeData.value) : rawTreeData.value
  );

  /** 对比主机列表（过滤已选中的节主机点） */
  const compareHostList = computed<IHostTopoHostNode[]>(() => {
    const hostMap = new Map();
    let currentHostId = selectedNode.value?.id;
    if (selectedNode.value && ('id' in selectedNode.value || 'bk_host_id' in selectedNode.value)) {
      currentHostId = handleCreateItemId(selectedNode.value);
    }
    const fn = (data: IHostTopoTreeNode[]) => {
      for (const item of data) {
        if ('children' in item) {
          fn(item.children);
        }
        if ('ip' in item || 'bk_host_id' in item) {
          const id = handleCreateItemId(item);
          if (id !== currentHostId && !hostMap.has(id)) {
            hostMap.set(id, {
              ...item,
              id,
            });
          }
        }
      }
    };
    fn(displayTreeData.value);
    const hostList = Array.from(hostMap).map(item => item[1]);
    return hostList;
  });

  /** 当前选中的是否为主机（决定 hover 其他主机时是否出现「对比」按钮） */
  const selectedIsHost = computed(() => !!selectedNode.value && isHostNode(selectedNode.value));

  /** 受控选中态：传给 bk-tree 的 selected（node-key=id） */
  const selectedIds = computed<string[]>(() => (selectedNode.value ? [selectedNode.value.id] : []));

  /**
   * bk-tree 搜索配置：
   * - 自定义 match 命中 IP / 主机名 / 节点名称
   * - showChildNodes=false：命中父节点时默认折叠子内容，但仍可手动展开
   */
  const searchOption = computed(() => ({
    value: searchValue.value,
    match: (keyword: boolean | number | string, _itemText: string, item: IHostTopoTreeNode) =>
      matchTreeNode(String(keyword), item),
    resultType: 'tree' as const,
    showChildNodes: false,
  }));

  /** 加载拓扑树（暂用 mock，后续替换为 getHostTopoTreeByBizId） */
  const loadTopoTree = async () => {
    loading.value = true;
    try {
      const data = await getHostTopoTreeByBizId();
      console.log('topo tree data = ', data);
      rawTreeData.value = data;
      // 根节点默认选中
      selectedNode.value = data[0] ?? null;
    } finally {
      loading.value = false;
    }
  };

  const handleRefresh = () => {
    loadTopoTree();
  };

  /** 选中节点 / 主机 */
  const handleSelectNode = (node: IHostTopoTreeNode) => {
    selectedNode.value = node;
  };

  /** 全部收起：收起当前树内所有节点 */
  const handleCollapseAll = () => {
    const tree = treeRef.value;
    if (!tree) {
      return;
    }
    const { data } = tree.getData();
    // getData().data 为扁平化后的全部节点，逐个收起
    data.forEach(node => tree.setOpen(node, false));
  };

  return {
    treeRef,
    loading,
    searchValue,
    hideEmptyNode,
    selectedNode,
    selectedIsHost,
    selectedIds,
    displayTreeData,
    compareHostList,
    searchOption,
    loadTopoTree,
    handleRefresh,
    handleSelectNode,
    handleCollapseAll,
  };
};

export type HostTopoTreeContext = ReturnType<typeof useHostTopoTree>;
