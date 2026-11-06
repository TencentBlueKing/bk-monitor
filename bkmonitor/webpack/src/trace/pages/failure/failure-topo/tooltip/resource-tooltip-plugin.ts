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
 * @file resource-graph 使用的 G6 Tooltip 插件
 */

import { nextTick } from 'vue';

import { type IG6GraphEvent, type IGraph, type Item, Tooltip } from '@antv/g6';

export interface IPluginBaseConfig {
  [key: string]: any;
  className?: string;
  container?: HTMLDivElement | null | string;
  graph?: IGraph;
}

interface TooltipConfig extends IPluginBaseConfig {
  fixToNode?: [number, number] | undefined;
  // 允许出现 tooltip 的 item 类型
  itemTypes?: string[];
  offsetX?: number;
  offsetY?: number;
  trigger?: 'click' | 'mouseenter';
  getContent?: (evt?: IG6GraphEvent) => HTMLDivElement | string;
  shouldBegin?: (evt?: IG6GraphEvent) => boolean;
}

/**
 * resource-graph / failure-topo 共用基类 Tooltip：
 * - 用 tipTarget 做开关态（避开基类 private currentTarget 的 TS 冲突）
 * - 必须在 hide / onMouseLeave（含 drag、canvas:click）里清空 tipTarget，否则下次点同一节点会被当成关闭
 * - nextTick 后按真实尺寸定位
 */
export default class TopoTooltip extends Tooltip {
  /** 定义不可出现 tips 的情况（resource-graph 传入） */
  disabled: (e: IG6GraphEvent) => boolean;
  /**
   * 当前 tip 对应图元。
   * 不用 currentTarget 命名，避免与基类 private currentTarget 产生 TS2415。
   */
  protected tipTarget: Item | null = null;

  constructor(config: TooltipConfig, disabled?: (e: IG6GraphEvent) => boolean) {
    super(config);
    disabled && (this.disabled = disabled);
  }

  public getDefaultCfgs(): TooltipConfig {
    return {
      offsetX: 6,
      offsetY: 6,
      // 指定菜单内容，function(e) {...}
      getContent: e => {
        return `
          <h4 class='tooltip-type'>类型：${e.item.getType()}</h4>
          <span class='tooltip-id'>ID：${e.item.getID()}</span>
        `;
      },
      shouldBegin: () => {
        return false;
      },
      itemTypes: ['node', 'edge', 'combo'],
      trigger: 'mouseenter',
      fixToNode: undefined,
    };
  }

  /**
   * 外部 hide（互关 tip、combo 点击、resize）。
   * 必须清空 tipTarget，不能只调父类 hide→onMouseLeave（父类只清 private currentTarget）。
   */
  hide() {
    this.setTipTarget(null);
    this.hideTooltip();
  }

  onClick(e: IG6GraphEvent) {
    if (this.disabled?.(e)) return;
    const itemTypes = this.get('itemTypes');
    if (e.item?.getType && itemTypes.indexOf(e.item.getType()) === -1) return;

    const { item } = e;
    const graph: IGraph = this.get('graph');
    // 插件已销毁或 graph 未就绪时不处理，避免对 null 取属性
    if (!graph || (this as { destroyed?: boolean }).destroyed) return;

    // 若与上一次同一 item，隐藏该 tooltip
    if (this.tipTarget === item) {
      this.setTipTarget(null);
      this.hideTooltip();
      graph.emit('tooltipchange', { item: e.item, action: 'hide' });
    } else {
      this.setTipTarget(item);
      this.showTooltip(e);
      this.updatePositionExpand(e);
      graph.emit('tooltipchange', { item: e.item, action: 'show' });
    }
  }

  /**
   * 覆盖父类：drag / canvas:click / contextmenu 等都会走到这里。
   * 拖拽节点后若 tipTarget 未清空，再点同一节点会被当成「二次点击关闭」而出不来 tip。
   */
  onMouseLeave() {
    const prevTarget = this.tipTarget;
    this.hideTooltip();
    const graph: IGraph | undefined = this.get('graph');
    if (graph && !(this as { destroyed?: boolean }).destroyed) {
      graph.emit('tooltipchange', { item: prevTarget, action: 'hide' });
    }
    this.setTipTarget(null);
  }

  /** 写入当前 tip 图元 */
  protected setTipTarget(item: Item | null) {
    this.tipTarget = item;
  }

  updatePositionExpand(e: IG6GraphEvent) {
    nextTick(() => {
      const tooltip = this.get('tooltip');
      const graph: IGraph = this.get('graph');
      if (!tooltip || !graph || (this as { destroyed?: boolean }).destroyed) return;

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

      const { x, y } = graph.getCanvasByPoint(point.x, point.y);

      const graphContainer = graph.getContainer();

      // resource-graph 历史定位：画布坐标 + container offset
      const res = {
        x: x + graphContainer.offsetLeft + offsetX,
        y: y + graphContainer.offsetTop + offsetY,
      };

      // 先修改为 visible 方可正确计算 bbox
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

/**
 * Modify the CSS of a DOM.
 * @param dom
 * @param css
 * @returns
 */
function modifyCSS(dom: HTMLElement | null | undefined, css: { [key: string]: any }): HTMLElement {
  if (!dom) return;

  Object.keys(css).forEach(key => {
    dom.style[key] = css[key];
  });
  return dom;
}
