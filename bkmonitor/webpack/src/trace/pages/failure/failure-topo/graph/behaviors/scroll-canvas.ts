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
 * @file 自定义滚动画布行为
 * @description 注册 custom-scroll-canvas：failure-topo 专用滚轮缩放行为（与 resource-graph 的行为区分）
 */
import { type ICombo, type IG6GraphEvent, registerBehavior } from '@antv/g6';

import type { CanvasByPointResult } from '../../types/g6';
import type { Graph } from '@antv/g6';

/** 增加画布离画布上下左右的留白区域 */
const GRAPH_DRAG_MARGIN = 100;

/** 画布滚轮滚动行为上下文（this 类型） */
interface ScrollCanvasContext {
  graph: Graph;
}

/**
 * 注册自定义滚动行为 - failure-topo 扩展版
 *
 * 与 resource-graph 的 custom-scroll-canvas-base 的差异：
 * 1. 更大的留白边距：GRAPH_DRAG_MARGIN = 100（resource-graph 用 0）
 * 2. 接收外部 getCanvasByPoint 函数（resource-graph 使用 getComboCanvasBounds）
 *
 * ⚠️ onWheel 必须用正则函数（非箭头函数），否则 G6 无法绑定 this.graph，
 *    而 e.graph 在 wheel 事件中不可靠（部分场景为 undefined）。
 */
export function registerScrollCanvas(getCanvasByPoint: (combo: ICombo) => CanvasByPointResult): void {
  registerBehavior('custom-scroll-canvas', {
    getEvents() {
      return {
        wheel: 'onWheel',
      };
    },
    onWheel(this: ScrollCanvasContext, e: IG6GraphEvent) {
      e.preventDefault();
      e.stopPropagation();
      // wheel 事件上的 delta 字段未在 IG6GraphEvent 中声明，仅做类型断言
      const { deltaX, deltaY } = e as IG6GraphEvent & { deltaX: number; deltaY: number };
      // 设置滚动灵敏度
      const sensitivity = 2;
      let dx = -deltaX * sensitivity;
      let dy = -deltaY * sensitivity;

      // 获取所有combos的布局信息
      const combos = this.graph.getCombos().filter((combo: ICombo) => !combo.getModel().parentId);
      const width = this.graph.getWidth();
      const height = this.graph.getHeight() + 20;

      if (Math.abs(deltaY) > Math.abs(deltaX)) {
        // vertical scroll
        if (deltaY > 0) {
          const bottomCombo = combos[combos.length - 1];
          const { bottomRight } = getCanvasByPoint(bottomCombo);
          if (bottomRight.y + GRAPH_DRAG_MARGIN < height) {
            dy = 0;
          }
        } else {
          const topCombo = combos[0];
          const { topLeft } = getCanvasByPoint(topCombo);
          if (topLeft.y - GRAPH_DRAG_MARGIN > 0) {
            dy = 0;
          }
        }
        dx = 0;
      } else {
        const topCombo = combos[0];
        const { topLeft, bottomRight } = getCanvasByPoint(topCombo);
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
