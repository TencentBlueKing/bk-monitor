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
 * @file 节点拖拽行为
 * @description 注册 drag-node-with-fixed-combo：节点/子 combo 拖拽且限制在父 combo 内
 */
import { type IBBox, type ICombo, type IG6GraphEvent, type INode, registerBehavior } from '@antv/g6';

import type { DragNodeBehaviorContext } from '../../types/g6';
import type { ITopoNode } from '../../types/topo';

/** 拖拽行为 this 上下文 */
type DragNodeThis = DragNodeBehaviorContext;

/**
 * 注册自定义拖拽行为 - 防止节点拖出 combo
 * @param toFrontAnomalyEdge - 拖拽结束后将边(异常边)置于顶层的回调
 */
export function registerDragNodeWithFixedCombo(toFrontAnomalyEdge: () => void): void {
  registerBehavior('drag-node-with-fixed-combo', {
    getEvents() {
      return {
        'combo:dragstart': 'onDragStart',
        'combo:drag': 'onDrag',
        'combo:dragend': 'onDragEnd',
        'node:dragstart': 'onDragStart',
        'node:drag': 'onDrag',
        'node:dragend': 'onDragEnd',
      };
    },
    onDragStart(this: DragNodeThis, e: IG6GraphEvent) {
      const { item } = e;
      const combos = this.graph.getCombos();
      const model = item.getModel();
      // 存储当前节点所在的 combo ID
      if (item.get('type') === 'node' || (item.get('type') === 'combo' && model.parentId)) {
        const combo = combos.find((combo: ICombo) =>
          [model.comboId, model.subComboId, model.parentId].includes(combo.getID())
        );
        this.currentComboId = combo ? combo.getID() : null;
        this.currentNodes = [];
        /** 如果拖动的是combo */
        if (item.get('type') === 'combo') {
          this.graph.getNodes().forEach((node: INode) => {
            if (node.getModel().subComboId === item.getID()) {
              this.currentNodes!.push(node);
            }
          });
        }
        this.origin = { x: e.x, y: e.y };
      }
      // 拖动combo或者节点时，隐藏Tooltip
      const comboLabelTooltip = document.getElementById('combo-label-tooltip');
      if (comboLabelTooltip) {
        comboLabelTooltip.style.visibility = 'hidden';
      }
      const nodeInfoTooltip = document.getElementById('node-detail-tips');
      if (nodeInfoTooltip) {
        nodeInfoTooltip.style.visibility = 'hidden';
      }
    },
    onDrag(this: DragNodeThis, e: IG6GraphEvent) {
      const { item, x, y } = e;
      if (this.currentComboId) {
        const combos = this.graph.getCombos();
        let dragBbox: any = item.getBBox();
        const combo = combos.find((combo: ICombo) => combo.getID() === this.currentComboId);
        const comboBBox = combo.getBBox();
        // 假设节点的边长为40
        const nodeSize = 40;
        const { x: originX, y: originY } = this.origin as { x: number; y: number };
        let dx = x - originX;
        let dy = y - originY;

        if (item.get('type') === 'node') {
          // getModel 返回 ModelConfig，业务字段需断言为拓扑节点
          const model = item.getModel() as ITopoNode;
          const isAggregatedNode = (model.aggregated_nodes?.length ?? 0) > 0;
          // 聚合节点不会展示 节点名称用外层容器节点类型判断， 非聚合节点用节点名称判断
          // group.find 回调参数为 G6 Shape，类型未稳定导出，暂用 any
          const nameTextShape = item
            .get('group')
            .find((s: any) => s.get('name') === (isAggregatedNode ? 'topo-node-type-text' : 'topo-node-name-text'));
          // getBBox 可能返回不完整字段，兜底后按 IBBox 使用
          const nameShapeBBox: IBBox = nameTextShape?.getBBox?.() || {
            width: 0,
            y: 0,
            height: 0,
            minX: 0,
            maxX: 0,
            minY: 0,
            maxY: 0,
            x: 0,
          };
          // 获取该Shape相对于画布的边界框
          // 根据节点中心位置和边长计算出节点的新边界框
          dragBbox = {
            minX: (model.x ?? 0) + (nameShapeBBox.minX ?? 0),
            maxX: (model.x ?? 0) + (nameShapeBBox.maxX ?? 0),
            minY: (model.y ?? 0) + (nameShapeBBox.minY ?? 0) - (nodeSize + (nameShapeBBox.height ?? 0) * 2),
            maxY: (model.y ?? 0) + (nameShapeBBox.maxY ?? 0),
          };
        }
        if (dragBbox.minX + dx < comboBBox.minX) {
          dx = comboBBox.minX - dragBbox.minX;
        }
        if (dragBbox.maxX + dx > comboBBox.maxX) {
          dx = comboBBox.maxX - dragBbox.maxX;
        }
        if (dragBbox.minY + dy < comboBBox.minY) {
          dy = comboBBox.minY - dragBbox.minY;
        }
        if (dragBbox.maxY + dy > comboBBox.maxY) {
          dy = comboBBox.maxY - dragBbox.maxY;
        }
        // 如果节点新位置还在Combo内，可以移动
        // 如果需要的话可以让节点到最前方显示
        item.toFront();
        const model = item.getModel();
        this.graph.updateItem(item, {
          x: model.x + dx,
          y: model.y + dy,
        });
        (this.currentNodes ?? []).forEach((node: INode) => {
          const model = node.getModel();
          this.graph.updateItem(node, {
            x: model.x + dx,
            y: model.y + dy,
          });
          node.toFront();
        });
        this.origin = { x: e.x, y: e.y };
      }
    },
    onDragEnd(this: DragNodeThis) {
      // 清除临时信息
      this.currentComboId = undefined;
      this.currentNodes = undefined;
      setTimeout(toFrontAnomalyEdge);
    },
  });
}
