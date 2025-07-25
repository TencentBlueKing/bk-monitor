export type Edge = { source: string; target: string };

export type NodeArgs = {
  combos: {
    id: string;
    parentId?: string;
  }[];
  edges: Edge[];
  maxGroupSize?: number;
  nodes: VirtaulNode[];
};

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
export type VirtaulNode = Record<string, any> & {
  children?: (undefined | VirtaulNode)[];
  comboId?: string;
  height?: number;
  id: string;
  isCombo?: boolean;
  isVirtual?: boolean;
  parentVid?: string;
  subComboId?: string;
  width?: number;
  x?: number;
  y?: number;
};

export default ({ combos, nodes, edges, maxGroupSize = 5 }: NodeArgs) => {
  const nodeWidth = 76;
  const nodeHeight = 92;
  const virtualNodeMap: Map<string, VirtaulNode> = new Map();
  const originNodeMap: Map<string, VirtaulNode> = nodes.reduce((map: Map<string, VirtaulNode>, node) => {
    map.set(node.id, Object.assign(node, { children: [] }));
    return map;
  }, new Map());

  const createVirtualNode = (id: string, children: VirtaulNode[], attrValue?: VirtaulNode) => {
    return { id, isVirtual: true, children, ...(attrValue ?? {}) };
  };

  const getVirtualNodeId = (id?: string) => `v#_${id}`;

  const setVirtualNodeRect = (node: VirtaulNode) => {
    const children = node?.children ?? [];
    const { length } = children;
    Object.assign(node, { width: nodeWidth * length, height: nodeHeight });
  };

  const setVirtualNode = (id: string, node: undefined | VirtaulNode) => {
    if (virtualNodeMap.has(id)) {
      Object.assign(virtualNodeMap.get(id), node ?? {});
      return;
    }

    virtualNodeMap.set(id, Object.assign(node ?? {}, { id, isVirtual: true }));
  };

  const setVirtualNodeChildren = (id: string, children: (undefined | VirtaulNode)[], parentVid?: string) => {
    children?.forEach(child => {
      Object.assign(child, { parentVid: parentVid ?? id });
    });

    if (virtualNodeMap.has(id)) {
      virtualNodeMap.get(id)?.children?.push(...(children ?? []));
      setVirtualNodeRect(virtualNodeMap.get(id));
      return;
    }

    console.warn(`setVirtualNodeChildren Error: ${id} not found`);
  };

  const isVirtualNode = (id: string) => {
    return virtualNodeMap.has(id);
  };

  const getNodeEdgeId = (node?: VirtaulNode) => {
    const { subComboId, id } = node ?? {};
    if (!subComboId) {
      const virtualId = getVirtualNodeId(subComboId);
      if (virtualNodeMap?.has(virtualId)) {
        return virtualId;
      }
    }

    return id;
  };

  const getRootCombos = combos => combos.filter(combo => !combo.parentId);

  /**
   * 格式化原始数据
   * 将Combo转换为虚拟节点
   * 同时将连线关系转换为节点所在的Combo转换的虚拟节点
   * 转换后 virtualNodeMap
   * @param param0
   */
  const formatOriginData = ({ combos, nodes, edges }: NodeArgs) => {
    const rootCombos = getRootCombos(combos);
    rootCombos.forEach(combo => {
      const id = getVirtualNodeId(combo.id);
      setVirtualNode(id, createVirtualNode(id, [], { id, comboId: combo.id, isCombo: true, isRoot: true }));
    });

    /**
     * subcombo 转换为虚拟节点
     */
    const subCombos = combos.filter(combo => !!combo.parentId);
    subCombos.forEach(combo => {
      const id = getVirtualNodeId(combo.id);
      const parentId = getVirtualNodeId(combo.parentId);
      setVirtualNode(
        id,
        createVirtualNode(id, [], { id, comboId: combo.parentId, subComboId: combo.id, isCombo: true, isRoot: false })
      );
      setVirtualNodeChildren(parentId, [virtualNodeMap.get(id)]);
    });

    /**
     * 更新节点连线为节点所在虚拟节点
     */
    const newEdges = [];
    edges.forEach(edge => {
      const { source, target } = edge;
      const sourceNode = originNodeMap.get(source);
      const targetNode = originNodeMap.get(target);

      const newEdge = {
        source: getNodeEdgeId(sourceNode),
        target: getNodeEdgeId(targetNode),
      };

      if (!newEdges.some(e => e.souce === newEdge.source && e.target === newEdge.target)) {
        newEdges.push(newEdge);
      }
    });

    rootCombos.forEach((combo, index) => {
      if (rootCombos[index + 1]) {
        newEdges.push({ source: getVirtualNodeId(combo.id), target: getVirtualNodeId(rootCombos[index + 1].id) });
      }
    });

    /**
     * 更新节点为虚拟节点子节点
     */
    nodes.forEach(node => {
      const { subComboId, comboId } = node;
      let virtualId = node.id;
      let virtualGroupId = null;
      if (subComboId || comboId) {
        const subComboVirtualId = getVirtualNodeId(subComboId);
        const rootComboVirtualId = getVirtualNodeId(comboId);
        virtualGroupId = isVirtualNode(subComboVirtualId) ? subComboVirtualId : null;
        virtualId = isVirtualNode(subComboVirtualId) ? subComboVirtualId : rootComboVirtualId;
        setVirtualNodeChildren(virtualId, [node]);

        if (virtualGroupId) {
          let edgeIndex = newEdges.findIndex(edge => edge.source === node.id);
          while (edgeIndex >= 0) {
            const edge = newEdges[edgeIndex];
            const newEdge = Object.assign({}, edge, { source: virtualGroupId });

            if (!newEdges.some(e => e.souce === newEdge.source && e.target === newEdge.target)) {
              newEdges.push(newEdge);
            }
            newEdges.splice(edgeIndex, 1);
            edgeIndex = newEdges.findIndex(edge => edge.source === node.id);
          }

          edgeIndex = newEdges.findIndex(edge => edge.target === node.id);

          while (edgeIndex >= 0) {
            const edge = newEdges[edgeIndex];

            const newEdge = Object.assign({}, edge, { target: virtualGroupId });

            if (!newEdges.some(e => e.souce === newEdge.source && e.target === newEdge.target)) {
              newEdges.push(newEdge);
            }
            newEdges.splice(edgeIndex, 1);
            edgeIndex = newEdges.findIndex(edge => edge.target === node.id);
          }
        }
      }

      /**
       * 这里指定 virtualGroupId 作为连线计算出来的子节点的分组ID
       * 这里的连线需要更新为连接到虚拟分组，而不是原来的子节点
       */
      // setOriginNodeChildren(
      //   node.id,
      //   newEdges
      //     .filter(edge => edge.source === node.id)
      //     .map(edge => edge.target)
      //     .map(id => originNodeMap.get(id))
      //     .filter(child => node.comboId === child.comboId)
      // );
    });

    return {
      nodes: [
        ...Array.from(originNodeMap.entries()).map(([, value]) => value),
        ...Array.from(virtualNodeMap.entries()).map(([, value]) => value),
      ],
      edges: newEdges,
    };
  };

  const getTargetNodeById = (id: string) => {
    return virtualNodeMap.get(id) ?? originNodeMap.get(id);
  };

  /**
   * 根据连线关系计算节点下游节点数量大于指定分组数据的节点
   * @param edges
   * @returns
   */
  const getNodesWithMoreThanMaxGroupSize = (edges: Edge[]) => {
    const nodeChildrenCount: Record<string, number> = {};

    // Calculate child count for each node
    edges.forEach(edge => {
      const { comboId = null } = getTargetNodeById(edge.target) ?? {};
      const key = `${edge.source}[####]${comboId}`;

      if (!nodeChildrenCount[key]) {
        nodeChildrenCount[key] = 0;
      }
      nodeChildrenCount[key] = nodeChildrenCount[key] + 1;
    });

    return Object.keys(nodeChildrenCount).filter(node => nodeChildrenCount[node] > maxGroupSize);
  };

  const computeLayout = () => {
    const formatData = formatOriginData({ combos, nodes, edges });

    let nodesToGroupNodes = [] || getNodesWithMoreThanMaxGroupSize(formatData.edges);

    let virtualNodes = 0;
    // If there are nodes to be grouped in this combo, process them
    while (nodesToGroupNodes.length > 0) {
      nodesToGroupNodes.forEach(key => {
        const keys = key.split('[####]');
        const nodeId = keys[0];
        const comboId = keys[1];
        virtualNodes = virtualNodes + 1;

        // Find all children of this node
        const children = formatData.edges
          .filter(edge => {
            const targetNode = getTargetNodeById(edge.target);
            return edge.source === nodeId && comboId === targetNode.comboId;
          })
          .map(edge => edge.target);
        const count = Math.ceil(children.length / maxGroupSize);
        const originNode = originNodeMap.get(nodeId);
        let start = 0;

        while (start < count) {
          const virtualNodeId = getVirtualNodeId(`node_group_${virtualNodes}_${start}`);
          const startIndex = start * maxGroupSize;
          const endIndex = Math.min(children.length, startIndex + maxGroupSize);
          const newChildren = children.slice(startIndex, endIndex);
          const newNodes = newChildren.map(id => formatData.nodes.find(node => node.id === id));
          setVirtualNode(virtualNodeId, createVirtualNode(virtualNodeId, newNodes, { id: virtualNodeId, comboId }));

          // 新增虚拟节点到父节点
          originNode?.children?.push(virtualNodeMap.get(virtualNodeId));
          originNode?.children?.forEach(child => {
            Object.assign(child, { parentVid: nodeId });
          });

          newChildren.forEach(n => {
            // 删除所有从父级节点连线到进行分组的节点的连线
            // 这里需要新增新的连线，从父级节点到虚拟的分组连线
            const edgeIndex = formatData.edges.findIndex(e => e.source === nodeId && e.target === n);
            if (edgeIndex >= 0) {
              formatData.edges.splice(edgeIndex, 1);
            }

            // 移除父节对应的分组包含子节点
            const index = originNode?.children?.findIndex(child => child?.id === n) ?? -1;
            if (index >= 0) {
              originNode?.children?.splice(index, 1);
            }

            /**
             * 调整连线开始位置
             */
            formatData.edges
              .filter(e => e.source === n)
              .forEach(e => {
                e.source = virtualNodeId;
              });
          });

          // 这里需要新增新的连线，从父级节点到虚拟的分组连线
          formatData.edges.push({ source: nodeId, target: virtualNodeId });
          start = start + 1;
        }
      });

      nodesToGroupNodes = getNodesWithMoreThanMaxGroupSize(formatData.edges);
    }

    const virtualNodeList = Array.from(virtualNodeMap.entries()).map(([, value]) => value);
    const originNodeList = Array.from(originNodeMap.entries()).map(([, value]) => value);

    return {
      nodes: [...originNodeList, ...virtualNodeList],
      edges: formatData.edges,
      layoutNodes: getRootCombos(combos).map(combo => virtualNodeMap.get(getVirtualNodeId(combo.id))),
      getVirtualNodeId,
    };
  };

  return computeLayout();
};
