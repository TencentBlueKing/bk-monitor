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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR DEALINGS IN
 * THE SOFTWARE.
 */

/**
 * @file 拓扑图 Tooltip Composable
 * @description 负责管理 FailureTopo 组件的所有 tooltip 相关逻辑
 *
 * ## 职责
 * - G6 Tooltip 插件注册（registerCustomTooltip）
 * - Combo Label tooltip DOM 操作（combo:mouseenter/leave）
 * - Node Detail tips DOM 操作（node:mouseenter/leave）
 * - tooltipchange 事件处理
 * - Combo 点击时 tooltip 隐藏辅助
 * - resize 时 tooltip 隐藏辅助
 *
 * ## 依赖注入
 * - state: 从 useTopoState 接收响应式状态
 * - data: 从 useTopoData 接收 topoRawDataCache
 * - interaction: 从 useTopoInteraction 接收 handleViewServiceFromTopo, handleNodeInfoTooltip
 * - g6TooltipRef: G6 Tooltip 插件 shallowRef（注册时直接赋值，无 setTooltip 桥接）
 * - graphAccess: { getGraph }
 */

import type { Ref, ShallowRef } from 'vue';

import { type IG6GraphEvent } from '@antv/g6';
import { random } from 'monitor-common/utils/utils.js';

import FailureTopoG6Tooltip from '../tooltip/failure-tooltip-plugin';

import type { G6TooltipInstance, GraphAccess } from '../types/composable';
import type { TooltipType, TopoRawDataCache } from '../types/g6';
import type { IEdge, ITopoNode } from '../types/topo';
import type { ResourceGraphExpose, TooltipCompExpose } from './use-topo-state';

// ============================================================================
// 类型定义
// ============================================================================

/** useTopoTooltip 需要从 useTopoData 接收的数据子集 */
export interface TopoTooltipData {
  /** 拓扑原始数据缓存 */
  topoRawDataCache: Ref<TopoRawDataCache>;
}

/** useTopoTooltip 需要从 useTopoInteraction 接收的交互函数子集 */
export interface TopoTooltipInteraction {
  /** 生成节点详情 info tooltip HTML 内容 */
  handleNodeInfoTooltip: (model: ITopoNode) => string;
  /** 通过主画布 tooltip 打开节点/边概览 */
  handleViewServiceFromTopo: (params: {
    data: IEdge | ITopoNode;
    isAggregatedEdge: boolean;
    sourceNode: ITopoNode | null;
    type: TooltipType;
  }) => void;
}

/** useTopoTooltip 需要从 useTopoState 接收的状态子集 */
export interface TopoTooltipState {
  /** Tooltip 边详情数据 */
  edgeDetail: Ref<IEdge>;
  /** 是否为点击边产生的 tooltip */
  isClickEdgeItem: Ref<boolean>;
  /** 资源拓扑组件 ref（薄接口，与 use-topo-state 对齐） */
  resourceGraphRef: Ref<ResourceGraphExpose>;
  /** 是否显示资源拓扑 */
  showResourceGraph: Ref<boolean>;
  /** Tooltip Vue 组件 ref（薄接口，与 use-topo-state 对齐） */
  tooltipCompRef: Ref<TooltipCompExpose>;
  /** Tooltip 边数据 */
  tooltipsEdge: Ref<IEdge>;
  /** Tooltip 数据模型（节点/边） */
  tooltipsModel: Ref<ITopoNode | ITopoNode[]>;
  /** Tooltip 类型（node/edge） */
  tooltipsType: Ref<TooltipType>;
}

// ============================================================================
// Composable
// ============================================================================

export function useTopoTooltip(
  state: TopoTooltipState,
  data: TopoTooltipData,
  interaction: TopoTooltipInteraction,
  /** G6 Tooltip 插件 shallowRef，注册时直接赋值 */
  g6TooltipRef: ShallowRef<G6TooltipInstance | undefined>,
  graphAccess: GraphAccess
) {
  const graph = () => graphAccess.getGraph();

  // ---------------------------------------------------------------------------
  // G6 Tooltip 插件注册
  // ---------------------------------------------------------------------------

  /** 注册自定义 G6 Tooltip 插件 */
  const registerCustomTooltip = () => {
    const tooltipInstance = new FailureTopoG6Tooltip({
      fixToNode: [1, 1],
      // 相对节点右下锚点留出空隙，避免「节点概览」贴住并挡住节点下半区文字
      offsetX: 20,
      offsetY: 20,
      container: document.querySelector('.topo-graph') as HTMLDivElement,
      trigger: 'click',
      // 覆盖插件默认 shouldBegin: false，否则 click 无法展示 tip
      shouldBegin: () => true,
      itemTypes: ['edge', 'node'],
      getContent: (e: IG6GraphEvent) => {
        // 切换节点/边前收起聚合列表内嵌套 Popover，避免残留干扰
        state.tooltipCompRef.value?.hide?.();

        const type = e.item.getType();
        const model = e.item.getModel();
        if (type === 'edge') {
          const { nodes = [] } = data.topoRawDataCache.value.complete;
          const targetModel = nodes.find(item => item.id === model.target);
          const sourceModel = nodes.find(item => item.id === model.source);
          state.tooltipsModel.value = [sourceModel, targetModel];
          state.tooltipsEdge.value = model as IEdge;

          state.edgeDetail.value = model as IEdge;
          state.isClickEdgeItem.value = false;

          model.nodes = [
            {
              ...sourceModel,
              events: model.events || [],
            },
            {
              ...targetModel,
              events: model.events || [],
            },
          ];
          // biome-ignore lint/complexity/noForEach: <explanation>
          (model.aggregated_edges as ITopoNode[]).forEach(node => {
            node.id = random(10);
            const targetModel = nodes.find(item => item.id === node.target);
            const sourceModel = nodes.find(item => item.id === node.source);
            /** 聚合节点在nodes集合中第一层可能找不到直接取边中的信息制造entity */
            node.nodes = [
              {
                entity: {
                  is_anomaly: node.source_is_anomaly,
                  is_on_alert: node.source_is_on_alert,
                  entity_name: node.source_name,
                  entity_type: node.source_type,
                },
                ...sourceModel,
                events: node.events || [],
              },
              {
                entity: {
                  is_anomaly: node.target_is_anomaly,
                  is_on_alert: node.target_is_on_alert,
                  entity_name: node.target_name,
                  entity_type: node.target_type,
                },
                ...targetModel,
                events: node.events || [],
              },
            ];
          });

          // 点击非聚合边，直接打开边概览
          if (!model.aggregated) {
            interaction.handleViewServiceFromTopo({
              type: 'edge',
              // getModel() 返回 G6 配置，此处按业务边模型传入
              data: model as IEdge,
              sourceNode: null,
              isAggregatedEdge: false,
            });
          }
        } else {
          state.tooltipsModel.value = model as ITopoNode;
        }
        // getType() 返回 ITEM_TYPE，业务侧仅处理 node/edge
        state.tooltipsType.value = type as TooltipType;
        return state.tooltipCompRef.value.$el as HTMLDivElement;
      },
    });
    // 直接写入 shallowRef，供随后 new Graph({ plugins }) 读取
    g6TooltipRef.value = tooltipInstance;
  };

  // ---------------------------------------------------------------------------
  // Combo Label tooltip DOM 操作
  // ---------------------------------------------------------------------------

  /** 初始化 combo-label-tooltip DOM 元素 */
  const initComboLabelTooltip = () => {
    const comboLabelTooltip = document.getElementById('combo-label-tooltip');
    if (comboLabelTooltip) {
      comboLabelTooltip.innerHTML = ' ';
    }
  };

  /** Combo 鼠标进入 — 显示被截断的 label tooltip + 反馈根因文本 */
  const handleComboMouseEnter = (e: IG6GraphEvent) => {
    const g = graph();
    if (!g) return;
    const { item } = e;
    // Combo model 含业务自定义 originLabel，与 ITopoNode 交叉以便访问 entity.properties
    const model = item.getModel() as ITopoNode & { originLabel?: string };

    const fullLabel = model.originLabel;
    // 只有被截断的combo label才显示 Tooltip
    if (fullLabel && fullLabel !== model.label) {
      // 获取 Combo 的包围盒坐标
      const bbox = item.getBBox();
      // 转换画布坐标到页面坐标
      const canvasPoint = g.getCanvasByPoint(bbox.x, bbox.y);
      const containerRect = g.getContainer().getBoundingClientRect();
      const x = containerRect.left + canvasPoint.x;
      const y = containerRect.top + canvasPoint.y;

      const comboLabelTooltip = document.getElementById('combo-label-tooltip');
      if (comboLabelTooltip) {
        comboLabelTooltip.innerHTML = `
            <p><span class='combo-label-text'>名称：</span>${fullLabel as string}</p>
            <p><span class='combo-label-text'>类型：</span>${model.entity?.properties?.entity_category as string}</p>
          `;
        const tooltipHeight = comboLabelTooltip.offsetHeight;
        comboLabelTooltip.style.left = `${x}px`;
        comboLabelTooltip.style.top = `${y - tooltipHeight}px`;
        comboLabelTooltip.style.visibility = 'visible';
      }
    }

    // 移入展示"反馈新根因"文本
    if (!item.getModel().parentId) return;
    g.setItemState(item, 'hover', true);
    const feedbackImg = item.getContainer().find(ele => ele.get('name') === 'sub-combo-feedback-img');
    const feedbackText = item.getContainer().find(ele => ele.get('name') === 'sub-combo-feedback-text');
    if (feedbackImg) feedbackImg.attr('opacity', 1);
    if (feedbackText) feedbackText.attr('opacity', 1);
  };

  /** Combo 鼠标离开 — 隐藏 label tooltip + 反馈根因文本 */
  const handleComboMouseLeave = (e: IG6GraphEvent) => {
    const g = graph();
    if (!g) return;
    // 移出隐藏combo label的Tooltip
    const comboLabelTooltip = document.getElementById('combo-label-tooltip');
    if (comboLabelTooltip) {
      comboLabelTooltip.style.visibility = 'hidden';
    }

    // 移出隐藏"反馈新根因"文本
    const { item } = e;
    const model = item.getModel();
    if (!model.parentId) return;
    g.setItemState(item, 'hover', false);
    const container = item.getContainer();
    const feedbackImg = container.find(ele => ele.get('name') === 'sub-combo-feedback-img');
    const feedbackText = container.find(ele => ele.get('name') === 'sub-combo-feedback-text');

    if (feedbackImg) feedbackImg.attr('opacity', 0);
    if (feedbackText) feedbackText.attr('opacity', 0);
  };

  /** 隐藏 combo-label-tooltip（供 combo:click 使用） */
  const hideComboLabelTooltip = () => {
    const comboLabelTooltip = document.getElementById('combo-label-tooltip');
    if (comboLabelTooltip) {
      comboLabelTooltip.style.visibility = 'hidden';
    }
  };

  // ---------------------------------------------------------------------------
  // Node Detail tips DOM 操作
  // ---------------------------------------------------------------------------

  /** 初始化 node-detail-tips DOM 元素 */
  const initNodeInfoTooltip = () => {
    const nodeInfoTooltip = document.getElementById('node-detail-tips');
    if (nodeInfoTooltip) {
      nodeInfoTooltip.innerHTML = ' ';
    }
  };

  /** 节点鼠标进入 — 显示详情 tooltip + Combo 悬停联动 */
  const handleNodeMouseEnter = (e: IG6GraphEvent) => {
    const g = graph();
    if (!g) return;
    const { item } = e;
    g.setItemState(item, 'hover', true);

    /**
     * 处理组合节点Combo的悬停状态联动
     * 当节点属于某个Combo时，需要同时激活父Combo的悬停状态
     */
    const model = item.getModel() as ITopoNode;
    if (model.subComboId) {
      const combo = g.findById(model.subComboId);
      if (!combo) return;
      // const label = combo.getContainer().find(element => element.get('type') === 'text');
      // if (label) {
      //   label.attr('opacity', 1); // 悬停时显示标签
      // }
      combo && g.setItemState(combo, 'hover', true);
    }

    /**
     * 计算并显示节点信息工具提示
     * 1. 获取节点在画布中的位置
     * 2. 转换为页面绝对坐标
     * 3. 动态调整提示框位置避免超出视口
     */
    // 获取节点的包围盒
    const bbox = item.getBBox();
    // 将画布坐标转换为页面坐标
    // 获取节点左上角画布坐标
    const canvasPoint = g.getCanvasByPoint(bbox.x, bbox.y);
    // 获取画布容器视口信息
    const containerRect = g.getContainer().getBoundingClientRect();
    // 计算页面绝对X坐标、Y坐标
    const x = containerRect.left + canvasPoint.x;
    const y = containerRect.top + canvasPoint.y;

    // 生成工具提示内容
    const nodeInfoTooltip = document.getElementById('node-detail-tips');
    if (!nodeInfoTooltip) return;
    const isAggNode = model.aggregated_nodes?.length > 0;
    nodeInfoTooltip.className = `node-detail-tips${isAggNode ? ' node-detail-tips--aggregated' : ''}`;
    nodeInfoTooltip.innerHTML = interaction.handleNodeInfoTooltip(model);
    // 获取提示框渲染后尺寸
    const { offsetWidth, offsetHeight } = nodeInfoTooltip;

    // 判断节点是否靠近画布左侧/右侧边缘
    const isNearLeft = canvasPoint.x < offsetWidth / 2;
    const isNearRight = canvasPoint.x + offsetWidth / 2 >= containerRect.width;
    if (isNearLeft) {
      // 提示框左对齐节点左上角
      nodeInfoTooltip.style.left = `${x}px`;
    } else if (isNearRight) {
      // 提示框右对齐节点左上角
      nodeInfoTooltip.style.left = `${x - offsetWidth}px`;
    } else {
      // 提示框中心对齐节点顶部中心
      nodeInfoTooltip.style.left = `${x - offsetWidth / 2 + 40}px`;
    }
    // 提示框底部对齐节点顶部，预留5px间隙
    nodeInfoTooltip.style.top = `${y - offsetHeight - 5}px`;
    nodeInfoTooltip.style.visibility = 'visible';
  };

  /** 节点鼠标离开 — 隐藏详情 tooltip */
  const handleNodeMouseLeave = (e: IG6GraphEvent) => {
    const g = graph();
    if (!g) return;
    // 鼠标移出隐藏node详情Tooltip
    const nodeInfoTooltip = document.getElementById('node-detail-tips');
    if (nodeInfoTooltip) {
      nodeInfoTooltip.style.visibility = 'hidden';
    }

    const nodeItem = e.item;
    // 移出隐藏名称
    const model = nodeItem.getModel() as ITopoNode;
    if (model.subComboId) {
      const combo = g.findById(model.subComboId);
      if (!combo) return;
      // const label = combo.getContainer().find(element => element.get('type') === 'text');
      // if (label) {
      //   label.attr('opacity', 0);
      // }
    }
    g.setItemState(nodeItem, 'hover', false);
  };

  // ---------------------------------------------------------------------------
  // tooltipchange 事件处理
  // ---------------------------------------------------------------------------

  /** G6 tooltipchange 事件 — 点击 tips 时关闭右侧资源打开的 tips */
  const handleTooltipChange = (e: IG6GraphEvent) => {
    if (e.action === 'show' && state.showResourceGraph.value) {
      state.resourceGraphRef.value?.hideToolTips?.();
    }
  };

  // ---------------------------------------------------------------------------
  // Tooltip 隐藏辅助函数
  // ---------------------------------------------------------------------------

  /** 隐藏 G6 Tooltip 插件（供 handleResize / combo:click 使用） */
  const hideG6Tooltip = () => {
    g6TooltipRef.value?.hide?.();
  };

  return {
    registerCustomTooltip,
    // DOM tooltip 初始化
    initComboLabelTooltip,
    initNodeInfoTooltip,
    // Combo label tooltip handlers
    handleComboMouseEnter,
    handleComboMouseLeave,
    hideComboLabelTooltip,
    // Node detail tips handlers
    handleNodeMouseEnter,
    handleNodeMouseLeave,
    // tooltipchange handler
    handleTooltipChange,
    // Tooltip 隐藏辅助
    hideG6Tooltip,
  };
}
