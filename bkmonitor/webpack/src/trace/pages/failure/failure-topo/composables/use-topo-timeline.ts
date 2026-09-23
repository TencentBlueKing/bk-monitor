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
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN THE EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/**
 * @file 拓扑图时间轴播放 Composable
 * @description 负责管理 FailureTopo 组件的时间轴播放逻辑
 *
 * ## 职责
 * - 渲染时间轴帧数据（handleRenderTimeline）
 * - 播放队列处理（processPlayQueue）
 * - 播放开始/暂停控制（handlePlay）
 * - 重置播放状态（handleResetPlay）
 * - 手动帧切换（handleTimelineChange）
 * - 模块内部播放状态（playTime/playQueue/isProcessingQueue/processNext）
 *
 * ## 依赖注入
 * - state: 从 useTopoState 接收响应式状态子集
 * - data: 从 useTopoData 接收数据函数子集
 * - graphAccess: Graph 实例访问器
 * - emit: Vue 组件 emit 函数
 */

import type { Ref } from 'vue';

import isEqual from 'lodash/isEqual';
import { random } from 'monitor-common/utils/utils.js';

import ServiceCombo from '../graph/service-combo';

import type { GraphAccess, TopoEmitFn } from '../types/composable';
import type { PlayOption, TopoRawDataCache } from '../types/g6';
import type { IEdge, ITopoNode } from '../types/topo';
import type { INode } from '@antv/g6';

// ============================================================================
// 类型定义
// ============================================================================

/** useTopoTimeline 需要从 useTopoData 接收的数据函数子集 */
export interface TopoTimelineData {
  /** 拓扑原始数据缓存（含 diff / complete） */
  topoRawDataCache: Ref<TopoRawDataCache>;
  clearRefreshTimeout: () => void;
  /** 在边列表中按 source/target 查找匹配边（与 use-topo-data.findEdges 对齐） */
  findEdges: (edges: IEdge[], target: IEdge | Pick<IEdge, 'source' | 'target'>) => IEdge | undefined;
  handleChangeRefleshTime: (time: number) => void;
}

/** useTopoTimeline 需要从 useTopoState 接收的状态子集 */
export interface TopoTimelineState {
  isPlay: Ref<boolean>;
  refreshTime: Ref<number>;
  resizeCacheCallback: Ref<(() => void) | null>;
  resourceNodeId: Ref<string>;
  showResourceGraph: Ref<boolean>;
  showServiceOverview: Ref<boolean>;
  timelinePosition: Ref<number>;
}

// ============================================================================
// Composable
// ============================================================================

export type UseTopoTimelineReturn = ReturnType<typeof useTopoTimeline>;

export function useTopoTimeline(
  state: TopoTimelineState,
  data: TopoTimelineData,
  graphAccess: GraphAccess,
  emit: TopoEmitFn
) {
  // ---------------------------------------------------------------------------
  // 模块内部播放状态（不在 use-topo-state 中声明，避免污染全局状态）
  // ---------------------------------------------------------------------------

  /** 边的动画定时器 */
  let playTime: null | ReturnType<typeof setTimeout> = null;
  /** 播放队列：存储需要播放的帧索引 */
  let playQueue: number[] = [];
  /** 队列处理标志：避免重复处理队列 */
  let isProcessingQueue = false;
  /** 处理播放队列中的下一帧 */
  let processNext: (() => void) | null = null;

  // ---------------------------------------------------------------------------
  // 渲染时间轴帧数据
  // ---------------------------------------------------------------------------

  /** 渲染时间轴帧数据，播放某一帧的图（播放队列 + 手动切换帧都调用此函数） */
  const handleRenderTimeline = () => {
    /** 播放时关闭查看资源态 */
    state.showResourceGraph.value = false;
    /** 播放时关闭查看节点/边概览态 */
    state.showServiceOverview.value = false;
    /** 播放时清除自动刷新 */
    data.clearRefreshTimeout();
    /** 对比node是否已经展示，已经展示还存在diff中说明只是状态变更以及对比每个展示的node都需要判断边关系的node是在展示状态 */
    const { showNodes, content, showEdges, showSubCombos } =
      data.topoRawDataCache.value.diff[state.timelinePosition.value];
    const currNodes = data.topoRawDataCache.value.diff[state.timelinePosition.value].content.nodes;
    const currEdges = data.topoRawDataCache.value.diff[state.timelinePosition.value].content.edges;
    const randomStr = random(8);
    let next = false;

    const g = graphAccess.getGraph();
    if (!g) return;

    // 处理边的更新，与 handleTimelineChange 保持一致
    const edges = g.getEdges();
    const updateEdges = currEdges;
    // biome-ignore lint/complexity/noForEach: <explanation>
    edges.forEach(edge => {
      // getModel() 返回 G6 配置，findEdges 按业务边模型匹配 source/target
      const edgeModel = edge.getModel() as IEdge;
      const targetEdge = data.findEdges(updateEdges, edgeModel);
      if (targetEdge) {
        g.updateItem(edge, { ...edge, ...targetEdge });
      } else {
        // 如果当前帧没有该边，尝试从 showEdges 或 complete.edges 中恢复
        const currEdges =
          data.findEdges(showEdges, edgeModel) || data.findEdges(data.topoRawDataCache.value.complete.edges, edgeModel);
        if (currEdges && edgeModel && !isEqual(currEdges, edgeModel)) {
          g.updateItem(edge, { ...edge, ...currEdges });
        }
      }
    });

    // 处理节点的更新，与 handleTimelineChange 保持一致
    // 遍历所有 complete.nodes，确保所有节点状态都正确
    // biome-ignore lint/complexity/noForEach: <explanation>
    data.topoRawDataCache.value.complete.nodes.forEach(({ id }) => {
      // 查找节点：与 handleTimelineChange 的逻辑保持一致
      // showNode: 在 showNodes 和 currNodes 的合并数组中查找（用于获取节点数据）
      const showNode = [...showNodes, ...currNodes].reverse().find(item => item.id === id);
      const deleteNodeIds = showNodes.filter(item => item.is_deleted).map(item => item.id);
      const diffNode = currNodes.find(item => item.id === id);
      // nodeInShowNodes: 单独在 showNodes 中查找，用于判断节点是否之前存在
      const nodeInShowNodes = showNodes.find(item => item.id === id);
      // diffData: 节点在 showNodes 中但不在 currNodes 中（之前存在，当前帧没有变化）
      const diffData = !diffNode && nodeInShowNodes;
      const updateNode = diffData ? showNode : diffNode;

      if ((!nodeInShowNodes && !diffNode) || deleteNodeIds.includes(id)) {
        // 节点应该隐藏：既不在 showNodes 中，也不在 currNodes 中，或者被标记为删除
        const node = g.findById(id);
        node && g.hideItem(node);
      } else if (diffNode || diffData) {
        // 节点应该显示：在 currNodes 中（当前帧有变化）或在 showNodes 中（之前存在）
        const node = g.findById(updateNode.id);
        if (node) {
          const model = node?.getModel?.();
          // 判断是否为新节点：在 currNodes 中但不在 showNodes 中
          const isNewNode = !nodeInShowNodes && diffNode;

          if (isNewNode) {
            // 新节点：需要设置动画
            next = true;
            g.updateItem(node, {
              ...node,
              ...updateNode,
              comboId: model.comboId,
              subComboId: model.subComboId,
            });
            g.setItemState(node, 'show-animate', randomStr);
            const edges = (node as INode).getEdges();
            // biome-ignore lint/complexity/noForEach: <explanation>
            edges.forEach(edge => {
              const edgeModel = edge.getModel();
              const edgeNode = [...showNodes, ...currNodes].find(node => {
                return edgeModel.source === updateNode.id ? node.id === edgeModel.target : node.id === edgeModel.source;
              });
              edgeNode && g.setItemState(edge, 'show-animate', randomStr);
            });
          } else {
            // 已存在的节点：需要更新状态
            // 与 handleTimelineChange 的逻辑保持一致
            if (diffNode?.is_deleted) {
              // 节点被标记为删除
              node?.hide?.();
              (node as INode)?.getEdges()?.forEach(edge => edge?.hide());
            } else {
              // 节点应该显示
              // 如果节点之前是隐藏状态，先显示
              if (model.is_deleted) {
                node?.show?.();
                (node as INode)?.getEdges()?.forEach(edge => edge?.show());
              }
              // 更新节点数据
              g.showItem(node);
              g.updateItem(node, {
                ...updateNode,
                is_deleted: false,
                comboId: model.comboId,
                subComboId: model.subComboId,
              });
            }
          }
        }
      }
    });

    // 处理 combo 的更新，与 handleTimelineChange 保持一致
    const combos = g.getCombos().filter(combo => combo.getModel().parentId);
    // biome-ignore lint/complexity/noForEach: <explanation>
    combos.forEach(combo => {
      const { entity, id, comboId } = combo.getModel() as ITopoNode;
      // 使用 showSubCombos 和 content.sub_combos，与 handleTimelineChange 保持一致
      const updateCombo = [...showSubCombos, ...content.sub_combos]
        .reverse()
        .find(item => item.id === entity.entity_id);
      const nodes = data.topoRawDataCache.value.complete.nodes.filter(node => node.subComboId === id);
      const showNodes = nodes.filter(({ id }) => {
        const node = g.findById(id);
        return node?._cfg.visible;
      });
      updateCombo &&
        g.updateItem(combo, {
          ...combo,
          id,
          comboId,
          is_feedback_root: updateCombo.is_feedback_root,
          entity: {
            ...updateCombo.entity,
          },
          alert_all_recorved: updateCombo.alert_all_recorved,
          is_on_alert: updateCombo.is_on_alert,
        });
      updateCombo && ServiceCombo.labelChange(combo);

      g[showNodes.length > 0 ? 'showItem' : 'hideItem'](combo);
    });
    return currNodes.length === 0 || !next;
  };

  // ---------------------------------------------------------------------------
  // 重置播放
  // ---------------------------------------------------------------------------

  /** 判断资源图或者节点/边概览是否为开启状态 是的话关闭状态并等待重新布局 */
  const handleResetPlay = (playOption: PlayOption) => {
    if (state.showResourceGraph.value || state.showServiceOverview.value) {
      state.showResourceGraph.value = false;
      state.showServiceOverview.value = false;
      state.resizeCacheCallback.value = () => {
        setTimeout(() => handlePlay(playOption), 500);
        state.resizeCacheCallback.value = null;
      };
      return;
    }
    handlePlay(playOption);
  };

  // ---------------------------------------------------------------------------
  // 播放队列处理
  // ---------------------------------------------------------------------------

  /** 处理播放队列 */
  const processPlayQueue = () => {
    if (isProcessingQueue || playQueue.length === 0) {
      return;
    }

    isProcessingQueue = true;
    processNext = () => {
      // 检查播放状态和队列状态
      if (!state.isPlay.value) {
        // 如果暂停了，停止处理但保留队列状态
        isProcessingQueue = false;
        return;
      }

      if (playQueue.length === 0) {
        // 队列处理完成
        isProcessingQueue = false;
        state.isPlay.value = false;
        emit('playing', false);
        data.handleChangeRefleshTime(state.refreshTime.value);
        return;
      }

      // 检查队列中的第一个帧是否与当前位置一致（避免重复处理）
      const nextIndex = playQueue[0];
      if (nextIndex === state.timelinePosition.value && playQueue.length > 1) {
        // 如果队列第一个帧与当前位置一致，且还有后续帧，跳过当前帧
        playQueue.shift();
        processNext();
        return;
      }

      const currentIndex = playQueue.shift();
      if (currentIndex === undefined) {
        isProcessingQueue = false;
        return;
      }

      const len = data.topoRawDataCache.value.diff.length;
      if (currentIndex >= len) {
        state.timelinePosition.value = data.topoRawDataCache.value.diff.length - 1;
        state.isPlay.value = false;
        emit('playing', false);
        data.handleChangeRefleshTime(state.refreshTime.value);
        isProcessingQueue = false;
        return;
      }

      state.timelinePosition.value = currentIndex;
      emit('playing', true, currentIndex);

      // 直接渲染当前帧，不再需要预先计算 hideNodes
      handleRenderTimeline();

      // 延迟处理下一帧，确保DOM渲染完成
      clearTimeout(playTime!);
      playTime = setTimeout(() => {
        if (state.isPlay.value && playQueue.length > 0) {
          // 继续处理队列中的下一帧
          processNext();
        } else {
          // 队列处理完成或已暂停
          isProcessingQueue = false;
          if (state.isPlay.value && playQueue.length === 0) {
            // 队列处理完成
            state.isPlay.value = false;
            emit('playing', false);
            data.handleChangeRefleshTime(state.refreshTime.value);
          }
        }
      }, 600); // 没有动画时，短暂延迟即可
    };

    processNext();
  };

  // ---------------------------------------------------------------------------
  // 播放控制
  // ---------------------------------------------------------------------------

  /** 播放 */
  const handlePlay = (playOption: PlayOption) => {
    const { value } = playOption;
    // 注意：isStart 参数在队列版本中不再使用，队列处理函数会根据 currentIndex 自动判断

    if ('timeline' in playOption) {
      // 重置时清空队列，不提前设置 timelinePosition，
      // 让 processPlayQueue 从第0帧开始正常播放（避免跳帧逻辑跳过首帧）
      playQueue = [];
      isProcessingQueue = false;
    }

    state.isPlay.value = value;

    if (value) {
      // 开始播放
      const len = data.topoRawDataCache.value.diff.length;
      // 判断是否需要从第0帧重新开始播放
      const isStartFromBeginning = 'timeline' in playOption;

      // 如果队列为空，或者队列第一个帧不等于当前位置，需要重新构建队列
      // 这包括以下情况：
      // 1. 首次播放（队列为空）
      // 2. 暂停后恢复播放，但用户手动切换了帧（队列第一个帧 != 当前位置）
      // 3. 播放时用户点击了其他帧（已在 handleTimelineChange 中处理，但这里作为兜底）
      if (playQueue.length === 0 || (playQueue.length > 0 && playQueue[0] !== state.timelinePosition.value)) {
        playQueue = [];
        const startIndex = isStartFromBeginning ? 0 : state.timelinePosition.value;
        for (let i = startIndex; i < len; i++) {
          playQueue.push(i);
        }
      }

      // 如果队列为空，说明已经播放完毕
      if (playQueue.length === 0) {
        state.timelinePosition.value = data.topoRawDataCache.value.diff.length - 1;
        state.isPlay.value = false;
        emit('playing', false);
        data.handleChangeRefleshTime(state.refreshTime.value);
        return;
      }

      // 开始处理队列
      // 如果之前正在处理但被暂停了，需要重置标志并重新开始
      if (isProcessingQueue) {
        isProcessingQueue = false;
      }
      processPlayQueue();
    } else {
      // 暂停播放：不清空队列，保留队列状态以便恢复播放
      // 清除定时器，停止队列处理
      clearTimeout(playTime!);
      // 重置处理标志，确保恢复播放时可以重新开始
      isProcessingQueue = false;
      // 注意：processNext 函数内部会检查 isPlay.value，如果为 false 会自动停止
      // 但我们需要重置 isProcessingQueue，以便恢复播放时可以重新调用 processPlayQueue
    }
  };

  // ---------------------------------------------------------------------------
  // 帧切换
  // ---------------------------------------------------------------------------

  /** 点击展示某一帧的图
   *  @param value    目标帧索引
   *  @param init     是否为初始化调用（跳过去重检查，不改变播放队列）
   *  @param keepSidePanel 是否保留侧滑面板（resize 场景下不应关闭侧滑）
   */
  const handleTimelineChange = (value: number, init = false, keepSidePanel = false) => {
    if (!init && value === state.timelinePosition.value) return;

    const g = graphAccess.getGraph();
    if (!g) return;

    // 如果正在播放时切换帧，需要重新构建队列并立即渲染当前帧
    if (state.isPlay.value && !init) {
      // 清空当前队列，重新构建从新位置开始的队列
      playQueue = [];
      clearTimeout(playTime!);
      isProcessingQueue = false;
      const len = data.topoRawDataCache.value.diff.length;
      // 构建从新位置的下一帧到末尾的播放队列
      // 当前帧会立即渲染，所以队列从下一帧开始
      for (let i = value + 1; i < len; i++) {
        playQueue.push(i);
      }
      // 立即渲染当前帧
      state.timelinePosition.value = value;
      if (data.topoRawDataCache.value.diff[value]) {
        handleRenderTimeline();
      }
      // 如果队列为空，停止播放
      if (playQueue.length === 0) {
        state.isPlay.value = false;
        emit('playing', false);
        data.handleChangeRefleshTime(state.refreshTime.value);
      } else {
        // 继续处理队列
        processPlayQueue();
      }
      // 直接返回，避免执行下面的非播放状态下的渲染逻辑
      return;
    }

    state.timelinePosition.value = value;
    if (!state.isPlay.value && data.topoRawDataCache.value.diff[value]) {
      /** 切换帧时关闭侧滑面板（除非明确要求保留，如 resize 场景） */
      if (!keepSidePanel) {
        state.showResourceGraph.value = false;
        state.showServiceOverview.value = false;
      }
      /** 直接切换到对应帧时，直接隐藏掉未出现的帧，并更新当前帧每个node的节点数据 */
      /** 注意：需要支持从后往前切换的场景，确保所有节点都按照目标帧的状态来处理 */
      const { showNodes, content, showEdges, showSubCombos } = data.topoRawDataCache.value.diff[value];
      const updateEdges = content.edges;
      // biome-ignore lint/complexity/noForEach: <explanation>
      data.topoRawDataCache.value.complete.nodes.forEach(({ id }) => {
        // 查找节点：与 handleRenderTimeline 的逻辑保持一致
        // showNode: 在 showNodes 和 content.nodes 的合并数组中查找（用于获取节点数据）
        const showNode = [...showNodes, ...content.nodes].reverse().find(item => item.id === id);
        const deleteNodeIds = showNodes.filter(item => item.is_deleted).map(item => item.id);
        const diffNode = content.nodes.find(item => item.id === id);
        // nodeInShowNodes: 单独在 showNodes 中查找，用于判断节点是否之前存在
        const nodeInShowNodes = showNodes.find(item => item.id === id);
        // diffData: 节点在 showNodes 中但不在 content.nodes 中（之前存在，当前帧没有变化）
        const diffData = !diffNode && nodeInShowNodes;
        const updateNode = diffData ? showNode : diffNode;

        if ((!nodeInShowNodes && !diffNode) || deleteNodeIds.includes(id)) {
          // 节点应该隐藏：既不在 showNodes 中，也不在 content.nodes 中，或者被标记为删除
          const node = g.findById(id);
          node && g.hideItem(node);
        } else if (diffNode || diffData) {
          // 节点应该显示：在 content.nodes 中（当前帧有变化）或在 showNodes 中（之前存在）
          const node = g.findById(updateNode.id);
          if (node) {
            const model = node?.getModel?.();
            // 如果节点之前是隐藏状态，先显示
            if (model.is_deleted) {
              node?.show?.();
              (node as INode)?.getEdges()?.forEach(edge => edge?.show());
            }
            // 更新节点数据
            g.showItem(node);
            g.updateItem(node, { ...updateNode, comboId: model.comboId, subComboId: model.subComboId });
          }
        }
      });
      const edges = g.getEdges();
      // biome-ignore lint/complexity/noForEach: <explanation>
      edges.forEach(edge => {
        // getModel() 返回 G6 配置，findEdges 按业务边模型匹配 source/target
        const edgeModel = edge.getModel() as IEdge;

        const targetEdge = data.findEdges(updateEdges, edgeModel);
        if (targetEdge) {
          g.updateItem(edge, { ...edge, ...targetEdge });
        } else {
          const currEdges =
            data.findEdges(showEdges, edgeModel) ||
            data.findEdges(data.topoRawDataCache.value.complete.edges, edgeModel);
          if (currEdges && edgeModel && !isEqual(currEdges, edgeModel)) {
            g.updateItem(edge, { ...edge, ...currEdges });
          }
        }
      });
      /** 子combo需要根据节点时候有展示来决定 */
      const combos = g.getCombos().filter(combo => combo.getModel().parentId);
      // biome-ignore lint/complexity/noForEach: <explanation>
      combos.forEach(combo => {
        const { id, comboId, entity } = combo.getModel() as ITopoNode;
        const updateCombo = [...showSubCombos, ...content.sub_combos]
          .reverse()
          .find(item => item.id === entity.entity_id);
        const nodes = data.topoRawDataCache.value.complete.nodes.filter(node => node.subComboId === id);
        const showNodes = nodes.filter(({ id }) => {
          const node = g.findById(id);
          return node?._cfg.visible;
        });
        updateCombo &&
          g.updateItem(combo, {
            ...combo,
            id,
            comboId,
            is_feedback_root: updateCombo.is_feedback_root,
            entity: {
              ...updateCombo.entity,
            },
            alert_all_recorved: updateCombo.alert_all_recorved,
            is_on_alert: updateCombo.is_on_alert,
          });
        updateCombo && ServiceCombo.labelChange(combo);
        g[showNodes.length > 0 ? 'showItem' : 'hideItem'](combo);
      });
    }
  };

  // ---------------------------------------------------------------------------
  // afteritemstatechange 事件回调
  // ---------------------------------------------------------------------------

  /** 供 initGraph 的 afteritemstatechange 事件绑定的回调 */
  const onAnimationStateChange = () => {
    // 如果正在播放且正在处理队列，动画完成后继续处理队列
    if (state.isPlay.value && isProcessingQueue && processNext) {
      clearTimeout(playTime!);
      playTime = setTimeout(() => {
        // 动画完成后继续处理队列中的下一帧
        if (state.isPlay.value && playQueue.length > 0 && processNext) {
          processNext();
        }
      }, 1000);
    }
  };

  // ---------------------------------------------------------------------------
  // 清理函数
  // ---------------------------------------------------------------------------

  /** 组件卸载时清理播放状态 */
  const cleanupTimeline = () => {
    clearTimeout(playTime!);
    // 清空播放队列
    playQueue = [];
    isProcessingQueue = false;
  };

  return {
    handleResetPlay,
    handlePlay,
    handleTimelineChange,
    onAnimationStateChange,
    cleanupTimeline,
  };
}
