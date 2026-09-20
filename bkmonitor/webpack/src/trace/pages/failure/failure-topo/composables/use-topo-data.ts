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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

/**
 * @file 拓扑图数据管理 Composable
 * @description 负责管理 FailureTopo 组件的拓扑数据获取、缓存、格式化和布局计算
 *
 * ## 职责
 * - 管理 topoRawDataCache / topoRawData / 聚合配置等数据状态
 * - API 数据获取（getGraphData）与格式化（formatResponseData 等）
 * - ELK 布局计算（resolveLayout）
 * - 视口辅助函数（isItemInView / moveToCenterIfNeeded）
 * - 自动刷新定时器（refreshTimeout）
 *
 * ## 依赖注入
 * - state: 从 useTopoState 接收响应式状态
 * - graphAccess: GraphAccess — 通过 getGraph() 读取当前 Graph 实例
 * - initGraphCallback: 延迟注册的回调，在 topoRawData.value 赋值后触发初始化（不在 .finally() 中，确保数据已就绪）
 */

import { type Ref, ref as deepRef } from 'vue';

import { incidentTopology } from 'monitor-api/modules/incident';
import { deepClone, random } from 'monitor-common/utils/utils.js';

import ElkjsUtils from '../graph/elkjs-utils';
import formatTopoData, { type NodeArgs } from '../graph/format-topo-data';

import type { GraphAccess } from '../types/composable';
import type { ErrorData, TopoRawDataCache } from '../types/g6';
import type { IEdge, IEntity, ITopoCombo, ITopoData, ITopoNode } from '../types/topo';
import type { Graph } from '@antv/g6';

// ============================================================================
// 类型定义
// ============================================================================

/** useTopoData 需要从 useTopoState 接收的状态子集 */
export interface TopoDataState {
  errorData: Ref<ErrorData>;
  incidentId: Ref<string>;
  isPlay: Ref<boolean>;
  loading: Ref<boolean>;
  nodeEntityId: Ref<string>;
  nodeEntityName: Ref<string>;
  refreshTime: Ref<number>;
  resourceNodeId: Ref<string>;
  timelinePosition: Ref<number>;
  wrapRef: Ref<HTMLDivElement | undefined>;
}

export type UseTopoDataReturn = ReturnType<typeof useTopoData>;

/**
 * formatResponseData 入参：接近完整拓扑的 API raw 结构
 * 字段均可选，函数内会用默认空数组兜底并就地改写 comboId
 */
type FormatResponseInput = Partial<ITopoData> & { sub_combos?: ITopoCombo[] };

/**
 * 布局计算入参：完整拓扑数据 + 可选 sub_combos（API/缓存帧可能带该字段）
 * 与 ITopoData 对齐，避免 resolveLayout 继续使用 any
 */
type LayoutInput = ITopoData & { sub_combos?: ITopoCombo[] };

// ============================================================================
// Composable
// ============================================================================

/** resolveLayout 的返回结构：ELK 布局结果 + 回写坐标后的拓扑数据 */
type ResolveLayoutResult = {
  data: LayoutInput;
  /** ELK 原始布局结果，具体结构由 ElkjsUtils 决定，此处不强制展开 */
  layouted: unknown;
};

export function useTopoData(state: TopoDataState, graphAccess: GraphAccess) {
  // ---------------------------------------------------------------------------
  // 数据状态（从 use-topo-state 迁移而来）
  // ---------------------------------------------------------------------------

  /** 拓扑原始数据缓存，包含 diff（差异帧列表）、latest（最新帧）、complete（完整数据） */
  const topoRawDataCache = deepRef<TopoRawDataCache>({
    diff: [],
    latest: { nodes: [] },
    complete: { nodes: [], combos: [], edges: [] },
  });

  /** 当前拓扑完整原始数据（格式化后的），用于查找节点/边、判断根因等 */
  const topoRawData = deepRef<ITopoData | null>(null);

  /** 是否自动聚合同类节点，默认开启 */
  const autoAggregate = deepRef<boolean>(true);

  /** 聚合配置参数，传递给 formatTopoData 的聚合逻辑 */
  const aggregateConfig = deepRef<Record<string, any>>({});

  /** 是否调用关系聚合，默认开启 */
  const aggregateCall = deepRef<boolean>(true);

  /** 是否部署版本聚合，默认关闭 */
  const aggregateVersion = deepRef<boolean>(false);

  // ---------------------------------------------------------------------------
  // 模块内部非响应式变量
  // ---------------------------------------------------------------------------

  /** 自动刷新定时器 ID */
  let refreshTimeout: null | ReturnType<typeof setTimeout> = null;

  // ---------------------------------------------------------------------------
  // 回调注册（用于打破 getGraphData ↔ initGraph 循环依赖）
  // ---------------------------------------------------------------------------

  let _initGraphCallback: (() => void) | null = null;

  /** 延迟注册 initGraph 回调，由主文件在定义 initGraph 后调用 */
  function registerInitGraphCallback(cb: () => void) {
    _initGraphCallback = cb;
  }

  /** 组件卸载时清空回调引用，释放闭包持有的大量 composable state */
  function cleanupData() {
    _initGraphCallback = null;
  }

  // ---------------------------------------------------------------------------
  // 纯数据变换函数（无 ref/let/graph 依赖）
  // ---------------------------------------------------------------------------

  /**
   * 清洗 ComboID 避免重复 ID 导致绘制错误
   * API 返回数据 ComboID 和 nodeID 会重复
   * @param data 接近 ITopoData 的 API raw（含可选 sub_combos），就地改写节点/combo
   */
  const formatResponseData = (data: FormatResponseInput) => {
    const { combos = [], nodes = [], sub_combos = [] } = data || {};
    // biome-ignore lint/complexity/noForEach: <explanation>
    nodes.forEach(node =>
      Object.assign(node, {
        width: 90,
        height: 92,
        // getComboId 入参为 string，可选字段统一转字符串或空串
        comboId: ElkjsUtils.getComboId(node.comboId != null ? String(node.comboId) : ''),
        subComboId: ElkjsUtils.getComboId(node.subComboId != null ? String(node.subComboId) : ''),
      })
    );
    combos.forEach(formatComboOption);
    sub_combos.forEach(formatSubcomboOption);
  };

  /** 为 sub_combo 添加 ID / comboId / isCombo 标记（就地 Object.assign，入参用 ITopoCombo） */
  const formatSubcomboOption = (combo: ITopoCombo) => {
    // getComboId 入参为 string，ITopoCombo.id 可能为 number，统一转字符串
    Object.assign(combo, {
      id: ElkjsUtils.getComboId(String(combo.id)),
      isCombo: true,
      comboId: ElkjsUtils.getComboId(combo.comboId != null ? String(combo.comboId) : ''),
    });
  };

  /** 为 combo 添加样式、label 配置等展示属性（就地 Object.assign，入参用 ITopoCombo） */
  const formatComboOption = (combo: ITopoCombo) => {
    // getComboId 入参为 string，ITopoCombo.id 可能为 number，统一转字符串
    Object.assign(combo, {
      id: ElkjsUtils.getComboId(String(combo.id)),
      isCombo: true,
      comboId: ElkjsUtils.getComboId(combo.comboId != null ? String(combo.comboId) : ''),
      type: 'rect',
      style: {
        cursor: 'grab',
        fill: '#1D2024',
        radius: 4,
        stroke: '#333333',
      },
      labelCfg: {
        style: {
          fill: '#C4C6CC',
          fontSize: 12,
        },
      },
    });
  };

  // ---------------------------------------------------------------------------
  // 视口辅助函数（参数全显式传入，无闭包依赖）
  // ---------------------------------------------------------------------------

  /** 判断某个节点/边是否完全在视口可视区域内 */
  function isItemInView(graph: Graph, itemId: string, containerWidth: number, containerHeight: number) {
    // 获取图表实例中的项目
    const item = graph.findById(itemId);
    if (!item) {
      console.error(`Item with id: ${itemId} not found`);
      return false;
    }

    const itemBBox = item.getBBox();
    // 当前组的矩阵，用于考虑缩放
    const matrix = graph.get('group').getMatrix();
    const currentScale = matrix ? matrix[0] : 1;

    // 获取项目位置基于缩放后的实际位置，进行缩放校正
    const scaledBBox = {
      minX: itemBBox.minX * currentScale,
      minY: itemBBox.minY * currentScale,
      maxX: itemBBox.maxX * currentScale,
      maxY: itemBBox.maxY * currentScale,
    };

    // 检查项目是否完全在视口内
    return (
      scaledBBox.minX >= 0 &&
      scaledBBox.maxX <= containerWidth &&
      scaledBBox.minY >= 0 &&
      scaledBBox.maxY <= containerHeight
    );
  }

  /** 如果指定节点不在视口内，将视口移动到该节点中心 */
  function moveToCenterIfNeeded(graph: Graph, itemId: string, containerWidth: number, containerHeight: number) {
    if (isItemInView(graph, itemId, containerWidth, containerHeight)) {
      console.info(`Item with id: ${itemId} is already in view`);
      graph.moveTo(0, 0);
      return;
    }

    const item = graph.findById(itemId);
    const itemBBox = item.getBBox();

    // 获取缩放比例
    const matrix = graph.get('group').getMatrix();
    const currentScale = matrix ? matrix[0] : 1;

    // 画布中心位置
    const canvasCenterX = containerWidth / 2;
    const canvasCenterY = containerHeight / 2;

    // 项目的中心位置
    const itemCenterX = (itemBBox.minX + itemBBox.maxX) / 2;
    const itemCenterY = (itemBBox.minY + itemBBox.maxY) / 2;

    // 计算将项目移动到画布中心所需的偏移量
    const moveX = canvasCenterX - itemCenterX * currentScale;
    const moveY = canvasCenterY - itemCenterY * currentScale;

    // 移动视口到目标位置
    graph.translate(moveX, moveY);
  }

  // ---------------------------------------------------------------------------
  // 布局计算
  // ---------------------------------------------------------------------------

  /**
   * ELK 布局计算，返回布局后的数据和布局坐标
   * @param data 完整拓扑 + 可选 sub_combos；内部深拷贝后回写坐标
   */
  const resolveLayout = (data: LayoutInput): Promise<ResolveLayoutResult> => {
    const graph = graphAccess.getGraph();
    const copyData = JSON.parse(JSON.stringify(data)) as LayoutInput;
    // LayoutInput 与 formatTopoData 的 NodeArgs 结构兼容，运行时一致，此处做类型适配
    const { layoutNodes, edges, nodes } = formatTopoData(copyData as unknown as NodeArgs);
    const resolvedData = ElkjsUtils.getKlayGraphData({ nodes: layoutNodes, edges, source: nodes });
    return ElkjsUtils.getLayoutData(resolvedData).then(layouted => {
      ElkjsUtils.updatePositionFromLayouted(layouted, copyData);
      data.sub_combos?.length > 0 && ElkjsUtils.OptimizeLayout(layouted, copyData, edges);
      ElkjsUtils.setRootComboStyle(copyData.combos, graph?.getWidth() ?? 0);
      return { layouted, data: copyData };
    });
  };

  // ---------------------------------------------------------------------------
  // 数据获取（核心 API 调用）
  // ---------------------------------------------------------------------------

  /** 获取拓扑数据，处理 API 响应、错误、刷新定时器 */
  const getGraphData = async (isAutoRefresh = false) => {
    state.loading.value = !isAutoRefresh;
    if (!state.wrapRef.value) return;
    clearTimeout(refreshTimeout!);
    const params: Record<string, any> = {
      id: state.incidentId.value,
      auto_aggregate: autoAggregate.value,
      aggregate_cluster: aggregateCall.value,
      aggregate_version: aggregateVersion.value,
      only_diff: true,
      start_time: isAutoRefresh
        ? topoRawDataCache.value.diff[topoRawDataCache.value.diff.length - 1].create_time + 1
        : state.incidentId.value.substr(0, 10),
    };
    // 手动聚合时，才传 aggregate_config
    if (!autoAggregate.value) {
      params.aggregate_config = aggregateConfig.value;
    }
    let isCancelled = false;
    const renderData = await incidentTopology(params, { needMessage: false, needCancel: true })
      .then(res => {
        const { latest, diff, complete } = res;
        complete.combos = latest.combos;
        formatResponseData(complete);
        const { combos = [], edges = [], nodes = [], sub_combos = [] } = complete || {};
        state.errorData.value.isNoData = combos.length === 0;
        state.errorData.value.isError = false;
        ElkjsUtils.setSubCombosMap(ElkjsUtils.getSubComboCountMap(nodes));
        const resolvedCombos = [...combos, ...ElkjsUtils.resolveSumbCombos(sub_combos)];
        const processedNodes = [];
        const processedEdges = [];
        const processedSubCombos = [];
        // biome-ignore lint/complexity/noForEach: <explanation>
        diff.forEach(item => {
          item.showNodes = [...processedNodes];
          // biome-ignore lint/complexity/noForEach: <explanation>
          item.content.nodes.forEach(showNode => {
            const index = processedNodes.findIndex(node => node.id === showNode.id);
            if (index !== -1) {
              processedNodes[index] = showNode;
            } else {
              processedNodes.push(showNode);
            }
          });
          processedNodes.push(item.content.nodes);
          // biome-ignore lint/complexity/noForEach: <explanation>
          item.content.edges.forEach(edge => {
            const key = edge.target + edge.source;
            const index = processedEdges.findIndex(item => item.target + item.source === key);
            if (index !== -1) {
              processedEdges[index] = edge;
            } else {
              processedEdges.push(edge);
            }
          });
          item.showSubCombos = [...processedSubCombos];
          processedSubCombos.push(...item.content.sub_combos);
          item.showEdges = [...processedEdges];
        });
        topoRawDataCache.value.diff = diff;
        topoRawDataCache.value.latest = latest;
        topoRawDataCache.value.complete = { ...complete, combos: resolvedCombos };
        const diffLen = topoRawDataCache.value.diff.length;
        state.timelinePosition.value = diffLen - 1;
        return ElkjsUtils.getTopoRawData(resolvedCombos, edges, nodes);
      })
      .catch(err => {
        // 被 needCancel 取消的请求，标记后跳过，保持 loading 状态等待后续请求完成
        if (!err) {
          isCancelled = true;
          return;
        }
        state.errorData.value.isError = true;
        state.errorData.value.msg = err.data?.error_details ? err.data.error_details.overview : err.message;
        state.errorData.value.isNoData = false;
      })
      .finally(() => {
        // 被取消的请求不执行 finally 逻辑，保持 loading 不变
        if (isCancelled) return;

        state.loading.value = false;
        if (state.refreshTime.value !== -1) {
          refreshTimeout = setTimeout(() => {
            getGraphData(true);
          }, state.refreshTime.value);
        }
      });
    if (isAutoRefresh || !renderData) return;
    topoRawData.value = renderData as ITopoData;
    // 首次加载且 graph 尚未创建时，触发 initGraph（此时 topoRawData.value 已赋值）
    const existingGraph = graphAccess.getGraph();
    if (!existingGraph && _initGraphCallback) {
      _initGraphCallback();
    }
    const rootNode = topoRawData.value.nodes.find(node => node.entity.is_root);
    if (!state.resourceNodeId.value && rootNode) {
      state.resourceNodeId.value = rootNode.id;
      state.nodeEntityId.value = rootNode.entity.entity_id;
      state.nodeEntityName.value = rootNode.entity.entity_name;
    }
  };

  // ---------------------------------------------------------------------------
  // 刷新定时器管理
  // ---------------------------------------------------------------------------

  /** 清除自动刷新定时器 */
  function clearRefreshTimeout() {
    clearTimeout(refreshTimeout!);
  }

  /** 设置刷新时间并重启定时器 */
  const handleChangeRefleshTime = (RefleshTime: number) => {
    clearTimeout(refreshTimeout!);
    state.refreshTime.value = RefleshTime;
    if (RefleshTime !== -1 && !state.isPlay.value) {
      refreshTimeout = setTimeout(() => getGraphData(true), RefleshTime);
    }
  };

  // ---------------------------------------------------------------------------
  // 边数据处理辅助（供 interaction composable 使用）
  // ---------------------------------------------------------------------------

  /**
   * 处理单个边的公共逻辑，构造边关联节点数据
   * @returns 带随机 id 与 nodes 的边模型（仍归入 IEdge）
   */
  const processEdge = (edge: IEdge, nodes: ITopoNode[], isAggregatedEdge = false): IEdge => {
    const model = deepClone(edge) as IEdge;
    model.id = `edge-${random(10)}`;
    const getEntityData = (prefix: string) =>
      isAggregatedEdge
        ? {
            entity: {
              is_anomaly: model[`${prefix}_is_anomaly`],
              is_on_alert: model[`${prefix}_is_on_alert`],
              entity_name: model[`${prefix}_name`],
              entity_type: model[`${prefix}_type`],
            },
          }
        : {};

    const targetModel = nodes.find(item => item.id === model.target);
    const sourceModel = nodes.find(item => item.id === model.source);
    // 聚合边会用 getEntityData 补齐 entity，再与源/目标节点合并，结果按 ITopoNode 使用
    model.nodes = [
      {
        ...getEntityData('source'),
        ...sourceModel,
        events: model.events || [],
      },
      {
        ...getEntityData('target'),
        ...targetModel,
        events: model.events || [],
      },
    ] as any;

    return model;
  };

  /** 整合与指定 nodeId 关联的边数据（含聚合边） */
  const filterEdges = (edges: IEdge[], nodes: ITopoNode[], nodeId: string): IEdge[] => {
    const result: IEdge[] = [];
    const checkAndProcess = (edge: IEdge, isAggregated = false) => {
      if (edge.source === nodeId || edge.target === nodeId) {
        result.push(processEdge(edge, nodes, isAggregated));
      }
    };

    // biome-ignore lint/complexity/noForEach: <explanation>
    edges.forEach(mainEdge => {
      checkAndProcess(mainEdge);
      // biome-ignore lint/complexity/noForEach: <explanation>
      mainEdge.aggregated_edges?.forEach(aggEdge => {
        checkAndProcess(aggEdge, true);
      });
    });
    return result;
  };

  // ---------------------------------------------------------------------------
  // 查找边辅助函数（供时间轴 composable 使用）
  // ---------------------------------------------------------------------------

  /**
   * 在边列表中查找匹配 source/target 的边
   * @param target 只需提供 source/target 即可匹配（也可传入完整 IEdge）
   */
  const findEdges = (edges: IEdge[], target: IEdge | Pick<IEdge, 'source' | 'target'>): IEdge | undefined => {
    return edges.find(item => item.source === target.source && target.target === item.target);
  };

  return {
    // 数据状态
    topoRawDataCache,
    topoRawData,
    autoAggregate,
    aggregateConfig,
    aggregateCall,
    aggregateVersion,
    // 纯数据变换
    formatComboOption,
    formatSubcomboOption,
    // 视口辅助
    moveToCenterIfNeeded,
    // 布局计算
    resolveLayout,
    // 数据获取
    getGraphData,
    registerInitGraphCallback,
    cleanupData,
    // 刷新定时器
    handleChangeRefleshTime,
    clearRefreshTimeout,
    // 边数据处理
    filterEdges,
    findEdges,
  };
}
