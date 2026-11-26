import { formatCompactToken } from './helpers';

import type { SpanLlmTokenMatrixNode } from '../../../../components/trace-view/typings';

/** 与 Trace 详情 llm_detail.token_matrix 复用同一节点结构 */
export type LlmTokenMatrixNode = SpanLlmTokenMatrixNode;

export type LlmMatrixNodeKind = 'container' | 'leaf' | 'pane' | 'tools';

export interface LlmMatrixViewNode {
  call_count?: number;
  children: LlmMatrixViewNode[];
  color: string;
  id: string;
  kind: LlmMatrixNodeKind;
  name: string;
  percent: number;
  value: number;
}

const TOOL_LEAF_PREFIX = 'tool_calls/tool/';
const TOOL_OTHER_ID = 'tool_calls/other';
const PANE_IDS = new Set(['input', 'output']);
const CONTAINER_IDS = new Set(['conversation', 'context']);
const TOOLS_ID = 'tool_calls';

/** 按节点 id 对齐设计稿色板；未登记 id 回退浅灰 */
const NODE_COLORS: Record<string, string> = {
  system: '#ECF0F7',
  definitions: '#E9F2D8',
  tool_calls: '#E1F5F0',
  [TOOL_OTHER_ID]: '#D8EAE0',
  model: '#EAE6FF',
  user: '#E4F5FF',
  content: '#FFF0E1',
  reasoning: '#E9EDFF',
};

/** id 是否属于 `tool_calls/tool/*` 形式的工具叶子节点 */
export function isToolLeafId(id: string): boolean {
  return id.startsWith(TOOL_LEAF_PREFIX);
}

/** 从工具叶子 id 还原工具名；非工具叶子返回空串 */
export function decodeToolNameFromId(id: string): string {
  if (!isToolLeafId(id)) return '';
  const encoded = id.slice(TOOL_LEAF_PREFIX.length);
  try {
    return decodeURIComponent(encoded);
  } catch {
    return encoded;
  }
}

/** 按 id 合并多棵矩阵树；有子节点时父 value 取子节点之和 */
export function mergeTokenMatrixNodes(groups: LlmTokenMatrixNode[][]): LlmTokenMatrixNode[] {
  const root = new Map<string, LlmTokenMatrixNode>();
  for (const nodes of groups) {
    for (const node of nodes) mergeInto(root, node);
  }
  return [...root.values()].map(recomputeValue);
}

/** 按节点 id 路径逐层下钻取节点 value；路径缺失或非叶子时返回 undefined */
export function pickMatrixTokenValue(nodes: LlmTokenMatrixNode[], path: string[]): number | undefined {
  let list = nodes;
  let current: LlmTokenMatrixNode | undefined;
  for (const id of path) {
    current = list.find(node => node.id === id);
    if (!current) return undefined;
    list = Array.isArray(current.children) ? current.children : [];
  }
  return current ? Math.max(0, current.value || 0) : undefined;
}

/** 顶层按 id 拆成输入 / 输出两栏；百分比分母为两侧 value 之和 */
export function splitTokenMatrixPanes(nodes: LlmTokenMatrixNode[]): {
  input?: LlmTokenMatrixNode;
  output?: LlmTokenMatrixNode;
  total: number;
} {
  const input = nodes.find(node => node.id === 'input');
  const output = nodes.find(node => node.id === 'output');
  const total = (input ? Math.max(0, input.value || 0) : 0) + (output ? Math.max(0, output.value || 0) : 0);
  return { input, output, total };
}

/** 后端矩阵节点 → 视图节点：补百分比 / 颜色 / 类型，并递归裁剪 value 为 0 的分支 */
export function toMatrixViewNode(node: LlmTokenMatrixNode, parentValue?: number): LlmMatrixViewNode {
  const children = Array.isArray(node.children) ? node.children : [];
  const value = Math.max(0, node.value || 0);
  const total = parentValue ?? value;
  const kind = resolveKind(node.id, children);
  return {
    id: node.id,
    name: node.name,
    value,
    percent: total > 0 ? (value / total) * 100 : 0,
    kind,
    color: resolveColor(node.id, kind),
    ...(node.call_count != null ? { call_count: node.call_count } : {}),
    // value 为 0 的子节点不渲染也不占位，仅保留 >0 的分支
    children: children
      .filter(child => Math.max(0, child.value || 0) > 0)
      .map(child => toMatrixViewNode(child, value)),
  };
}

/** 百分比展示：无效 / ≤0 归零，小于 1% 收敛为 `<1%`，其余四舍五入取整 */
export function formatMatrixPercent(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '0%';
  if (value < 1) return '<1%';
  return `${Math.round(value)}%`;
}

/** 悬浮提示文案：`名称 ×次数  Token 数（百分比）`，无次数时省略 */
export function formatMatrixTooltip(node: Pick<LlmMatrixViewNode, 'call_count' | 'name' | 'percent' | 'value'>): string {
  const count = node.call_count != null ? ` ×${node.call_count}` : '';
  return `${node.name || ''}${count}  ${formatCompactToken(node.value || 0)}（${formatMatrixPercent(node.percent)}）`;
}

/** 布局权重：value 至少为 1，避免 0 值条目在 flex 布局中塌缩不可见 */
export function flexWeight(node: LlmMatrixViewNode): number {
  return Math.max(node.value, 1);
}

/** 由 id / 子节点判定视图类型：input·output 为 pane，tool_calls 为 tools，其余有子节点或已知容器为 container */
function resolveKind(id: string, children: LlmTokenMatrixNode[]): LlmMatrixNodeKind {
  if (PANE_IDS.has(id)) return 'pane';
  if (id === TOOLS_ID) return 'tools';
  if (CONTAINER_IDS.has(id) || children.length) return 'container';
  return 'leaf';
}

/** 容器 / 分栏用白色底；叶子按 id 取色板，工具叶子回退 tool_calls 色，未登记 id 回退浅灰 */
function resolveColor(id: string, kind: LlmMatrixNodeKind): string {
  if (kind === 'pane' || kind === 'container') return '#FFFFFF';
  return NODE_COLORS[id] || (isToolLeafId(id) ? NODE_COLORS.tool_calls : '#F0F4FA');
}

/**
 * 按 id 将 node 合并进 map：新 id 直接深拷贝落库；已存在则累加 call_count，
 * 并将 children 递归合并。仅当合并结果无子节点时才累加叶子 value（有子节点时 value 由 recomputeValue 汇总）。
 */
function mergeInto(map: Map<string, LlmTokenMatrixNode>, node: LlmTokenMatrixNode) {
  const current = map.get(node.id);
  if (!current) {
    map.set(node.id, cloneNode(node));
    return;
  }
  if (node.call_count != null || current.call_count != null) {
    current.call_count = (current.call_count || 0) + (node.call_count || 0);
  }
  const childMap = new Map((current.children || []).map(child => [child.id, child]));
  for (const child of node.children || []) mergeInto(childMap, child);
  current.children = [...childMap.values()];
  if (!current.children.length) {
    current.value = (current.value || 0) + (node.value || 0);
  }
}

/** 深拷贝节点，避免合并时污染接口返回的原始对象 */
function cloneNode(node: LlmTokenMatrixNode): LlmTokenMatrixNode {
  return {
    id: node.id,
    name: node.name,
    value: node.value || 0,
    children: (node.children || []).map(cloneNode),
    ...(node.call_count != null ? { call_count: node.call_count } : {}),
  };
}

/** 自底向上重算 value：有子节点时取子节点之和，叶子保持原值（不小于 0） */
function recomputeValue(node: LlmTokenMatrixNode): LlmTokenMatrixNode {
  const children = (node.children || []).map(recomputeValue);
  const childSum = children.reduce((sum, child) => sum + child.value, 0);
  return {
    ...node,
    children,
    value: children.length ? childSum : Math.max(0, node.value || 0),
  };
}
