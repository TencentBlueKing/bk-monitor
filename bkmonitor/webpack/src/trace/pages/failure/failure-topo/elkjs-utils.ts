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
import Elkjs from 'elkjs';

import type { Edge, VirtaulNode } from './format-topo-data';

let subCombosMap: Record<string, number> = {};
const space = 30;
const nodeWidth = 92;
const nodeHeight = 92;

const setSubCombosMap = (val: any) => {
  subCombosMap = val;
};
/**
 * 用于判定Combo子节点数量，判定是否展示当前Combo
 * @param id
 * @returns
 */
const filterSubCombo = id => (subCombosMap[id] ?? 0) > 0;

const getRootCombos = data => {
  return (data.combos?.filter(combo => !combo.parentId) ?? []).map(combo =>
    Object.assign(combo, {
      isRoot: true,
    })
  );
};

const defaultLayoutOptions = {
  algorithm: 'layered',
  'elk.direction': 'DOWN',
  // // 调节分布每行展示节点数量
  'org.eclipse.elk.aspectRatio': '3',
  separateConnectedComponents: 'true',
};

const childLayoutOption = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
};

const subChildOption = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.layering.strategy': 'LONGEST_PATH',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.mergeEdges': true,
  'elk.spacing.edgeNode': nodeWidth,
  'elk.spacing.nodeNode': nodeWidth,
  'elk.layered.spacing.nodeNodeBetweenLayers': nodeWidth,
  'org.eclipse.elk.aspectRatio': '3',
  'elk.portAlignment.strategy': 'CENTER',
  'org.eclipse.elk.nodePlacement.bk.fixedAlignment': 'CENTER',
  'elk.layered.mergeHierarchyCrossingEdges': true,
  'elk.spacing.builder': 'NETWORK_SIMPLEX',
};

// 将数据转换为 ELK 格式
const convertToElkFormat = data => {
  const elkEdges = [];

  // 处理边（edges）
  data.edges.forEach(edge => {
    elkEdges.push({
      id: `${edge.source}-${edge.target}`,
      sources: [edge.source],
      targets: [edge.target],
    });
  });

  data.nodes.forEach(child => {
    Object.assign(child, { layoutOptions: subChildOption });
    (child.children ?? []).forEach(subChild => {
      if (subChild.isCombo) {
        Object.assign(child, {
          layoutOptions: {
            'elk.algorithm': 'layered',
            'elk.direction': 'DOWN',
          },
        });
      }
    });
  });

  const virtualEdges = [];

  return {
    id: 'superRoot',
    children: data.nodes,
    edges: elkEdges.concat(virtualEdges),
    layoutOptions: childLayoutOption,
  };
};

/**
 * 递归格式化布局数据
 * @param data
 * @param rootList
 * @returns
 */
const getKlayGraphData = data => {
  const elkData = convertToElkFormat(data);
  return elkData;
};

const getFixedRect = node => {
  const { height, width, isCombo, children, isRoot } = node;
  const fixWidth = isCombo && !isRoot ? children.length * nodeWidth : width;
  const fixHeight = isCombo && !isRoot ? nodeHeight : height;
  return [fixWidth, fixHeight];
};

/**
 * 根据布局排列算法计算结果进行位置大小信息同步到节点配置
 * @param layouted
 * @param data
 */
const updatePositionFromLayouted = (layouted, data, parent?, index?) => {
  const { x, y, isCombo, id, children, comboId, subComboId = null } = layouted;
  const queryId = isCombo ? (subComboId ?? comboId) : id;
  const { combos, nodes } = data;
  const target = (isCombo ? combos : nodes).find(n => n.id === queryId);

  if (target) {
    const [fixWidth, fixHeight] = getFixedRect(layouted);
    const startX = parent?.x;
    const startY = parent?.y;
    const isVirtualBox = (parent?.isVirtual && parent?.isCombo && !parent?.isRoot) ?? false;
    Object.assign(target, {
      fixSize: [fixWidth, fixHeight],
      width: fixWidth,
      height: fixHeight,
      x: isVirtualBox ? startX + index * nodeWidth : x,
      y: isVirtualBox ? startY + (index % 2) * 30 : y,
    });
  }

  children?.forEach((child, index) => updatePositionFromLayouted(child, data, layouted, index));
};

const setSubNodesX = (children: VirtaulNode[], startX: number) => {
  children.forEach((node, index) => {
    Object.assign(node, { x: startX - nodeWidth / 2 + index * nodeWidth });
  });
};

const setSubNodesY = (children: VirtaulNode[], starY: number) => {
  children.forEach(node => {
    Object.assign(node, { y: starY });
  });
};

const fixNodeYOffset = (nodes, diff) => {
  nodes.forEach(node => {
    node.y += diff;
    if (node.children?.length) {
      fixNodeYOffset(node.children, diff);
    }
  });
};

/**
 * 优化最终布局
 * @param layouted 计算之后的布局数据
 * @param data 原始数据
 * @param edges 按照分组处理之后的连线关系
 */
const OptimizeLayout = (layouted, data, edges: Edge[]) => {
  const globalNodes = [];
  const groupByY = new Map<number, VirtaulNode[]>();
  layouted.children.forEach((child, index) => {
    const prevHeight = index > 0 ? layouted.children[index - 1].height : 0;
    const diffY = child.y - child.height / 2 + prevHeight;
    child.y = child.height / 2 + prevHeight;
    fixNodeYOffset(child.children, diffY);
  });
  const rootNode = data.nodes.find(node => node.entity.is_root);
  let rootBox = rootNode;

  /**
   * 将树形数据结构平铺 & 按照y轴分组
   * @param root
   */
  const getNodes = (root: VirtaulNode) => {
    const { y, isCombo, id, children, isRoot } = root;
    const subNodes = isCombo && !isRoot ? children : edges.filter(edge => edge.source === id).map(edge => edge.target);
    Object.assign(root, { subNodes, referenceRoot: getRootNodeReference(root) });
    globalNodes.push(root);

    if (!isRoot && id !== 'superRoot') {
      if (!groupByY.has(y)) {
        groupByY.set(y, []);
      }

      groupByY.get(y)?.push(root);
    }

    if (!isCombo || isRoot) {
      children?.forEach(child => getNodes(child));
    }
  };

  /**
   * 根据实际连线关系，调整节点位置
   * @param node 当前节点
   * @param preLeveYVal 上层节点y轴值
   * @param placement 相对于中心节点的相对位置
   * @returns
   */
  const getCenterXByChildren = (node: VirtaulNode, preLeveYVal: number, placement) => {
    const nodeChildren = node.subNodes.map(id => globalNodes.find(node => node.id === id));
    const childList =
      node.isCombo && !node.isRoot
        ? []
        : nodeChildren?.filter(child => child.y === preLeveYVal && child.x < rootNode.x);

    if (!childList.length) {
      return undefined;
    }

    childList.sort((a, b) => b.x - a.x);
    const childLength = childList.length - 1;

    const maxChildX = childList[0].x + childList[0].width;
    const minChildX = childList[childLength].x;

    /**
     * 取三分之一处作为锚点
     */
    const split = 3;
    if (placement === 'left') {
      return maxChildX - (maxChildX + space - maxChildX) / split;
    }
    return minChildX + (maxChildX - minChildX + space) / split;
  };

  const getStartXSpace = key => {
    const isRootNodeLevel = key === rootNode.y;

    if (isRootNodeLevel) {
      const rootNodeId = `v#_${rootNode.subComboId}` === rootNode.parentVid ? rootNode.parentVid : rootNode.id;
      return globalNodes.find(node => node.id === rootNodeId)?.width ?? space;
    }

    return space;
  };

  /**
   * 查找指定节点与中心节点的连线关系
   * @param node
   * @returns
   */
  const getRootNodeReference = (node: VirtaulNode) => {
    const rootNodeId = `v#_${rootNode.subComboId}` === rootNode.parentVid ? rootNode.parentVid : rootNode.id;
    return edges.filter(
      edge =>
        (edge.source === node.id && edge.target === rootNodeId) ||
        (edge.target === node.id && edge.source === rootNodeId)
    );
  };

  const getRootBox = () => {
    const rootNodeId = `v#_${rootNode.subComboId}` === rootNode.parentVid ? rootNode.parentVid : rootNode.id;
    rootBox = globalNodes.find(node => node.id === rootNodeId) ?? rootNode;
  };
  if (rootNode) {
    getNodes(layouted);
    getRootBox();

    const { x } = rootNode;
    let yKeys = [...groupByY.keys()];
    yKeys.sort((a, b) => a - b);

    const updateNodeY = (to, index) => {
      groupByY.get(yKeys[index]).forEach(node => {
        Object.assign(node, { y: to });

        if (node.isCombo && !node.isRoot) {
          setSubNodesY(node.children, to);
        }
      });

      groupByY.set(to, groupByY.get(yKeys[index]));
      groupByY.delete(yKeys[index]);
      yKeys[index] = to;
    };

    let diffValue = 0;
    const nodeSpace = nodeHeight + space * 2;
    for (let index = 0; index < yKeys.length; index++) {
      if (index > 0 && groupByY.get(yKeys[index])[0].comboId === groupByY.get(yKeys[index - 1])[0].comboId) {
        diffValue = yKeys[index] - yKeys[index - 1];
        if (diffValue < nodeSpace) {
          /** nodeHeight 为固定节点高度，但如果是一个子combo高度是不确定的，求的这一层级的最大高度和nodeHeight做对比  */
          const maxHeight = Math.max(...groupByY.get(yKeys[index - 1]).map(node => node.height));
          /** height > 间距表示可能出现重叠或者间距过小 */
          const diffY = maxHeight - nodeSpace;
          const to = yKeys[index - 1] + nodeSpace + (diffY > 0 ? diffY : 0);

          updateNodeY(to, index);
        }

        if (diffValue > nodeSpace * 2) {
          const to = yKeys[index] - diffValue + nodeSpace * 2;
          updateNodeY(to, index);
        }
      }
    }

    yKeys = [...groupByY.keys()];
    yKeys.sort((a, b) => b - a);
    let preLeveYVal = null;
    yKeys.forEach(key => {
      const nodes = groupByY.get(key);
      const leftNodes = nodes.filter(node => node.x < x);
      leftNodes.sort((a, b) => a.subNodes?.length - b.subNodes?.length);
      leftNodes.sort((a, b) => b.referenceRoot.length - a.referenceRoot.length);

      let lastOneX = x - getStartXSpace(key);
      leftNodes.forEach(node => {
        if (node.id !== rootNode.id) {
          const computedX = lastOneX - node.width - space;
          const centerX = getCenterXByChildren(node, preLeveYVal, 'left') ?? computedX;

          Object.assign(node, { x: centerX < computedX ? centerX : computedX });
          lastOneX = node.x;
          if (node.isCombo && !node.isRoot) {
            setSubNodesX(node.children, node.x);
          }
        }
      });

      const rightNodes = nodes.filter(node => node.x >= x);
      rightNodes.sort((a, b) => a.subNodes?.length - b.subNodes?.length);
      rightNodes.sort((a, b) => b.referenceRoot.length - a.referenceRoot.length);

      let rightX = x + getStartXSpace(key);
      rightNodes.forEach(node => {
        if (node.id !== rootNode.id) {
          const computedX = rightX + node.width;
          const centerX = getCenterXByChildren(node, preLeveYVal, 'right') ?? computedX;

          Object.assign(node, { x: centerX < computedX ? computedX : centerX });
          rightX = node.x + node.width + space;
          if (node.isCombo && !node.isRoot) {
            setSubNodesX(node.children, node.x);
          }
        }
      });

      preLeveYVal = key;
    });
  }

  // 计算整体偏移量
  const usefullNodes = globalNodes.filter(node => !node.isRoot && node.id !== 'superRoot');
  const globalX = usefullNodes.map(node => node.x);
  const globalMinX = Math.min(...globalX);
  const globalMaxX = Math.max(...globalX);

  const leftPdding = Math.max(...usefullNodes.filter(node => node.x === globalMinX).map(node => node.width));
  const rightPadding = Math.max(...usefullNodes.filter(node => node.x === globalMaxX).map(node => node.width));
  const globalWidth = globalMaxX - globalMinX + leftPdding + rightPadding;
  data.combos.forEach(combo => {
    if (combo.parentId) return;
    Object.assign(combo, {
      width: globalWidth,
      fixSize: [globalWidth, combo.height],
    });
  });
  // Object.assign(data.combos[0], {
  //   width: globalWidth,
  //   fixSize: [globalWidth, data.combos[0].height],
  // });
  // Object.assign(data.combos[1], {
  //   width: globalWidth,
  //   fixSize: [globalWidth, data.combos[1].height],
  // });

  const paddingLeft = globalMinX < 0 ? -globalMinX : 0;

  if (rootBox !== rootNode) {
    setSubNodesX(rootBox.children, rootBox.x);
  }

  globalNodes.forEach(node => {
    const { x, y, isCombo, id, comboId, subComboId } = node;
    const queryId = isCombo ? (subComboId ?? comboId) : id;
    const { combos, nodes } = data;
    const target = (isCombo ? combos : nodes).find(n => n.id === queryId);
    if (target) {
      Object.assign(target, { x: x + paddingLeft, y });
      if (isCombo && !node.isRoot) {
        node.children.forEach((child, index) => {
          child.x = target.x - target.width / 2 + index * child.width + 10;
        });
      }
    }
  });
};

/** 兼容动态combo数量 */
const setRootComboStyle = (combos: Array<any>, width) => {
  const rootCombos = getRootCombos({ combos });
  const maxWidth = Math.max(...rootCombos.map(combo => combo.width ?? 0), width, 1440);
  rootCombos.forEach((combo, index) => {
    const prevCombo = rootCombos[index - 1];
    const y = index === 0 ? 0 : prevCombo.y + prevCombo.height + combo.height / 2 + 15 + 30;
    Object.assign(combo, { width: maxWidth, x: width / 2, y, fixSize: [maxWidth, combo.height + 30] });
  });
};

/**
 * 计数SubCombo
 * 如果Combo下面只有一个节点时不需要展示Combo
 * @param nodes
 * @returns
 */
const getSubComboCountMap = (nodes: any[]) => {
  return nodes.reduce((map, node) => Object.assign(map, { [node.subComboId]: (map[node.subComboId] ?? 0) + 1 }), {});
};

const resolveSumbCombos = (sub_combos: any[]) => {
  const filterCombos = (sub_combos ?? []).filter(combo => filterSubCombo(combo.id));
  // 这里接口给的鬼数据可能乱七八糟，各种重复
  // 前端自己做数据去重吧，靠谱点
  const ids = new Set(filterCombos.map(combo => combo.id));
  return Array.from(ids).map(id => {
    const combo = filterCombos.find(combo => combo.id === id);
    const { comboId, label, dataType, dimensions } = combo;

    return {
      parentId: comboId,
      id,
      type: 'rect',
      padding: 30,
      label,
      dataType,
      dimensions,
      style: {
        cursor: 'grab',
        fill: '#4E4F52',
        radius: 6,
        stroke: '#4E4F52',
        opacity: 0.4,
      },
      labelCfg: {
        style: {
          fill: '#979BA5',
          fontSize: 12,
        },
      },
    };
  });
};

const getComboId = (str: string) => {
  return str ? `ComboId_${str}` : null;
};

const getTopoRawData = (combos, edges, nodes) => {
  const getNodeComboId = node => {
    return filterSubCombo(node.subComboId) ? `${node.subComboId}` : `${node.comboId}`;
  };

  return {
    combos: combos.map(combo => ({ ...combo, id: combo.id.toString() })),
    edges: edges.map(edge => ({
      ...edge,
      id: `${edge.source}-${edge.target}`,
      sources: [edge.source],
      targets: [edge.target],
    })),
    nodes: nodes.map(node => ({
      ...node,
      id: `${node.id}`,
      comboId: getNodeComboId(node),
    })),
  };
};

const getLayoutData = elkData => {
  // 初始化 ELK 实例
  const elk = new Elkjs();

  // 初步计算 Combo 尺寸
  return elk
    .layout(elkData, { layoutOptions: defaultLayoutOptions })
    .then(layoutedGraph => {
      return layoutedGraph;
    })
    .catch(error => {
      console.error('Error: ', error);
      return Promise.reject(error);
    });
};
export default {
  getLayoutData,
  getComboId,
  resolveSumbCombos,
  getSubComboCountMap,
  setRootComboStyle,
  getKlayGraphData,
  updatePositionFromLayouted,
  getTopoRawData,
  getRootCombos,
  setSubCombosMap,
  OptimizeLayout,
};
