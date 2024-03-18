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
import { HierarchyNode } from 'd3-hierarchy';

export const ColorTypes = {
  http: '#aea2e0',
  db: '#f9ba8f',
  rpc: '#eba8e6',
  other: '#59c0a3',
  mysql: '#82b5d8',
  message: '#4e92f9',
  elasticsearch: '#fee174',
  redis: '#ea6460',
  async_backend: '#699DF4',
  error: '#d74747',
  network: '#59c0a3'
};

export const RootId = '___root___';
export interface IOtherData {
  xAxisValue?: number;
  rootValue?: number;
}
export interface BaseRect {
  preDepth?: number;
  clickDepth?: number;
  startTime?: number;
  endTime?: number;
  highlightName?: string;
  highlightId?: number;
  keywords?: string[];
  value?: number;
}
export interface ThreadPos {
  x: number;
  y: number;
}
export interface RootData {
  startTime: number;
  endTime: number;
}
export interface BaseDataType {
  name: string;
  n?: string;
  value?: number;
  v?: number;
  children: Iterable<BaseDataType>;
  c?: BaseDataType[];
  id: string | number;
  hide?: boolean;
  start_time?: number;
  end_time?: number;
  depth?: number;
  status?: {
    message: string;
    code: 1 | 2 | 3;
  };
  last_sibling_id?: string;
  diff_info?: {
    baseline: number;
    comparison: number;
    mark: 'added' | 'removed' | 'changed' | 'unchanged';
  };
}
export interface ILineData<D extends BaseDataType> {
  x: number;
  y: number;
  tag: 'from' | 'to';
  data: D;
}
export interface IFlameChartOptions {
  w?: number;
  h?: number;
  c?: number;
  minHeight?: number;
  transitionDuration?: number;
  keywords?: string[];
  direction?: 'ltr' | 'rtl';
  getFillColor?: (d: BaseDataType) => string;
  onDetail?: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c?: IOtherData) => void;
  onMouseMove?: (e: MouseEvent, c?: IOtherData) => void;
  onContextMenu?: (e: MouseEvent, d: HierarchyNode<BaseDataType>) => void;
  onMouseOut?: (e: MouseEvent) => void;
  onMouseDown?: (e: MouseEvent) => void;
}
export interface IFlameData<D extends BaseDataType> {
  main: D;
  threads: D[];
}

export interface ICommonMenuItem {
  id: string; // 菜单 id
  name: string; // 菜单名称
  icon: string; // 菜单图标
}
// 基础 trace 信息
export interface IBaseTraceInfo {
  trace_end_time: number; // trace 结束时间
  trace_start_time: number; // trace 开始时间
  trace_duration: number; // trace 持续时间
}
export const CommonMenuList: ICommonMenuItem[] = [
  // {
  //   id: 'span',
  //   name: window.i18n.tc('Span 详情'),
  //   icon: 'icon-menu-view'
  // },
  {
    id: 'reset',
    name: window.i18n.tc('重置图表'),
    icon: 'icon-menu-view'
  },
  {
    id: 'highlight',
    name: window.i18n.tc('高亮相似 Span'),
    icon: 'icon-menu-view'
  }
];
// 用于标识根节点
export interface ITipsDetail {
  left?: number; // 提示框左边距离画布左边的距离
  top?: number; // 提示框上边距离画布上边的距离
  title?: string;
  proportion?: string | number;
  duration?: string;
  diffDuration?: string;
  diffValue?: number | string;
  id?: string | number;
  mark?: BaseDataType['diff_info']['mark'];
}
export interface IAxisRect {
  left?: number;
  top?: number;
  bottom?: number;
  title?: string;
  visibility?: 'hidden' | 'visible';
}
export interface IContextMenuRect {
  left: number;
  top: number;
  spanId: string | number;
  spanName: string;
}
/**
 * 表示一个缩放矩形的接口
 */
export interface IZoomRect {
  left: number; // 矩形左边距离画布左边的距离
  width: number; // 矩形的宽度
}
