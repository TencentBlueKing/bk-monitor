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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
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
 * @file 拓扑图 Graph 初始化与操作 Composable
 * @description 负责管理 FailureTopo 组件的 Graph 创建、事件绑定、渲染和 resize
 *
 * ## 职责
 * - initGraph: 创建 Graph 实例 + 注册自定义类型 + 绑定所有事件
 * - renderGraph: 渲染拓扑数据到 Graph
 * - handleResize: 窗口 resize 时重新布局和调整
 * - cleanupGraph: 组件卸载时清理 G6 相关资源（动画 + resize 监听）
 *
 * ## 依赖注入
 * - state: 从 useTopoState 接收响应式状态（含 graphInstanceRef / g6TooltipRef）
 * - data: 从 useTopoData 接收数据和函数（含 topoRawDataCache）
 * - interaction / timeline / tooltip: 各 composable 返回的能力子集
 */

import { type Ref, type ShallowRef, nextTick } from 'vue';

import { type ICombo, type IG6GraphEvent, type INode, type Item, Arrow, Graph } from '@antv/g6';
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { debounce } from 'throttle-debounce';

import ElkjsUtils from '../graph/elkjs-utils';
import { clearAllG6Animations, registerAllAfterGraph, registerAllBeforeGraph } from '../graph/register-all';
import { clearEdgeIntervals } from '../graph/topo-edge';
import { createTruncateByTextWidth } from '../graph/topo-node';
import { canJumpByType, handleToLink } from '../utils';

import type { G6TooltipInstance } from '../types/composable';
import type { CanvasByPointResult, ComboLabelPoint, NavSelectNodeItem, TopoRawDataCache } from '../types/g6';
import type { IncidentDetailData, ITopoCombo, ITopoData, ITopoNode } from '../types/topo';
import type { TooltipCompExpose } from './use-topo-state';
import type { GraphData } from '@antv/g6';

// ============================================================================
// 类型定义
// ============================================================================

/** useTopoGraph 需要从 useTopoData 接收的数据函数子集 */
export interface TopoGraphData {
  /** 拓扑完整原始数据（格式化后的） */
  topoRawData: Ref<ITopoData | null>;
  /** 拓扑原始数据缓存（含 diff / complete） */
  topoRawDataCache: Ref<TopoRawDataCache>;
  /** 如果指定节点不在视口内，将视口移动到该节点中心 */
  moveToCenterIfNeeded: (graph: Graph, itemId: string, containerWidth: number, containerHeight: number) => void;
  /** ELK 布局计算 */
  resolveLayout: (data: LayoutInput) => Promise<ResolveLayoutResult>;
}

/** useTopoGraph 需要从 useTopoInteraction 接收的交互函数子集 */
export interface TopoGraphInteraction {
  /** G6 默认缩放级别下限 */
  MIN_ZOOM: number;
  /** 导航选中节点计算属性 */
  navSelectNode: Ref<NavSelectNodeItem[]>;
  /** 清除高亮状态 */
  clearAllStats: () => void;
  /** 清除边状态 */
  clearEdgeState: (item: Item, highlight?: boolean) => void;
  /** 获取 combo 画布坐标包围盒边界 */
  getCanvasByPoint: (combo: ICombo) => CanvasByPointResult;
  /** 反馈根因 */
  handleFeedBack: (model: ITopoNode) => void;
  /** 画布缩放 */
  handleZoomChange: (value: number) => void;
  /** 拖拽时设置 combo label 的位置 */
  moveComboLabelPosition: (point: { x?: number; y?: number }) => void;
  /** 切换 node 清除高亮边信息 */
  setHighlightEdge: (highlight?: boolean, nodeId?: string) => void;
  /** 将所有边置于顶层 */
  toFrontAnomalyEdge: () => void;
}

/** useTopoGraph 需要从 useTopoState 接收的状态子集 */
export interface TopoGraphState {
  /** 当前选中的业务 ID 列表 */
  bkzIds: Ref<string[]>;
  /** 标记当前是否在 resize 过程中 */
  cacheResize: Ref<boolean>;
  /** G6 Tooltip 插件实例 shallowRef（在 registerCustomTooltip 中赋值） */
  g6TooltipRef: ShallowRef<G6TooltipInstance | undefined>;
  /** G6 Graph 实例 shallowRef（在此 composable 的 initGraph 中赋值） */
  graphInstanceRef: ShallowRef<Graph | undefined>;
  /** G6 画布 DOM 容器 ref */
  graphRef: Ref<HTMLElement | null>;
  /** 事件详情数据 */
  incidentDetailData: Ref<IncidentDetailData>;
  /** 是否正在播放时间轴动画 */
  isPlay: Ref<boolean>;
  /** 是否已完成首次渲染 */
  isRenderComplete: Ref<boolean>;
  /** 缓存 resize 回调 */
  resizeCacheCallback: Ref<(() => void) | null>;
  /** 当前选中资源图的边 ID */
  resourceEdgeId: Ref<string>;
  /** 当前选中资源图的节点 ID */
  resourceNodeId: Ref<string>;
  /** 缓存根 combo 拖拽后 label 的坐标 */
  rootComboMovePoint: Ref<ComboLabelPoint>;
  /** 时间轴停留帧索引 */
  timelinePosition: Ref<number>;
  /** Tooltip Vue 组件实例引用 */
  tooltipCompRef: Ref<TooltipCompExpose>;
  /** 缩放级别数值 */
  zoomValue: Ref<number>;
}

/** useTopoGraph 需要从 useTopoTimeline 接收的播放函数子集 */
export interface TopoGraphTimeline {
  /** 帧切换 */
  handleTimelineChange: (value: number, init?: boolean, keepSidePanel?: boolean) => void;
  /** afteritemstatechange 事件回调 */
  onAnimationStateChange: () => void;
}

/** useTopoGraph 需要从 useTopoTooltip 接收的 tooltip 函数子集 */
export interface TopoGraphTooltip {
  /** Combo 鼠标进入 — 显示 label tooltip + 反馈根因文本 */
  handleComboMouseEnter: (e: IG6GraphEvent) => void;
  /** Combo 鼠标离开 — 隐藏 label tooltip + 反馈根因文本 */
  handleComboMouseLeave: (e: IG6GraphEvent) => void;
  /** 节点鼠标进入 — 显示详情 tooltip */
  handleNodeMouseEnter: (e: IG6GraphEvent) => void;
  /** 节点鼠标离开 — 隐藏详情 tooltip */
  handleNodeMouseLeave: (e: IG6GraphEvent) => void;
  /** G6 tooltipchange 事件处理 */
  handleTooltipChange: (e: IG6GraphEvent) => void;
  /** 隐藏 combo-label-tooltip */
  hideComboLabelTooltip: () => void;
  /** 隐藏 G6 Tooltip 插件 */
  hideG6Tooltip: () => void;
  /** 初始化 combo-label-tooltip DOM 元素 */
  initComboLabelTooltip: () => void;
  /** 初始化 node-detail-tips DOM 元素 */
  initNodeInfoTooltip: () => void;
  /** 注册自定义 G6 Tooltip 插件 */
  registerCustomTooltip: () => void;
}

export type UseTopoGraphReturn = ReturnType<typeof useTopoGraph>;

/**
 * 布局计算入参（与 use-topo-data 中 LayoutInput 等价；该类型未导出故本地复刻）
 * 完整拓扑数据 + 可选 sub_combos
 */
type LayoutInput = ITopoData & { sub_combos?: ITopoCombo[] };

// ============================================================================
// Composable
// ============================================================================

/** resolveLayout 返回结构（与 use-topo-data 中 ResolveLayoutResult 等价） */
type ResolveLayoutResult = {
  data: LayoutInput;
  /** ELK 原始布局结果 */
  layouted: unknown;
};

export function useTopoGraph(
  state: TopoGraphState,
  topoData: TopoGraphData,
  interaction: TopoGraphInteraction,
  timeline: TopoGraphTimeline,
  tooltip: TopoGraphTooltip
) {
  // ---------------------------------------------------------------------------
  // Graph 实例便捷访问
  // ---------------------------------------------------------------------------

  /** 获取当前 Graph 实例（undefined 表示尚未初始化） */
  const getGraph = () => state.graphInstanceRef.value;

  // ---------------------------------------------------------------------------
  // 渲染数据
  // ---------------------------------------------------------------------------

  /** 渲染拓扑数据到 Graph */
  const renderGraph = (renderData = topoData.topoRawDataCache.value.complete, renderComplete = false) => {
    const graph = getGraph();
    if (!graph) return;
    clearEdgeIntervals();
    topoData.resolveLayout(renderData).then(resp => {
      // LayoutInput 与 G6 GraphData 字段对齐，断言后写入画布
      graph.data(resp.data as GraphData);
      graph.render();
      if (state.resourceNodeId.value) {
        const node = graph.findById(state.resourceNodeId.value);
        node && graph.setItemState(node, 'running', true);
      }
      interaction.setHighlightEdge();
      state.isRenderComplete.value = renderComplete;
      // 获取用户拖动设置后的zoom缩放级别
      const zoom = localStorage.getItem('failure-topo-zoom');
      if (zoom) {
        // localStorage 取出为 string，缩放接口要求 number
        interaction.handleZoomChange(Number(zoom));
        state.zoomValue.value = Number(zoom);
      }
      topoData.moveToCenterIfNeeded(
        graph,
        state.resourceNodeId.value,
        state.graphRef.value!.clientWidth,
        state.graphRef.value!.clientHeight
      );
      // biome-ignore lint/complexity/noForEach: <explanation>
      renderData.nodes.forEach(node => {
        if (node.is_deleted) {
          const deleteNode = graph.findById(node.id) as INode;
          if (!deleteNode) return;
          // biome-ignore lint/complexity/noForEach: <explanation>
          deleteNode.getEdges().forEach(edge => edge.hide());
          deleteNode.hide();
        }
      });
      /** 布局渲染完将边置于顶层 */
      setTimeout(interaction.toFrontAnomalyEdge, 500);
    });
  };

  // ---------------------------------------------------------------------------
  // 窗口 resize 处理
  // ---------------------------------------------------------------------------

  /** 窗口变化 */
  function handleResize() {
    const graph = getGraph();
    if (!graph || graph.get('destroyed') || !state.graphRef.value) return;
    /** 播放过程中不需 resize，等待播放完毕后判断 resize */
    if (state.isPlay.value) {
      state.cacheResize.value = true;
      return;
    }
    const graphWidth = graph.getWidth();
    const { height } = document.querySelector('.failure-topo')!.getBoundingClientRect();
    const { width } = state.graphRef.value.getBoundingClientRect();
    state.tooltipCompRef.value?.hide?.();
    state.rootComboMovePoint.value = { x: null, y: null };
    tooltip.hideG6Tooltip();
    // getModel() 返回 G6 ModelConfig，业务层按 ITopoCombo 使用
    const combosList = graph.getCombos().map(combo => combo.getModel()) as ITopoCombo[];
    ElkjsUtils.setRootComboStyle(combosList, width, !(graphWidth - width > 450));
    // biome-ignore lint/complexity/noForEach: <explanation>
    graph.getCombos().forEach(combo => {
      if (!combo.getModel()?.parentId) {
        const com = combosList.find(c => c.id === combo.getID());
        // updateItem 官方 cfg 类型偏窄，业务 combo 模型此处宽松传入
        graph.updateItem(combo, com as any);
      }
    });
    graph.changeSize(width, height - 40);
    graph.get('viewController').changeSize(width, height - 40);
    graph.layout();
    /** resize + layout 完成后，触发缓存的回调（如 handleResetPlay 延迟启动播放）
     *  G6 v3 中 graph.layout() 只触发 afterlayout 事件，不触发 afterrender，
     *  而 resizeCacheCallback 仅在 initGraph 的 afterrender 中被调用，
     *  导致侧滑关闭时 resizeCacheCallback 永远不会被执行。
     *  在此处显式调用，确保 resize 完成后回调能触发。
     *  回调内部会先清空自身，afterrender 的重复调用不会造成问题。 */
    state.resizeCacheCallback.value?.();
    graph.translate(graphWidth - width > 450 ? -10 : 0, 0);
    const zoom = localStorage.getItem('failure-topo-zoom');
    if (zoom) {
      // localStorage 取出为 string，缩放接口要求 number
      interaction.handleZoomChange(Number(zoom));
      state.zoomValue.value = Number(zoom);
    }
    state.timelinePosition.value = topoData.topoRawDataCache.value.diff.length - 1;
    /** resize 后同步渲染最后一帧的节点状态 */
    timeline.handleTimelineChange(topoData.topoRawDataCache.value.diff.length - 1, true, true);
    /** 打开时会触发导致动画消失 */
    if (state.resourceNodeId.value) {
      const isNavSelectNode = interaction.navSelectNode.value.some(node => node.id === state.resourceNodeId.value);
      if (isNavSelectNode) {
        // biome-ignore lint/complexity/noForEach: <explanation>
        interaction.navSelectNode.value.forEach(node => {
          graph.setItemState(graph.findById(node.id), 'running', true);
        });
        return;
      }
      const node = graph.findById(state.resourceNodeId.value);
      node && graph.setItemState(node, 'running', true);
    }
    if (!state.resourceEdgeId.value) {
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getEdges().forEach(edge => {
        edge && graph.setItemState(edge, 'highlight', false);
      });
    }
  }

  const onResize = debounce(300, handleResize);

  // ---------------------------------------------------------------------------
  // Graph 初始化
  // ---------------------------------------------------------------------------

  /** 初始化图表相关 */
  const initGraph = async () => {
    if (!topoData.topoRawData.value) return;
    const { width, height } = state.graphRef.value!.getBoundingClientRect();
    const maxHeight = Math.max(160 * ElkjsUtils.getRootCombos(topoData.topoRawData.value).length, height);

    // 注册自定义 G6 类型（需要在 Graph 创建之前注册 edge、combo、behavior）
    registerAllBeforeGraph({
      toFrontAnomalyEdge: interaction.toFrontAnomalyEdge,
      rootComboMovePoint: state.rootComboMovePoint,
      moveComboLabelPosition: interaction.moveComboLabelPosition,
      getCanvasByPoint: interaction.getCanvasByPoint,
    });
    tooltip.registerCustomTooltip();

    // 创建 Graph 实例，赋值到 shallowRef
    const graph = new Graph({
      container: state.graphRef.value as HTMLElement,
      width,
      height: maxHeight,
      fitViewPadding: 40,
      fitCenter: false,
      fitView: false,
      minZoom: interaction.MIN_ZOOM,
      maxZoom: 2,
      groupByTypes: false,
      plugins: [state.g6TooltipRef.value],
      defaultNode: {
        type: 'circle',
        size: 40,
        style: {
          cursor: 'pointer',
        },
        // 定义连接点
        anchorPoints: [
          [0.5, 0], // 顶部中间
          [0, 0.5], // 左侧中间
          [1, 0.5], // 右侧中间
          [0.5, 1], // 底部中间
        ],
      },
      defaultEdge: {
        size: 1,
        color: '#63656D',
        style: {
          cursor: 'pointer',
        },
      },
      modes: {
        default: [
          'drag-node-with-fixed-combo',
          'drag-canvas-no-move',
          'drag-canvas-move',
          {
            type: 'scroll-canvas',
            scalableRange: -0.92,
          },
        ],
      },
      comboStateStyles: {
        active: {
          fill: '#3A3B3D',
          stroke: '#3A3B3D',
        },
        inactive: {
          fill: '#3A3B3D',
          stroke: '#3A3B3D',
        },
      },
    });
    state.graphInstanceRef.value = graph;

    // 创建文本截断函数（基于 graph canvas context），注册自定义节点
    const truncateByTextWidth = createTruncateByTextWidth(graph.get('canvas').get('context'));
    registerAllAfterGraph(truncateByTextWidth);
    graph.node(node => {
      return {
        ...node,
        stateStyles: {
          active: {
            stroke: '#3A3B3D',
          },
        },
        type: 'topo-node',
      };
    });
    graph.edge((cfg: any) => {
      const { is_anomaly, edge_type, anomaly_score, source, target } = cfg;
      const isInvoke = edge_type === 'ebpf_call';
      const color = is_anomaly ? '#F55555' : '#63656E';
      const isSelfLoop = source === target;

      const edg = {
        ...cfg,
        shape: 'quadratic',
        style: {
          cursor: 'pointer',
          lineAppendWidth: 15,
          endArrow:
            isInvoke || is_anomaly
              ? {
                  path: Arrow.triangle(10, 10, 0),
                  d: 0,
                  fill: color,
                  stroke: color,
                  lineDash: [0, 0],
                }
              : false,
          // fill: isInvoke ? '#F55555' : '#63656E',
          stroke: color,
          lineWidth: is_anomaly ? (anomaly_score > 0 ? 3 : 1.5) : 1,
          lineDash: is_anomaly ? [4, 2] : false,
        },
      };
      if (!cfg.color) return edg;
      if (isSelfLoop) {
        return {
          ...edg,
          shape: 'loop',
          type: 'topo-edge-loop',
          loopCfg: {
            dist: 60, // 自环边与节点的距离
            clockwise: true, // 顺时针方向
          },
        };
      }
      return {
        ...edg,
        shape: 'quadratic',
        type: 'topo-edge',
      };
    });
    graph.combo((cfg: any) => {
      const originLabel = cfg.originLabel || cfg.label;
      const model = {
        ...cfg,
        originLabel: originLabel,
      };
      if (cfg.parentId) {
        // label宽度为cfg.width减去"反馈根因节点"文本宽度
        const labelWidth = cfg.width - (cfg.is_feedback_root ? 90 : 56);
        const link = canJumpByType(cfg);
        const fill = link ? '#699DF4' : '#C4C6CC';
        return {
          ...model,
          type: 'service-combo',
          label: truncateByTextWidth(cfg.label, labelWidth),
          style: {
            fill: '#34383d',
            stroke: '#7A7C80',
            lineWidth: 1,
            lineDash: [2, 3],
            opacity: 1,
            radius: 4,
          },
          labelCfg: {
            style: {
              fill,
              opacity: 1,
              cursor: link ? 'pointer' : 'default',
            },
            // 启用 label 事件捕获
            triggerable: true,
          },
        };
      }
      return model;
    });
    renderGraph();

    // ---------------------------------------------------------------------------
    // 事件绑定
    // ---------------------------------------------------------------------------

    /** 点击tips时，关闭右侧资源打开的tips */
    graph.on('tooltipchange', tooltip.handleTooltipChange);

    /** 点击非节点、非边，清除高亮状态 */
    graph.on('click', e => {
      if (!e.item || (e.item.getType() !== 'node' && e.item.getType() !== 'edge')) {
        interaction.clearAllStats();
      }
      setTimeout(interaction.toFrontAnomalyEdge, 500);
    });

    // 初始化 DOM tooltip 元素并绑定 combo/node tooltip 事件
    tooltip.initComboLabelTooltip();
    tooltip.initNodeInfoTooltip();
    graph.on('combo:mouseenter', tooltip.handleComboMouseEnter);
    graph.on('combo:mouseleave', tooltip.handleComboMouseLeave);
    graph.on('node:mouseenter', tooltip.handleNodeMouseEnter);
    graph.on('node:mouseleave', tooltip.handleNodeMouseLeave);

    /** 监听手势缩放联动缩放轴数据 */
    graph.on('viewportchange', ({ action }) => {
      if (action === 'zoom') {
        state.zoomValue.value = graph.getZoom() * 10;
      }
      const currentZoom = graph.getZoom();
      // if (action === 'translate') {
      const firstCombo = graph.getCombos()[0] as ICombo;
      const comboModel = firstCombo.getModel() as { height: number; width: number };
      const labelPoint = {
        x: -(comboModel.width / 2 + 10) * currentZoom,
        y: -(comboModel.height / 2 + 30) * currentZoom,
      };
      const canvasCenter = graph.getGraphCenterPoint(); // 画布中心
      if (canvasCenter.x < Math.abs(labelPoint.x)) {
        const x = -(canvasCenter.x - 5) / currentZoom;
        interaction.moveComboLabelPosition({ x });
        state.rootComboMovePoint.value.x = x;
      } else {
        state.rootComboMovePoint.value.x = null;
        interaction.moveComboLabelPosition({ x: labelPoint.x / currentZoom });
      }
      // }
    });
    /** resize之后的render 调用一次缓存的函数 通知可以播放 */
    graph.on('afterrender', () => {
      state.resizeCacheCallback.value?.();
    });
    /** 设置节点高亮状态 */
    graph.on('node:click', event => {
      const { item } = event;
      graph.setAutoPaint(false);
      /** 根据边的关系设置节点状态 */
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getEdges().forEach(edge => {
        if (edge.getSource() === item) {
          graph.setItemState(edge, 'dark', true);
          edge.toFront();
        } else if (edge.getTarget() === item) {
          graph.setItemState(edge, 'dark', true);
          edge.toFront();
        } else {
          graph.setItemState(edge, 'dark', false);
        }
      });
      // biome-ignore lint/complexity/noForEach: <explanation>
      graph.getNodes().forEach(node => {
        graph.clearItemStates(node, ['dark', 'highlight']);
        graph.setItemState(node, 'dark', true);
        node.toFront();
      });
      graph.setItemState(item, 'dark', false);
      graph.setItemState(item, 'highlight', true);
      graph.paint();
      graph.setAutoPaint(true);
    });
    /** 设置边高亮状态 */
    graph.on('edge:click', ({ item }) => {
      graph.setAutoPaint(false);
      const { source, target, count } = item.getModel();
      interaction.clearEdgeState(item, count === 1);
      graph.paint();
      graph.setAutoPaint(true);
      item.toFront();
      state.resourceEdgeId.value = `${source}-${target}`;
      if (count === 1) {
        graph.setItemState(item, 'highlight', true);
        graph.setItemState(item, 'dark', true);
      }
    });

    graph.on('combo:click', e => {
      state.tooltipCompRef.value?.hide?.();
      tooltip.hideG6Tooltip();
      tooltip.hideComboLabelTooltip();

      // 点击"反馈新根因"，打开反馈弹窗
      const { target, item } = e;
      const model = item.getModel();
      if (model.type !== 'service-combo') return;
      if (target.get('name') === 'text-shape') {
        handleToLink(model, state.bkzIds.value, state.incidentDetailData.value);
        return;
      }
      if (target.get('className') === 'sub-combo-label-feedback') {
        // getModel() 返回 G6 配置，反馈根因按业务节点模型使用
        interaction.handleFeedBack(model as ITopoNode);
      }
    });
    /** 触发下一帧播放 - 动画完成后继续处理队列 */
    graph.on('afteritemstatechange', ({ state }) => {
      if (state && !(state as string).includes('show-animate')) return;
      timeline.onAnimationStateChange();
    });
    nextTick(() => {
      addListener(state.graphRef.value as HTMLElement, onResize);
    });
  };

  // ---------------------------------------------------------------------------
  // G6 资源清理（由主文件在 onUnmounted 中调用）
  // ---------------------------------------------------------------------------

  /** 清理 G6 资源（动画、resize 监听、Graph 实例），由主文件在 onUnmounted 中调用 */
  const cleanupGraph = () => {
    clearAllG6Animations();
    const graphEl = state.graphRef.value;
    graphEl && removeListener(graphEl as HTMLElement, onResize);
    const graph = getGraph();
    if (graph && !graph.get('destroyed')) {
      graph.destroy();
    }
    // 置空 shallowRef，释放 G6 实例和 Tooltip 插件的引用，允许 GC 回收
    state.graphInstanceRef.value = undefined;
    state.g6TooltipRef.value = undefined;
  };

  return {
    initGraph,
    renderGraph,
    handleResize,
    cleanupGraph,
  };
}
