/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝疆智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝疆智云PaaS平台 (BlueKing PaaS):
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
 * @file 自定义拓扑边注册
 * @description 注册 topo-edge / topo-edge-loop，并管理边流动动画定时器
 */

import { registerEdge } from '@antv/g6';

import { createConnectedParallelCurves } from '../utils';

import type { EdgeIntervalItem } from '../types/g6';
import type { IEdge } from '../types/topo';
import type { IGroup, Item, ModelConfig } from '@antv/g6';

/** 边业务字段：registerEdge 回调入参仍用官方 ModelConfig，内部再断言 */
type EdgeBizCfg = IEdge & ModelConfig;

// ============================================================================
// 边动画定时器管理（模块内部变量）
// ============================================================================

/** 模块内部：存储边动画定时器，用于重新渲染或卸载时清除 */
let edgeInterval: EdgeIntervalItem[] = [];

/** 清除所有边动画定时器（渲染新数据前或组件卸载时调用） */
export function clearEdgeIntervals(): void {
  // biome-ignore lint/complexity/noForEach: <explanation>
  edgeInterval.forEach(interval => {
    clearInterval(interval.timer);
  });
  edgeInterval = [];
}

// ============================================================================
// 边公共工具函数
// ============================================================================

const edgeUtils = {
  /** 绘制高亮边（选中时显示蓝色平行线） */
  handelCreateHighlightEdge(shape: any, group: IGroup) {
    const offset = shape.attrs.endArrow ? 6 : 0;
    const [left, right, mid] = createConnectedParallelCurves(
      shape.attrs.path,
      Math.max(shape.attrs.lineWidth - 1, 1),
      offset
    );
    group.addShape('path', {
      attrs: {
        ...shape.attrs,
        stroke: 'rgba(58, 132, 255, 1)',
        endArrow: false,
        lineDash: false,
        lineWidth: 0,
        path: right,
      },
      name: 'select-edge-path-right',
    });
    group.addShape('path', {
      attrs: {
        ...shape.attrs,
        stroke: 'rgba(58, 132, 255, 1)',
        endArrow: false,
        lineDash: false,
        lineWidth: 0,
        path: left,
      },
      name: 'select-edge-path-left',
    });

    group.addShape('path', {
      attrs: {
        ...shape.attrs,
        endArrow: false,
        stroke: 'rgba(58, 132, 255, 1)',
        lineDash: false,
        lineWidth: 0,
        path: mid,
      },
      name: 'select-edge-path-mid',
    });
  },

  /**
   * 处理边动画（异常边的流动虚线动画）
   * 边动画定时器由模块内 edgeInterval 统一管理
   */
  handleEdgeAnimation(shape: any, item: Item, cfg: EdgeBizCfg) {
    // biome-ignore lint/complexity/noForEach: <explanation>
    const { is_anomaly, anomaly_score, events, edge_type } = cfg;
    const lineDash = anomaly_score === 0 ? [6] : [10];
    if (is_anomaly && events?.[0] && edge_type === 'ebpf_call') {
      const { direction } = events[0];
      let index = 0;
      // 这里改为定时器执行，自带的动画流动速度控制不了
      const interVal: EdgeIntervalItem = {
        id: cfg.id as string,
        timer: setInterval(() => {
          if (item.hasState('highlight')) {
            item.toFront();
          }
          shape.animate(() => {
            index = index + 1;
            if (index > (anomaly_score === 0 ? 60 : 120)) {
              index = 0;
            }
            const res = {
              lineDash,
              lineDashOffset: direction === 'reverse' ? index : -index,
            };
            return res;
          });
        }, 30),
      };
      // 避免反复存储
      const intervalIndex = edgeInterval.findIndex(item => item.id === cfg.id);
      if (intervalIndex === -1) {
        edgeInterval.push(interVal);
      } else {
        clearInterval(edgeInterval[intervalIndex].timer);
        edgeInterval[intervalIndex] = null;
        edgeInterval.splice(intervalIndex, 1, interVal);
      }
    }
  },

  /** 添加聚合点（聚合边中点显示圆形数字标记） */
  addAggregationMarkers(cfg: EdgeBizCfg, group: IGroup) {
    if (!cfg.aggregated || !cfg.count) return;
    const shape = group.get('children')[0];
    // 获取路径图形的中点坐标
    const midPoint = shape.getPoint(0.5);
    // 在中点增加一个圆形，注意圆形的原点在其左上角
    group.addShape('circle', {
      zIndex: 10,
      attrs: {
        cursor: 'pointer',
        r: 10,
        fill: '#212224',
        // 使圆形中心在 midPoint 上
        x: midPoint.x,
        y: midPoint.y,
      },
    });
    group.addShape('text', {
      zIndex: 11,
      attrs: {
        cursor: 'pointer',
        x: midPoint.x,
        y: midPoint.y + 1,
        textAlign: 'center',
        textBaseline: 'middle',
        text: cfg.count,
        fontSize: 12,
        fill: '#fff',
      },
      name: 'topo-node-text',
    });
  },

  /** 处理边状态变化（highlight / dark / show-animate） */
  handleEdgeState(name: string, value: boolean | string, item: Item) {
    const model = item.getModel();
    const group = item.getContainer();
    const shape = group.get('children')[0];
    const { is_anomaly } = model;
    const colors = {
      highlight: is_anomaly ? '#F55555' : '#699DF4',
      dark: is_anomaly ? '#F55555' : '#63656E',
    };
    switch (name) {
      case 'show-animate':
        item.show();
        break;
      case 'highlight':
        // biome-ignore lint/complexity/noForEach: <explanation>
        group.get('children').forEach(shape => {
          const name = shape.get('name');
          if (name?.includes('select-edge-path')) {
            shape.attr('lineWidth', value ? 1 : 0);
          }
        });
        group.attr('opacity', 1);
        if (shape.attrs.endArrow) {
          shape.attr({
            endArrow: {
              opacity: 1,
              ...shape.attrs.endArrow,
              stroke: value ? '#3A84FF' : colors.dark,
            },
          });
        }
        break;
      case 'dark':
        group.attr('opacity', value ? 1 : 0.4);
        break;
    }
  },
};

// ============================================================================
// 边类型注册
// ============================================================================

/** 自定义边类型工厂函数（cfg 保持 G6 ModelConfig，与 registerEdge 签名兼容） */
const createEdgeConfig = () => ({
  afterDraw(cfg: ModelConfig, group: IGroup) {
    const shape = group.get('children')[0];
    const item = group.get('item') as Item;
    // 业务边字段从 ModelConfig 断言读取
    const edgeCfg = cfg as EdgeBizCfg;
    edgeUtils.handleEdgeAnimation(shape, item, edgeCfg);
    edgeUtils.addAggregationMarkers(edgeCfg, group);
    // 绘制异常选中的高亮边
    edgeUtils.handelCreateHighlightEdge(shape, group);
  },
  setState(name: string, value: boolean | string, item: Item) {
    edgeUtils.handleEdgeState(name, value, item);
  },
  update: undefined,
});

/**
 * 注册自定义拓扑边
 * 注册 'topo-edge' (普通边/二次曲线) 和 'topo-edge-loop' (自环边) 两种边类型
 */
export function registerTopoEdge(): void {
  // 普通边
  registerEdge('topo-edge', createEdgeConfig(), 'quadratic');
  // 自环边
  registerEdge('topo-edge-loop', createEdgeConfig(), 'loop');
}
