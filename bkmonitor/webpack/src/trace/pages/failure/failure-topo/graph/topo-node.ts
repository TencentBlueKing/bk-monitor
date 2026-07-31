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
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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
 * @file 自定义拓扑节点注册
 * @description 注册 G6 'topo-node'，并提供文本截断工厂与节点动画清理
 */

import { registerNode } from '@antv/g6';

import { checkIsRoot } from '../../utils';
import { NODE_TYPE_SVG } from '../node-type-svg';
import { getApmServiceType, getNodeAttrs, truncateText } from '../utils';

import type { NodeStyleAttrs, TruncateByTextWidthFn } from '../types/g6';
import type { ITopoNode } from '../types/topo';
import type { IGroup, Item, ModelConfig } from '@antv/g6';

// ============================================================================
// 文本截断工厂函数
// ============================================================================

/**
 * 创建文本截断函数（基于 Canvas 2D context 测量文本宽度）
 * 由调用方注入 Canvas context，返回可复用的截断函数。
 *
 * @param context - Canvas 2D 上下文，通常从 graph.get('canvas').get('context') 获取
 * @returns TruncateByTextWidthFn - 文本截断函数
 */
export function createTruncateByTextWidth(context: CanvasRenderingContext2D): TruncateByTextWidthFn {
  return (text: string, maxWidth = 80) => {
    const textWidth = context.measureText(text).width;
    if (textWidth > maxWidth) {
      let truncatedText = '';
      let accumulatedWidth = 0;

      // 逐个字符检查，直到累计宽度超过最大宽度，然后截断
      for (const char of text) {
        accumulatedWidth += context.measureText(char).width;
        if (accumulatedWidth > maxWidth) break;
        truncatedText += char;
      }
      return `${truncatedText}...`;
    }
    return text;
  };
}

// ============================================================================
// 动画管理（模块内部变量）
// ============================================================================

/** 模块内部：存储当前活跃的动画实例，用于 setState('running', false) 时批量停止 */
let activeAnimation: { stop?: () => void }[] = [];

/** 清理所有节点动画（组件卸载时调用） */
export function clearActiveAnimations(): void {
  activeAnimation.forEach(animation => animation?.stop?.());
  activeAnimation = [];
}

// ============================================================================
// 自定义节点注册
// ============================================================================

/**
 * 注册自定义拓扑节点 'topo-node'
 *
 * @param truncateByTextWidth - 文本截断函数，由 createTruncateByTextWidth 创建后注入
 *   用于 draw() 中 entity_show_type / entity_name 等动态文本的截断
 *
 * 注意：
 * - 根因标签 "根因" 使用 truncateText + window.i18n.t（与 service-combo.tsx 保持一致）
 * - entity_show_type / entity_name 使用 truncateByTextWidth（基于 Canvas context 测量）
 */
export function registerTopoNode(truncateByTextWidth: TruncateByTextWidthFn): void {
  registerNode('topo-node', {
    afterDraw(cfg: ModelConfig, group: IGroup) {
      // registerNode 回调入参为 ModelConfig，内部断言为业务节点
      const model = cfg as ITopoNode;
      const nodeAttrs: NodeStyleAttrs = getNodeAttrs(model);
      const { entity, alert_all_recorved, is_feedback_root } = model;
      const isRoot = checkIsRoot(entity);
      if (isRoot || is_feedback_root) {
        group.addShape('circle', {
          attrs: {
            lineDash: [3],
            lineWidth: 1, // 描边宽度
            cursor: 'pointer', // 手势类型
            r: 25, // 圆半径
            stroke: isRoot ? '#F55555' : '#FF9C01',
          },
          name: 'topo-node-root-border',
        });
        group.addShape('rect', {
          zIndex: 10,
          attrs: {
            x: -15,
            y: 12,
            width: 30,
            height: 16,
            radius: 8,
            stroke: '#3A3B3D',
            fill: isRoot ? '#F55555' : '#FF9C01',
          },
          name: 'topo-node-rect',
        });
        group.addShape('text', {
          zIndex: 11,
          attrs: {
            x: 0,
            y: 21,
            textAlign: 'center',
            textBaseline: 'middle',
            text: truncateText(window.i18n.t('根因'), 28, 11, 'PingFangSC-Medium'),
            fontSize: 11,
            fill: '#fff',
            ...nodeAttrs.textAttrs,
          },
          name: 'topo-node-text',
        });
      }
      if (entity.is_on_alert || alert_all_recorved) {
        group.addShape('circle', {
          attrs: {
            x: 15,
            y: -14,
            zIndex: 10,
            lineWidth: 1, // 描边宽度
            cursor: 'pointer', // 手势类型
            r: 8, // 圆半径
            fill: entity.is_on_alert ? '#F55555' : '#6C6F78',
          },
          name: 'topo-tag-border',
        });
        group.addShape('image', {
          zIndex: 12,
          attrs: {
            x: 9,
            y: -21,
            width: 12,
            height: 12,
            cursor: 'pointer', // 手势类型
            img: NODE_TYPE_SVG.Alert,
          },
          draggable: true,
          name: 'topo-tag-img',
        });
      }
    },
    draw(cfg: ModelConfig, group: IGroup) {
      // registerNode 回调入参为 ModelConfig，内部断言为业务节点
      const model = cfg as ITopoNode;
      const { entity, aggregated_nodes, anomaly_count, is_feedback_root } = model;
      const nodeAttrs: NodeStyleAttrs = getNodeAttrs(model);
      const isRoot = checkIsRoot(entity);
      const showRoot = isRoot || entity.is_feedback_root;
      const isAggregated = (aggregated_nodes?.length ?? 0) > 0;
      const nodeShapeWrap = group.addShape('rect', {
        zIndex: 10,
        attrs: {
          x: showRoot ? -25 : -20,
          y: showRoot ? -28 : -22,
          lineWidth: 1, // 描边宽度
          cursor: 'pointer', // 手势类型
          width: showRoot ? 50 : 40, // 根因有外边框整体宽度为50
          height: showRoot ? 82 : isAggregated ? 63 : 67, // 根因展示根因提示加节点类型加节点名称 聚合节点展示聚合提示加类型 普通节点展示名字与类型
        },
        draggable: true,
        name: 'topo-node-shape-wrap',
      });
      group.addShape('circle', {
        zIndex: 10,
        attrs: {
          lineWidth: 1, // 描边宽度
          cursor: 'pointer', // 手势类型
          r: 20, // 圆半径
          ...nodeAttrs.groupAttrs,
          fill: showRoot ? '#F55555' : nodeAttrs.groupAttrs.fill,
        },
        draggable: true,
        name: 'topo-node-shape',
      });
      group.addShape('image', {
        zIndex: 12,
        attrs: {
          x: -14,
          y: -14,
          width: 28,
          height: 28,
          cursor: 'pointer', // 手势类型
          img: NODE_TYPE_SVG[getApmServiceType(entity)],
        },
        draggable: true,
        name: 'topo-node-img',
      });
      group.addShape('circle', {
        attrs: {
          lineWidth: 0, // 描边宽度
          cursor: 'pointer', // 手势类型
          r: 22, // 圆半径
          stroke: 'rgba(5, 122, 234, 1)',
        },
        name: 'topo-node-running',
      });
      group.addShape('circle', {
        attrs: {
          lineWidth: 0,
          cursor: 'pointer',
          r: 27,
          stroke: '#3a84ff4d',
        },
        name: 'topo-node-running-shadow',
      });

      if (aggregated_nodes?.length) {
        group.addShape('rect', {
          zIndex: 10,
          attrs: {
            x: (anomaly_count as number) > 0 ? -17 : -8,
            y: 12,
            width: (anomaly_count as number) > 0 ? 32 : 16,
            cursor: 'pointer',
            height: 16,
            radius: 8,
            fill: '#fff',
            ...nodeAttrs.rectAttrs,
          },
          name: 'topo-node-rect',
        });
        (anomaly_count as number) > 0 &&
          group.addShape('text', {
            zIndex: 11,
            attrs: {
              x: -9,
              y: 21,
              cursor: 'cursor',
              textAlign: 'center',
              textBaseline: 'middle',
              text: anomaly_count,
              fontSize: 11,
              ...nodeAttrs.textAttrs,
              fill: '#FF6666',
            },
            name: 'topo-node-err-text',
          });
        (anomaly_count as number) > 0 &&
          group.addShape('text', {
            zIndex: 11,
            attrs: {
              x: -2,
              y: 21,
              cursor: 'default',
              textAlign: 'center',
              textBaseline: 'middle',
              text: '/',
              fontSize: 11,
              ...nodeAttrs.textAttrs,
              fill: '#979BA5',
            },
            name: 'topo-node-err-text',
          });

        group.addShape('text', {
          zIndex: 11,
          attrs: {
            x: 0 + ((anomaly_count as number) > 0 ? 5 : 0),
            y: 21,
            textAlign: 'center',
            cursor: 'cursor',
            textBaseline: 'middle',
            text:
              isRoot || is_feedback_root
                ? truncateText(window.i18n.t('根因'), 28, 11, 'PingFangSC-Medium')
                : aggregated_nodes.length + 1,
            fontSize: 11,
            fill: '#EAEBF0',
            ...nodeAttrs.textAttrs,
          },
          name: 'topo-node-text',
        });
      }
      group.addShape('text', {
        zIndex: 11,
        attrs: {
          x: 0,
          y: aggregated_nodes?.length || isRoot || is_feedback_root ? 36 : 28,
          textAlign: 'center',
          textBaseline: 'middle',
          cursor: 'cursor',
          text: truncateByTextWidth(entity?.properties?.entity_show_type || entity.entity_type),
          fontSize: 10,
          ...nodeAttrs.textNameAttrs,
        },
        name: 'topo-node-type-text',
      });
      aggregated_nodes.length === 0 &&
        group.addShape('text', {
          zIndex: 11,
          attrs: {
            x: 0,
            y: isRoot || is_feedback_root ? 48 : 40,
            textAlign: 'center',
            textBaseline: 'middle',
            cursor: 'cursor',
            text: truncateByTextWidth(entity.entity_name),
            fontSize: 10,
            ...nodeAttrs.textNameAttrs,
          },
          name: 'topo-node-name-text',
        });
      group.sort();
      return nodeShapeWrap;
    },
    setState(name: string, value: boolean | string, item: Item) {
      const group = item.getContainer();
      if (name === 'hover') {
        const shape = group.find(e => e.get('name') === 'topo-node-shape');
        shape?.attr({
          shadowColor: value ? 'rgba(0, 0, 0, 0.5)' : false,
          shadowBlur: value ? 6 : false,
          shadowOffsetX: value ? 0 : false,
          shadowOffsetY: value ? 2 : false,
          strokeOpacity: value ? 0.6 : 1,
          cursor: 'pointer', // 手势类型
        });
      } else if (name === 'running') {
        const runningShape = group.find(e => e.get('name') === 'topo-node-running');
        const runningShadowShape = group.find(e => e.get('name') === 'topo-node-running-shadow');
        const rootBorderShape = group.find(e => e.get('name') === 'topo-node-root-border');
        if (value) {
          rootBorderShape?.attr({
            opacity: 0,
          });
          runningShape.attr({
            lineWidth: 3,
            r: 24,
            strokeOpacity: 1,
          });
          runningShadowShape.attr({
            lineWidth: 3,
            r: 27,
            strokeOpacity: 1,
          });
        } else {
          rootBorderShape?.attr({
            opacity: 1,
          });
          runningShape.attr({
            lineWidth: 0, // 描边宽度
            cursor: 'pointer', // 手势类型
            r: 22, // 圆半径
            stroke: 'rgba(5, 122, 234, 1)',
          });
          runningShadowShape.attr({
            lineWidth: 0,
            cursor: 'pointer',
            r: 27,
            stroke: '#3a84ff4d',
          });
          activeAnimation.forEach(animation => animation?.stop?.());
          activeAnimation = [];
        }
      } else if (name === 'show-animate') {
        group.attr({
          opacity: 0,
        });
        item.show();
        group.animate(
          {
            opacity: 1,
          },
          {
            duration: 1000,
          }
        );
      } else if (name === 'dark') {
        group.attr({
          opacity: value ? 0.4 : 1,
        });
      }
    },
  });
}
