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

/**
 * @file 画布拖拽行为
 * @description 注册 drag-canvas-move：根 combo 区域拖动画布，含边界留白与 combo label 位置同步
 */
import { type ICombo, type IG6GraphEvent, registerBehavior } from '@antv/g6';

import type {
  CanvasByPointResult,
  ComboLabelPoint,
  DragCanvasBehaviorContext,
  DragCanvasComboRect,
} from '../../types/g6';

/** 增加画布离画布上下左右的留白区域 */
const GRAPH_DRAG_MARGIN = 100;

export interface DragCanvasMoveOptions {
  /** 根 combo 拖拽后的 label 位置 (Ref) */
  rootComboMovePoint: { value: ComboLabelPoint };
  /** 获取 combo 的画布坐标范围 */
  getCanvasByPoint: (combo: ICombo) => CanvasByPointResult;
  /** 移动 combo label 位置的函数 */
  moveComboLabelPosition: (point: { x?: number; y?: number }) => void;
}

/**
 * 注册自定义拖拽行为
 */
export function registerDragCanvasMove(options: DragCanvasMoveOptions): void {
  const { rootComboMovePoint, moveComboLabelPosition, getCanvasByPoint } = options;

  registerBehavior('drag-canvas-move', {
    getEvents() {
      return {
        mouseenter: 'onMouseEnter',
        mousedown: 'onMouseDown',
        mousemove: 'onMouseMove',
        mouseup: 'onMouseUp',
        mouseleave: 'onMouseLeave',
      };
    },
    onMouseEnter(this: DragCanvasBehaviorContext, e: IG6GraphEvent) {
      const itemType = e?.item?.getType();
      const model = e?.item?.getModel();
      /** 子combo/节点/和边不响应拖动 */
      if (['node', 'edge'].includes(itemType) || (itemType === 'combo' && model?.parentId)) {
        return;
      }
      const canvas = this.graph.get('canvas');
      // 获取到画布实际的 DOM 元素
      const el = canvas.get('el');
      this.comboRect = { el };
      this.comboRect.el.style.cursor = 'grab';
    },
    onMouseDown(this: DragCanvasBehaviorContext, e: IG6GraphEvent) {
      const itemType = e?.item?.getType();
      const model = e?.item?.getModel();
      if (['node', 'edge'].includes(itemType) || (itemType === 'combo' && model?.parentId)) {
        return;
      }
      e.item &&
        this.graph.updateItem(e.item, {
          style: { cursor: 'grabbing' },
        });
      this.comboRect.el.style.cursor = 'grabbing';
      this.dragging = true;

      const combos = this.graph.getCombos().filter((combo: ICombo) => !combo.getModel().parentId);
      let xCombo = combos[0];
      let xComboWidth = 0;
      combos.forEach((combo: ICombo) => {
        const { width } = combo.getBBox();
        if (width > xComboWidth) {
          xCombo = combo;
          xComboWidth = width;
        }
        if (rootComboMovePoint.value.x) {
          (combo.getContainer() as any).shapeMap['text-shape'].attr({
            x: rootComboMovePoint.value.x,
          });
        }
      });
      const comboModel = combos[0].getModel() as { height: number; width: number };
      this.comboRect = {
        ...this.comboRect,
        labelPoint: {
          x: -(comboModel.width / 2 + 10),
          y: -(comboModel.height / 2 + 30),
        },
        xCombo,
        topCombo: combos[0],
        bottomCombo: combos[combos.length - 1],
        width: this.graph.getWidth(),
        height: this.graph.getHeight() + 20,
      };
    },
    onMouseMove(this: DragCanvasBehaviorContext, e: IG6GraphEvent) {
      if (this.dragging) {
        const comboRect = this.comboRect as DragCanvasComboRect & {
          bottomCombo: ICombo;
          height: number;
          labelPoint: { x: number; y: number };
          topCombo: ICombo;
          width: number;
          xCombo: ICombo;
        };
        // originalEvent 运行时为 MouseEvent，G6 类型标为 Event
        let { movementX, movementY } = e.originalEvent as MouseEvent;
        // 大于零向上拖动
        if (movementY < 0) {
          const { bottomRight } = getCanvasByPoint(comboRect.bottomCombo);
          if (bottomRight.y + GRAPH_DRAG_MARGIN < comboRect.height) {
            movementY = 0;
          }
        } else {
          const { topLeft } = getCanvasByPoint(comboRect.topCombo);
          if (topLeft.y - GRAPH_DRAG_MARGIN > 0) {
            movementY = 0;
          }
        }

        const { topLeft, bottomRight } = getCanvasByPoint(comboRect.xCombo);
        /** 大于0向左拖动 */
        if (movementX < 0) {
          if (bottomRight.x + GRAPH_DRAG_MARGIN < comboRect.width) {
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
    onMouseUp(this: DragCanvasBehaviorContext, e: IG6GraphEvent) {
      if (!this.dragging) {
        return;
      }
      this.dragging = false;
      e.item?.getType() === 'combo' &&
        this.graph.updateItem(e.item, {
          style: { cursor: 'grab' },
        });
      this.comboRect.el.style.cursor = 'grab';
      rootComboMovePoint.value.x && moveComboLabelPosition({ x: rootComboMovePoint.value.x });
    },
    onMouseLeave(this: DragCanvasBehaviorContext, e: IG6GraphEvent) {
      if (this.dragging) {
        e.item?.getType() === 'combo' &&
          this.graph.updateItem(e.item, {
            style: { cursor: 'grab' },
          });
        this.comboRect.el.style.cursor = 'grab';
        this.dragging = false;
      }
    },
  });
}
