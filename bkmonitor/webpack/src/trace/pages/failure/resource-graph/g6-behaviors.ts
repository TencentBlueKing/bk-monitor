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
 * resource-graph/g6-behaviors.ts — 资源拓扑图专属的 G6 行为注册模块
 *
 * 提供：
 * 1. `registerDragCanvasMoveBase` — 画布拖拽行为（dragMargin=0，无 combo label 联动）
 * 2. `registerScrollCanvasBase` — 画布滚轮滚动行为（dragMargin=0，使用 getComboCanvasBounds）
 *
 * 命名约定：
 * - 行为名带 `-base` 后缀：`drag-canvas-move-base` / `custom-scroll-canvas-base`
 * - failure-topo 有独立的扩展版行为（drag-canvas-move / custom-scroll-canvas），差异较大，不适合复用
 */

import { registerBehavior } from '@antv/g6';

import { getComboCanvasBounds } from '../failure-topo/graph/get-canvas-by-point';

import type { Graph } from '@antv/g6';

// ============================================================================
// 选项类型
// ============================================================================

export interface DragCanvasMoveBaseOptions {
  /** 画布离上下左右的留白边距（像素）。默认 30。failure-topo 用 100，resource-graph 用 0 */
  dragMargin?: number;
}

export interface ScrollCanvasBaseOptions {
  /** 画布离上下左右的留白边距（像素）。默认 30。failure-topo 用 100，resource-graph 用 0 */
  dragMargin?: number;
}

// ============================================================================
// 行为上下文类型（this 类型）
// ============================================================================

/** 画布拖拽行为上下文（this 类型） */
interface DragCanvasBaseContext {
  dragging: boolean;
  graph: Graph;
  comboRect: {
    bottomCombo?: any;
    el?: HTMLElement;
    height?: number;
    topCombo?: any;
    width?: number;
    xCombo?: any;
  };
}

/** 画布滚轮滚动行为上下文（this 类型） */
interface ScrollCanvasBaseContext {
  graph: Graph;
}

// ============================================================================
// drag-canvas-move-base — 画布拖拽
// ============================================================================

/**
 * 注册画布拖拽行为 — 资源拓扑图版
 *
 * 注册的行为名为 `'drag-canvas-move-base'`。
 *
 * 功能：
 * - 仅允许根 combo（无 parentId）拖拽画布，节点/边不响应
 * - dragMargin 控制画布留白边距
 */
export function registerDragCanvasMoveBase(options: DragCanvasMoveBaseOptions = {}): void {
  const GRAPH_DRAG_MARGIN = options.dragMargin ?? 30;

  registerBehavior('drag-canvas-move-base', {
    getEvents() {
      return {
        mouseenter: 'onMouseEnter',
        mousedown: 'onMouseDown',
        mousemove: 'onMouseMove',
        mouseup: 'onMouseUp',
        mouseleave: 'onMouseLeave',
      };
    },
    onMouseEnter(this: DragCanvasBaseContext, e: any) {
      const itemType = e?.item?.getType();
      /** 子combo/节点/和边不响应拖动 */
      if (e.item && ['node', 'edge'].includes(itemType)) {
        return;
      }
      const canvas = this.graph.get('canvas');
      const el = canvas.get('el'); // 获取到画布实际的 DOM 元素
      this.comboRect = { el };
      (this.comboRect as any).el.style.cursor = 'grab';
    },
    onMouseDown(this: DragCanvasBaseContext, e: any) {
      const itemType = e?.item?.getType();
      if (e.item && ['node', 'edge'].includes(itemType)) {
        return;
      }
      e.item &&
        this.graph.updateItem(e.item, {
          style: { cursor: 'grabbing' },
        });
      (this as any).comboRect.el.style.cursor = 'grabbing';
      this.dragging = true;

      const combos = this.graph.getCombos().filter((combo: any) => !combo.getModel().parentId);
      let xCombo = combos[0];
      let xComboWidth = 0;
      combos.forEach((combo: any) => {
        const { width } = combo.getBBox();
        if (width > xComboWidth) {
          xCombo = combo;
          xComboWidth = width;
        }
      });
      this.comboRect = {
        ...((this as any).comboRect || {}),
        xCombo,
        topCombo: combos[0],
        bottomCombo: combos[combos.length - 1],
        width: this.graph.getWidth(),
        height: this.graph.getHeight() + 20,
      };
    },
    onMouseMove(this: DragCanvasBaseContext, e: any) {
      if (this.dragging) {
        const comboRect = this.comboRect;
        let { movementX, movementY } = e.originalEvent;
        // 大于零向上拖动
        if (movementY < 0) {
          const { bottomRight } = getComboCanvasBounds(comboRect.bottomCombo!, this.graph);
          if (bottomRight.y + GRAPH_DRAG_MARGIN < comboRect.height!) {
            movementY = 0;
          }
        } else {
          const { topLeft } = getComboCanvasBounds(comboRect.topCombo!, this.graph);
          if (topLeft.y - GRAPH_DRAG_MARGIN > 0) {
            movementY = 0;
          }
        }

        const { topLeft, bottomRight } = getComboCanvasBounds(comboRect.xCombo!, this.graph);
        /** 大于0向左拖动 */
        if (movementX < 0) {
          if (bottomRight.x + GRAPH_DRAG_MARGIN < comboRect.width!) {
            movementX = 0;
          }
        } else {
          if (topLeft.x - GRAPH_DRAG_MARGIN > 0) {
            movementX = 0;
          }
        }

        this.graph.translate(movementX, movementY);
      }
    },
    onMouseUp(this: DragCanvasBaseContext, e: any) {
      this.dragging = false;
      e.item?.getType() === 'combo' &&
        this.graph.updateItem(e.item, {
          style: { cursor: 'grab' },
        });
      (this as any).comboRect.el.style.cursor = 'grab';
    },
    onMouseLeave(this: DragCanvasBaseContext, e: any) {
      if (this.dragging) {
        e.item?.getType() === 'combo' &&
          this.graph.updateItem(e.item, {
            style: { cursor: 'grab' },
          });
        (this as any).comboRect.el.style.cursor = 'grab';
        this.dragging = false;
      }
    },
  });
}

// ============================================================================
// custom-scroll-canvas-base — 画布滚轮滚动
// ============================================================================

/**
 * 注册画布滚轮滚动行为 — 资源拓扑图版
 *
 * 注册的行为名为 `'custom-scroll-canvas-base'`。
 *
 * 功能：
 * - dragMargin 控制画布留白边距
 * - 过滤根 combo 用于边界约束
 *
 * ⚠️ onWheel 必须用正则函数（非箭头函数），否则 G6 无法绑定 this.graph，
 *    而 e.graph 在 wheel 事件中为 undefined（原 shared 版的 bug 根因）。
 */
export function registerScrollCanvasBase(options: ScrollCanvasBaseOptions = {}): void {
  const GRAPH_DRAG_MARGIN = options.dragMargin ?? 30;

  registerBehavior('custom-scroll-canvas-base', {
    getEvents() {
      return {
        wheel: 'onWheel',
      };
    },
    onWheel(this: ScrollCanvasBaseContext, e: any) {
      e.preventDefault();
      e.stopPropagation();
      const { deltaX, deltaY } = e;
      // 设置滚动灵敏度
      const sensitivity = 2;
      let dx = -deltaX * sensitivity;
      let dy = -deltaY * sensitivity;

      // 获取所有根combos的布局信息
      const combos = this.graph.getCombos().filter((combo: any) => !combo.getModel().parentId);
      const width = this.graph.getWidth();
      const height = this.graph.getHeight() + 20;

      if (Math.abs(deltaY) > Math.abs(deltaX)) {
        // vertical scroll
        if (deltaY > 0) {
          const bottomCombo = combos[combos.length - 1];
          const { bottomRight } = getComboCanvasBounds(bottomCombo, this.graph);
          if (bottomRight.y + GRAPH_DRAG_MARGIN < height) {
            dy = 0;
          }
        } else {
          const topCombo = combos[0];
          const { topLeft } = getComboCanvasBounds(topCombo, this.graph);
          if (topLeft.y - GRAPH_DRAG_MARGIN > 0) {
            dy = 0;
          }
        }
        dx = 0;
      } else {
        const topCombo = combos[0];
        const { topLeft, bottomRight } = getComboCanvasBounds(topCombo, this.graph);
        /** 大于0判断右侧 否则判断左侧 */
        if (deltaX > 0) {
          if (bottomRight.x + GRAPH_DRAG_MARGIN < width) {
            dx = 0;
          }
        } else {
          if (topLeft.x - GRAPH_DRAG_MARGIN > 0) {
            dx = 0;
          }
        }
        dy = 0;
      }
      this.graph.translate(dx, dy);
    },
  });
}
