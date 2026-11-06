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
 * @file G6 自定义元素统一注册入口
 * @description 在 Graph 创建前/后分别注册边、combo、行为与节点，并提供动画清理
 */

import { registerDragCanvasMove } from './behaviors/drag-canvas-move';
import { registerDragNodeWithFixedCombo } from './behaviors/drag-node-with-fixed-combo';
import { registerScrollCanvas } from './behaviors/scroll-canvas';
import { registerTopoCombo } from './register-combo';
import { clearEdgeIntervals, registerTopoEdge } from './topo-edge';
import { clearActiveAnimations, registerTopoNode } from './topo-node';

import type { CanvasByPointResult, ComboLabelPoint, TruncateByTextWidthFn } from '../types/g6';
import type { ICombo } from '@antv/g6';

export interface RegisterAllBeforeGraphOptions {
  /** 根 combo 拖拽后的 label 位置 (Ref) */
  rootComboMovePoint: { value: ComboLabelPoint };
  /** 获取 combo 的画布坐标范围的函数 */
  getCanvasByPoint: (combo: ICombo) => CanvasByPointResult;
  /** 移动 combo label 位置的函数 */
  moveComboLabelPosition: (point: { x?: number; y?: number }) => void;
  /** 将边置于顶层的回调（实现为全部边 toFront） */
  toFrontAnomalyEdge: () => void;
}

/**
 * 清理所有 G6 动画
 * 在组件卸载时调用
 */
export function clearAllG6Animations(): void {
  clearActiveAnimations();
  clearEdgeIntervals();
}

/**
 * 注册所有需要在 Graph 创建之后完成的自定义 G6 元素
 * 包括：节点（需要 canvas context 用于文本截断）
 */
export function registerAllAfterGraph(truncateByTextWidth: TruncateByTextWidthFn): void {
  registerTopoNode(truncateByTextWidth);
}

/**
 * 注册所有需要在 Graph 创建之前完成的自定义 G6 元素
 * 包括：边、combo、行为（拖拽节点、画布拖拽、画布滚动）
 */
export function registerAllBeforeGraph(options: RegisterAllBeforeGraphOptions): void {
  const { toFrontAnomalyEdge, rootComboMovePoint, moveComboLabelPosition, getCanvasByPoint } = options;

  // 注册自定义边
  registerTopoEdge();

  // 注册自定义 combo
  registerTopoCombo();

  // 注册自定义行为 - 节点拖拽（防止拖出 combo）
  registerDragNodeWithFixedCombo(toFrontAnomalyEdge);

  // 注册自定义行为 - 画布拖拽
  registerDragCanvasMove({
    rootComboMovePoint,
    moveComboLabelPosition,
    getCanvasByPoint,
  });

  // 注册自定义行为 - 画布滚动
  registerScrollCanvas(getCanvasByPoint);
}
