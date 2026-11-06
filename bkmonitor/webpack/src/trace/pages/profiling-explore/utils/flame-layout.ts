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

import {
  COMPARE_ADDED_COLOR,
  COMPARE_DIFF_COLOR_LIST,
  COMPARE_REMOVED_COLOR,
  getSingleDiffColor,
} from 'monitor-ui/chart-plugins/plugins/profiling-graph/flame-graph/utils';
import { getSpanColorByName } from 'monitor-ui/chart-plugins/typings/flame-graph';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import type { FlameNode, ProfileRow } from '../types';

export interface FlameFrame {
  depth: number;
  /** 布局遍历索引；后端 id 可能在不同调用路径中重复，不能用于定位焦点。 */
  key: number;
  node: FlameNode;
  parent: number;
  width: number;
  x: number;
}

/** 行内按 x 升序排列，命中区间为左闭右开；与 layoutFlame 的入栈顺序保持一致。 */
export function findFrame(row: FlameFrame[], x: number): FlameFrame | undefined {
  let left = 0;
  let right = row.length - 1;
  while (left <= right) {
    const mid = (left + right) >>> 1;
    const item = row[mid];
    if (x < item.x) right = mid - 1;
    else if (x >= item.x + item.width) left = mid + 1;
    else return item;
  }
}

/** 迭代后序计算宽度，避免深调用栈递归；对比独有节点也占有可见宽度。 */
export function layoutFlame(root: FlameNode | undefined): { frames: FlameFrame[]; rows: FlameFrame[][] } {
  if (!root?.name) return { frames: [], rows: [] };
  const nodes: { children: number[]; node: FlameNode; parent: number; weight: number }[] = [];
  const pending = [{ node: root, parent: -1 }];
  while (pending.length) {
    const { node, parent } = pending.pop();
    const index = nodes.length;
    nodes.push({ node, parent, children: [], weight: Math.max(0, node.value || 0) });
    if (parent >= 0) nodes[parent].children.push(index);
    const children = node.children || [];
    for (let i = children.length - 1; i >= 0; i--) pending.push({ node: children[i], parent: index });
  }
  for (let i = nodes.length - 1; i >= 0; i--) {
    const item = nodes[i];
    // 子节点合计可能大于父值，扩大布局权重保证子节点容纳得下；不修改用于展示的原值。
    item.weight = Math.max(
      item.weight,
      item.children.reduce((sum, child) => sum + nodes[child].weight, 0)
    );
  }
  const frames: FlameFrame[] = [];
  const rows: FlameFrame[][] = [];
  const positions = [{ index: 0, x: 0, width: 1, depth: 0 }];
  while (positions.length) {
    const position = positions.pop();
    const { index, x, width, depth } = position;
    const item = nodes[index];
    const frame = { key: index, node: item.node, x, width, depth, parent: item.parent };
    frames[index] = frame;
    (rows[depth] ||= []).push(frame);
    let offset = x;
    const children = item.children.map(child => {
      const childWidth = item.weight > 0 ? (width * nodes[child].weight) / item.weight : 0;
      const result = { index: child, x: offset, width: childWidth, depth: depth + 1 };
      offset += childWidth;
      return result;
    });
    for (let i = children.length - 1; i >= 0; i--) positions.push(children[i]);
  }
  return { frames, rows };
}

export const diffLegend = [
  { label: 'added', color: COMPARE_ADDED_COLOR },
  ...COMPARE_DIFF_COLOR_LIST.map(item => ({ label: `${item.value > 0 ? '+' : ''}${item.value}%`, color: item.color })),
  { label: 'removed', color: COMPARE_REMOVED_COLOR },
];

export function diffTextColor(row: Partial<FlameNode['diff_info']>): string {
  if (row.mark === 'added') return '#2dcb56';
  if (row.mark === 'removed') return '#ff5656';
  return row.diff === 0 ? '#dddfe3' : row.diff > 0 ? '#ff5656' : '#2dcb56';
}

export function formatDiff(row: Partial<FlameNode['diff_info']>): string {
  if (row.mark === 'added') return 'added';
  if (row.mark === 'removed') return 'removed';
  return row.diff == null ? '--' : row.diff === 0 ? '0%' : `${(row.diff * 100).toFixed(2)}%`;
}

export function formatProfileValue(value: number, unit = ''): string {
  if (!Number.isFinite(value)) return '--';
  if (!unit || unit === 'count') return String(value);
  const normalized = unit === 'nanoseconds' ? 'ns' : unit === 'seconds' ? 's' : unit;
  const formatted = getValueFormat(normalized)(value);
  return `${formatted.text}${formatted.suffix || ''}`;
}

export function formatProportion(value: number, total: number): string {
  return total > 0 ? `${Number(((value / total) * 100).toFixed(4))}%` : '--';
}

export function frameColor(name: string, diff?: FlameNode['diff_info']): string {
  return diff ? getSingleDiffColor(diff) : getSpanColorByName(name);
}

export function rowValue(row: ProfileRow, field: string): number {
  return field === 'total' ? (row.total ?? row.value ?? 0) : (row[field] ?? 0);
}
