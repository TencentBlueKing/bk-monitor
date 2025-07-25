/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

export default class TopoTooltip extends Tooltip {
  currentTarget: Item;
  disabled: (e: IG6GraphEvent) => boolean; // 定义不可出现tips的情况
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

  onClick(e: IG6GraphEvent) {
    if (this.disabled?.(e)) return;
    const itemTypes = this.get('itemTypes');
    if (e.item?.getType && itemTypes.indexOf(e.item.getType()) === -1) return;

    const { item } = e;
    const graph: IGraph = this.get('graph');
    // 若与上一次同一 item，隐藏该 tooltip
    if (this.currentTarget === item) {
      this.currentTarget = null;
      this.hideTooltip();
      graph.emit('tooltipchange', { item: e.item, action: 'hide' });
    } else {
      this.currentTarget = item;
      this.showTooltip(e);
      this.updatePositionExpand(e);
      graph.emit('tooltipchange', { item: e.item, action: 'show' });
    }
  }

  updatePositionExpand(e: IG6GraphEvent) {
    nextTick(() => {
      const tooltip = this.get('tooltip');

      const graph: IGraph = this.get('graph');
      const width: number = graph.get('width');
      const height: number = graph.get('height');

      const offsetX = this.get('offsetX') || 0;
      const offsetY = this.get('offsetY') || 0;

      let point = graph.getPointByClient(e.clientX, e.clientY);

      const fixToNode = this.get('fixToNode');
      const { item } = e;
      if (item.getType && item.getType() === 'node' && fixToNode && Array.isArray(fixToNode) && fixToNode.length >= 2) {
        const itemBBox = item.getBBox();
        point = {
          x: itemBBox.minX + itemBBox.width * fixToNode[0],
          y: itemBBox.minY + itemBBox.height * fixToNode[1],
        };
      }

      const { x, y } = graph.getCanvasByPoint(point.x, point.y);

      const graphContainer = graph.getContainer();

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
