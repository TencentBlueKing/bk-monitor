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
 * @file failure-topo 专用 G6 Tooltip 插件
 * @description
 * - tip 与 graph 同挂 #topo-graph，定位不加 container offset
 * - hide 时安全清理，不依赖可能已销毁的 graph.emit
 */

import { nextTick } from 'vue';

import { type IG6GraphEvent, type IGraph } from '@antv/g6';

import TopoTooltip from './resource-tooltip-plugin';

/**
 * FailureTopo 主画布 Tooltip。
 * 在 Vue 重绘 tip 内容后再量尺寸，避免聚合列表（大）切到节点概览（小）时用旧 bbox 翻转错位。
 */
export default class FailureTopoG6Tooltip extends TopoTooltip {
  /**
   * 外部 hide（侧滑/resize）时清理状态并隐藏 DOM。
   * 不走父类 hide→onMouseLeave（需 graph.emit），避免插件销毁后对 null 取属性。
   */
  hide() {
    this.setTipTarget(null);
    this.hideTooltip();
  }

  /**
   * tip 与 graph 同容器时直接使用画布坐标，不再叠加 offsetLeft/Top。
   */
  updatePositionExpand(e: IG6GraphEvent) {
    nextTick(() => {
      const tooltip = this.get('tooltip') as HTMLElement | null;
      const graph: IGraph = this.get('graph');
      if (!tooltip || !graph || (this as { destroyed?: boolean }).destroyed) return;

      // 画布逻辑宽高，用于溢出翻转判断
      const width: number = graph.get('width');
      const height: number = graph.get('height');

      const offsetX = this.get('offsetX') || 0;
      const offsetY = this.get('offsetY') || 0;

      let point = graph.getPointByClient(e.clientX, e.clientY);

      const fixToNode = this.get('fixToNode');
      const { item } = e;
      if (item?.getType?.() === 'node' && fixToNode && Array.isArray(fixToNode) && fixToNode.length >= 2) {
        const itemBBox = item.getBBox();
        point = {
          x: itemBBox.minX + itemBBox.width * fixToNode[0],
          y: itemBBox.minY + itemBBox.height * fixToNode[1],
        };
      }

      // 与 position:absolute 的 tip 同源坐标系
      const { x, y } = graph.getCanvasByPoint(point.x, point.y);

      const res = {
        x: x + offsetX,
        y: y + offsetY,
      };

      // 先改为可见才能正确量到当前 tip 真实尺寸
      modifyCSS(tooltip, {
        visibility: 'visible',
        display: 'unset',
      });
      const bbox = tooltip.getBoundingClientRect();

      if (x + bbox.width + offsetX > width) {
        res.x -= bbox.width + offsetX;
      }

      if (y + bbox.height + offsetY > height) {
        res.y -= bbox.height + offsetY;
        if (res.y < 0) {
          res.y = 0;
        }
      }

      modifyCSS(tooltip, {
        left: `${res.x}px`,
        top: `${res.y}px`,
      });
    });
  }
}

function modifyCSS(dom: HTMLElement | null | undefined, css: { [key: string]: any }): HTMLElement {
  if (!dom) return;

  Object.keys(css).forEach(key => {
    dom.style[key] = css[key];
  });
  return dom;
}
