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

import type { IHostTopoHostNode, IHostTopoInstNode, IHostTopoTreeNode } from '../types';

/**
 * @description 判断树节点是否为主机叶子节点（主机节点带 bk_host_id，实例节点不带）
 */
export const isHostNode = (node: IHostTopoTreeNode): node is IHostTopoHostNode =>
  (node as IHostTopoHostNode).bk_host_id !== undefined;

/**
 * @description 统计节点下的主机数量（节点行右侧展示的数字）。主机节点自身计为 1。
 */
export const countHostNodes = (node: IHostTopoTreeNode): number => {
  if (isHostNode(node)) {
    return 1;
  }
  return (node.children ?? []).reduce((total, child) => total + countHostNodes(child), 0);
};

/**
 * @description 裁剪「无主机节点」。递归剔除主机数量为 0 的实例节点，返回新树（不修改原数据）。
 */
export const pruneEmptyNodes = (nodes: IHostTopoTreeNode[]): IHostTopoTreeNode[] =>
  nodes
    .map(node => {
      if (isHostNode(node)) {
        return node;
      }
      return { ...node, children: pruneEmptyNodes(node.children ?? []) } as IHostTopoInstNode;
    })
    .filter(node => isHostNode(node) || countHostNodes(node) > 0);

/**
 * @description 拓扑树自定义搜索匹配函数，命中 IP / 主机名 / 节点名称（对接 bk-tree search.match）。
 */
export const matchTreeNode = (keyword: string, node: IHostTopoTreeNode): boolean => {
  const kw = keyword.trim().toLowerCase();
  if (!kw) {
    return true;
  }
  const fields = isHostNode(node)
    ? [node.ip, node.bk_host_innerip, node.bk_host_name, node.alias_name, node.display_name]
    : [node.name, node.bk_inst_name];
  return fields.some(field => !!field && String(field).toLowerCase().includes(kw));
};

/**
 * @description 获取节点展示名称：主机展示 IP，实例展示节点名。
 */
export const getNodeDisplayName = (node: IHostTopoTreeNode): string => (isHostNode(node) ? node.ip : node.name);
