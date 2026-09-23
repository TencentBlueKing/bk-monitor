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
 * @file G6 图形引擎相关类型声明
 * @description G6 节点样式、边动画、画布坐标、拖拽行为、Tooltip 等类型定义
 */

import type { IEdge, ITopoCombo, ITopoNode } from './topo';
import type { Graph, ICombo, INode } from '@antv/g6';

/** 画布坐标转换结果（getComboCanvasBounds 返回值） */
export interface CanvasByPointResult {
  bottomRight: { x: number; y: number };
  topLeft: { x: number; y: number };
}

/** Combo 拖拽后 label 坐标缓存 */
export interface ComboLabelPoint {
  x: null | number;
  y: null | number;
}

/** 详情面板类型枚举 */
export type DetailType = 'edge' | 'node';

/** 时间轴差异帧数据（TopoRawDataCache.diff 元素类型） */
export interface DiffItem {
  [key: string]: any;
  create_time: number;
  showEdges: IEdge[];
  showNodes: ITopoNode[];
  showSubCombos: ITopoCombo[];
  content: {
    [key: string]: any;
    edges: IEdge[];
    nodes: ITopoNode[];
    sub_combos: ITopoCombo[];
  };
}

/** drag-canvas-move 行为的 this 上下文 */
export interface DragCanvasBehaviorContext {
  comboRect: DragCanvasComboRect;
  dragging: boolean;
  graph: Graph;
}

/** drag-canvas-move 行为中的 comboRect 临时状态 */
export interface DragCanvasComboRect {
  bottomCombo?: ICombo;
  el: HTMLElement;
  height?: number;
  labelPoint?: { x: number; y: number };
  topCombo?: ICombo;
  width?: number;
  xCombo?: ICombo;
}

/** drag-node-with-fixed-combo 行为的 this 上下文 */
export interface DragNodeBehaviorContext {
  currentComboId?: null | string;
  currentNodes?: INode[];
  graph: Graph;
  origin?: { x: number; y: number };
}

/** 边动画定时器项 */
export interface EdgeIntervalItem {
  id: string;
  timer: null | ReturnType<typeof setInterval>;
}

/** 错误数据状态 */
export interface ErrorData {
  isError: boolean;
  isNoData: boolean;
  msg: string;
}

/** 导航选中节点条目（navSelectNode computed 元素） */
export interface NavSelectNodeItem {
  entity_name: string;
  entityId: string;
  id: string;
}

/** 节点样式属性集合（getNodeAttrs 返回值） */
export interface NodeStyleAttrs {
  groupAttrs: { fill: string; stroke: string };
  rectAttrs: { fill: string; stroke: string };
  textAttrs: { fill: string };
  textNameAttrs: { fill: string };
}

/** 播放选项参数 */
export interface PlayOption {
  timeline?: unknown;
  value: boolean;
}

/** Tooltip 类型枚举 */
export type TooltipType = 'edge' | 'node';

/** 拓扑完整缓存帧（complete / latest 共用结构） */
export interface TopoCacheFrame {
  combos?: ITopoCombo[];
  edges?: IEdge[];
  nodes: ITopoNode[];
  sub_combos?: ITopoCombo[];
}

/** 拓扑数据缓存（核心状态容器） */
export interface TopoRawDataCache {
  diff: DiffItem[];
  /** 最新一帧（至少含 nodes） */
  latest: TopoCacheFrame;
  /** 完整拓扑数据帧 */
  complete: TopoCacheFrame & {
    combos: ITopoCombo[];
    edges: IEdge[];
    nodes: ITopoNode[];
  };
}

/** 文本截断函数签名（createTruncateByTextWidth 的返回类型） */
export type TruncateByTextWidthFn = (text: string, maxWidth?: number) => string;
