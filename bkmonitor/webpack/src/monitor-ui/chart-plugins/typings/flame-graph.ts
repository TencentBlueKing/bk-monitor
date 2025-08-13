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

import { getHashVal } from '../plugins/profiling-graph/flame-graph/utils';

import type { HierarchyNode } from 'd3-hierarchy';

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
  network: '#59c0a3',
};

export const RootId = '___root___';
export interface BaseDataType {
  c?: BaseDataType[];
  children: Iterable<BaseDataType>;
  depth?: number;
  end_time?: number;
  hide?: boolean;
  id: number | string;
  last_sibling_id?: string;
  n?: string;
  name: string;
  start_time?: number;
  v?: number;
  value?: number;
  diff_info?: {
    baseline: number;
    comparison: number;
    diff: number;
    mark: 'added' | 'changed' | 'removed' | 'unchanged';
  };
  status?: {
    code: 1 | 2 | 3;
    message: string;
  };
}
export interface BaseRect {
  clickDepth?: number;
  endTime?: number;
  highlightId?: number;
  highlightName?: string;
  keywords?: string[];
  preDepth?: number;
  startTime?: number;
  value?: number;
}
// 基础 trace 信息
export interface IBaseTraceInfo {
  trace_duration: number; // trace 持续时间
  trace_end_time: number; // trace 结束时间
  trace_start_time: number; // trace 开始时间
}
export interface ICommonMenuItem {
  icon: string; // 菜单图标
  id: string; // 菜单 id
  name: string; // 菜单名称
}
export interface IFlameChartOptions {
  c?: number;
  direction?: 'ltr' | 'rtl';
  h?: number;
  keywords?: string[];
  minHeight?: number;
  transitionDuration?: number;
  unit?: string;
  w?: number;
  getFillColor?: (d: BaseDataType) => string;
  onContextMenu?: (e: MouseEvent, d: HierarchyNode<BaseDataType>) => void;
  onDetail?: (e: MouseEvent, d: HierarchyNode<BaseDataType>, c?: IOtherData) => void;
  onMouseDown?: (e: MouseEvent) => void;
  onMouseMove?: (e: MouseEvent, c?: IOtherData) => void;
  onMouseOut?: (e: MouseEvent) => void;
}
export interface IFlameData<D extends BaseDataType> {
  main: D;
  threads: D[];
}
export interface ILineData<D extends BaseDataType> {
  data: D;
  tag: 'from' | 'to';
  x: number;
  y: number;
}
export interface IOtherData {
  rootValue?: number;
  xAxisValue?: number;
}

export interface RootData {
  endTime: number;
  startTime: number;
}
export interface ThreadPos {
  x: number;
  y: number;
}
export const CommonMenuList: ICommonMenuItem[] = [
  {
    id: 'copy',
    name: window.i18n.t('复制函数名称'),
    icon: 'icon-mc-copy',
  },
  {
    id: 'reset',
    name: window.i18n.t('重置图表'),
    icon: 'icon-zhongzhi1',
  },
  {
    id: 'highlight',
    name: window.i18n.t('高亮相似 Node'),
    icon: 'icon-beauty',
  },
];
export interface IAxisRect {
  bottom?: number;
  left?: number;
  title?: string;
  top?: number;
  visibility?: 'hidden' | 'visible';
}
export interface IContextMenuRect {
  left: number;
  spanId: number | string;
  spanName: string;
  top: number;
}
// 用于标识根节点
export interface ITipsDetail {
  data?: number | string;
  dataText?: string;
  diffData?: number | string;
  diffDuration?: string;
  diffValue?: number | string;
  duration?: string;
  id?: number | string;
  left?: number; // 提示框左边距离画布左边的距离
  mark?: BaseDataType['diff_info']['mark'];
  proportion?: number | string;
  title?: string;
  top?: number; // 提示框上边距离画布上边的距离
}
/**
 * 表示一个缩放矩形的接口
 */
export interface IZoomRect {
  left: number; // 矩形左边距离画布左边的距离
  width: number; // 矩形的宽度
}

export const getSpanColorByName = (name: string) => {
  const palette = Object.values(ColorTypes);
  const colorIndex = getHashVal(name) % palette.length;
  return palette[colorIndex];
};
