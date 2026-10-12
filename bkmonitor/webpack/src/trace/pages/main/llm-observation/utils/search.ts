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
import type { ComputedRef, InjectionKey } from 'vue';

import { beautifyJsonValue, formatJsonDisplay, isRecord } from './helpers';
import { formatAgentLabel, parseAgentObservation } from './parse-agent';
import { parseInputObservation } from './parse-input';
import { parseOutputObservation } from './parse-output';
import { parseToolObservation } from './parse-tool';

import type { LlmInputObservation, LlmOutputObservation, LlmPlannedToolCall, LlmToolCallRecord } from './typings';

/** 页内搜索：字面量匹配、命中收集、高亮定位与 provide/inject 上下文 */

/** 命中所属页签：输入 / 输出一起搜，Tool Span 只搜工具面板，Agent 名称条始终可见 */
export type LlmSearchTab = 'agent' | 'input' | 'output' | 'tool';

/** 折叠分区 id，定位时自动展开 */
export const LLM_SEARCH_SECTION = {
  agent: 'agent',
  inputModel: 'input-model',
  inputReasoning: 'input-reasoning',
  inputSystem: 'input-system',
  inputToolCalls: 'input-tool-calls',
  inputTools: 'input-tools',
  inputUser: 'input-user',
  outputModel: 'output-model',
  outputPlanned: 'output-planned',
  outputReasoning: 'output-reasoning',
  outputResults: 'output-results',
  tool: 'tool',
} as const;

/** 高亮拆段：match 段保留原文大小写 */
export type LlmHighlightPart = {
  match: boolean;
  text: string;
};

/** 观测页搜索上下文：父级收集 hits，子组件只读后高亮 / 展开 / 定位 */
export type LlmObservationSearchContext = {
  /** 当前序号对应的命中；无关键词或无结果时为 null */
  activeHit: ComputedRef<LlmSearchHit | null>;
  /** 当前命中在 hits 中的下标，从 0 起 */
  activeIndex: ComputedRef<number>;
  /** 输入 + 输出（或 Tool 面板）按文档顺序排好的全部命中 */
  hits: ComputedRef<LlmSearchHit[]>;
  /** 用户输入原文，匹配前由收集侧 trim */
  keyword: ComputedRef<string>;
};

/** 单条命中，按输入 → 输出（或工具面板）的文档顺序编号 */
export type LlmSearchHit = {
  /** 与渲染侧 HighlightText / JsonView 对齐的锚点 */
  blockId: string;
  /** 工具调用卡片 id，定位时展开对应卡片 */
  expandId?: string;
  /** 全局序号，与搜索框 n / total 对齐 */
  index: number;
  sectionId: LlmSearchSectionId;
  tab: LlmSearchTab;
  /** 可用工具 tag 名，定位时切到该工具 */
  toolName?: string;
};

export type LlmSearchSectionId = (typeof LLM_SEARCH_SECTION)[keyof typeof LLM_SEARCH_SECTION];

export const LLM_OBSERVATION_SEARCH_KEY: InjectionKey<LlmObservationSearchContext> = Symbol('llm-observation-search');

type HitBuilder = {
  hits: LlmSearchHit[];
  pushJson: (data: unknown, rootPath: string, meta: Omit<HitMeta, 'blockId'>) => void;
  pushText: (text: string, meta: HitMeta) => void;
};

type HitMeta = Omit<LlmSearchHit, 'index'>;

/**
 * 按 vue-json-pretty 的 path 规则展开 JSON，供高亮与计数共用。
 * 标识符 key 用 `.name`，其余用 `["name"]`；数组用 `[0]`。
 */
export function collectJsonSearchTexts(data: unknown, rootPath: string): { blockId: string; text: string }[] {
  const items: { blockId: string; text: string }[] = [];

  const walk = (value: unknown, path: string, key?: string) => {
    if (key) {
      items.push({ blockId: `${path}:key`, text: key });
    }
    if (Array.isArray(value)) {
      for (const [index, item] of value.entries()) {
        walk(item, `${path}[${index}]`);
      }
      return;
    }
    if (isRecord(value)) {
      for (const childKey of Object.keys(value)) {
        walk(value[childKey], jsonChildPath(path, childKey), childKey);
      }
      return;
    }
    items.push({ blockId: `${path}:value`, text: formatJsonDisplay(value) });
  };

  walk(beautifyJsonValue(data), rootPath);
  return items;
}

/** 从 Span attributes 收集输入 + 输出（或工具面板）的全部命中 */
export function collectObservationHits(
  keyword: string,
  attributes: Record<string, unknown>,
  isTool: boolean,
  isAgent = false
): LlmSearchHit[] {
  const trimmed = keyword.trim();
  if (!trimmed) return [];

  const builder = createHitBuilder(trimmed);
  if (isTool) {
    collectToolHits(builder, parseToolObservation(attributes));
    return builder.hits;
  }

  if (isAgent) {
    collectAgentHits(builder, parseAgentObservation(attributes));
  }
  collectInputHits(builder, parseInputObservation(attributes));
  collectOutputHits(builder, parseOutputObservation(attributes));
  return builder.hits;
}

/** 统计一段文本里的命中次数 */
export function countMatches(text: string, keyword: string): number {
  if (!keyword || !text) return 0;
  return text.match(new RegExp(escapeRegExp(keyword), 'gi'))?.length ?? 0;
}

/** 转义用户输入，按字面量做大小写不敏感匹配 */
export function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * 当前命中是否落在指定文本 / JSON 块。
 * 文本块用 `prefix:field`；JSON 叶子用 vue-json-pretty path，中间是 `.` / `[` 而不是 `:`。
 */
export function isActiveHitOnBlock(hit: LlmSearchHit | null | undefined, blockId: string): boolean {
  if (!hit?.blockId || !blockId) return false;
  if (hit.blockId === blockId) return true;
  // JSON path：tool:args.user、tool:args[0].x；文本块：tool:args:field
  return (
    hit.blockId.startsWith(`${blockId}:`) ||
    hit.blockId.startsWith(`${blockId}.`) ||
    hit.blockId.startsWith(`${blockId}[`)
  );
}

/** 工具调用列表：根据命中 block 或 expandId 找到应展开的卡片 id */
export function resolveToolCallExpandId(
  hit: LlmSearchHit | null | undefined,
  searchPrefix: string,
  itemIds: string[]
): string {
  if (!hit || !searchPrefix || !itemIds.length) return '';
  if (hit.expandId && itemIds.includes(hit.expandId)) return hit.expandId;
  const matched = itemIds.find(id => isActiveHitOnBlock(hit, `${searchPrefix}:${id}`));
  return matched ?? '';
}

/** 把文本拆成「普通 / 命中」片段，命中段保留原文大小写 */
export function splitHighlightParts(text: string, keyword: string): LlmHighlightPart[] {
  if (!keyword || !text) return [{ match: false, text }];
  const reg = new RegExp(escapeRegExp(keyword), 'gi');
  const parts: LlmHighlightPart[] = [];
  let lastIndex = 0;
  let match = reg.exec(text);
  while (match) {
    if (match.index > lastIndex) {
      parts.push({ match: false, text: text.slice(lastIndex, match.index) });
    }
    parts.push({ match: true, text: match[0] });
    lastIndex = match.index + match[0].length;
    // 空串匹配会让 lastIndex 不前进，必须手动推进避免死循环
    if (!match[0].length) reg.lastIndex += 1;
    match = reg.exec(text);
  }
  if (lastIndex < text.length) {
    parts.push({ match: false, text: text.slice(lastIndex) });
  }
  return parts;
}

/** Agent 名称条在输入 / 输出页签之上，命中时不切页签 */
function collectAgentHits(builder: HitBuilder, observation: ReturnType<typeof parseAgentObservation>) {
  const label = formatAgentLabel(observation.name, observation.version);
  const meta = { sectionId: LLM_SEARCH_SECTION.agent, tab: 'agent' };
  builder.pushText(label, { ...meta, blockId: 'agent:name' });
  builder.pushText(observation.description.trim(), { ...meta, blockId: 'agent:desc' });
}

/** 输入侧：消息 / 推理 / 工具调用 / 可用工具，顺序即翻页顺序 */
function collectInputHits(builder: HitBuilder, observation: LlmInputObservation) {
  for (const item of observation.userMessages) {
    builder.pushText(item.content, {
      blockId: `input:user:${item.id}`,
      sectionId: LLM_SEARCH_SECTION.inputUser,
      tab: 'input',
    });
  }
  for (const item of observation.modelMessages) {
    builder.pushText(item.content, {
      blockId: `input:model:${item.id}`,
      sectionId: LLM_SEARCH_SECTION.inputModel,
      tab: 'input',
    });
  }
  for (const item of observation.systemPrompts) {
    builder.pushText(item.content, {
      blockId: `input:system:${item.id}`,
      sectionId: LLM_SEARCH_SECTION.inputSystem,
      tab: 'input',
    });
  }
  for (const item of observation.reasoningMessages) {
    builder.pushText(item.content, {
      blockId: `input:reasoning:${item.id}`,
      sectionId: LLM_SEARCH_SECTION.inputReasoning,
      tab: 'input',
    });
  }
  for (const item of observation.toolCalls) {
    collectToolCallHits(builder, item, `input:toolcall:${item.id}`, 'input', LLM_SEARCH_SECTION.inputToolCalls);
  }
  for (const tool of observation.availableTools) {
    const prefix = `input:tool:${tool.name}`;
    const meta = {
      sectionId: LLM_SEARCH_SECTION.inputTools,
      tab: 'input' as const,
      toolName: tool.name,
    };
    builder.pushText(tool.name.trim(), { ...meta, blockId: `${prefix}:name` });
    builder.pushText(tool.description.trim(), { ...meta, blockId: `${prefix}:desc` });
    builder.pushJson(tool.parameters, `${prefix}:params`, meta);
  }
}

/** 输出侧接在输入侧之后，定位时可能自动切到输出页签 */
function collectOutputHits(builder: HitBuilder, observation: LlmOutputObservation) {
  for (const item of observation.reasoningMessages) {
    builder.pushText(item.content, {
      blockId: `output:reasoning:${item.id}`,
      sectionId: LLM_SEARCH_SECTION.outputReasoning,
      tab: 'output',
    });
  }
  for (const item of observation.modelOutputs) {
    builder.pushText(item.content, {
      blockId: `output:model:${item.id}`,
      sectionId: LLM_SEARCH_SECTION.outputModel,
      tab: 'output',
    });
  }
  for (const item of observation.plannedToolCalls) {
    collectToolCallHits(builder, item, `output:planned:${item.id}`, 'output', LLM_SEARCH_SECTION.outputPlanned);
  }
  for (const item of observation.toolResults) {
    const prefix = `output:result:${item.id}`;
    const meta = {
      expandId: item.id,
      sectionId: LLM_SEARCH_SECTION.outputResults,
      tab: 'output' as const,
    };
    builder.pushText(item.name.trim(), { ...meta, blockId: `${prefix}:name` });
    builder.pushJson(item.result, `${prefix}:json`, meta);
  }
}

function collectToolCallHits(
  builder: HitBuilder,
  item: LlmPlannedToolCall | LlmToolCallRecord,
  prefix: string,
  tab: Extract<LlmSearchTab, 'input' | 'output'>,
  sectionId: LlmSearchSectionId
) {
  const meta = { expandId: item.id, sectionId, tab };
  builder.pushText(item.name.trim(), { ...meta, blockId: `${prefix}:name` });
  if ('description' in item) {
    builder.pushText(item.description.trim(), { ...meta, blockId: `${prefix}:desc` });
  }
  builder.pushJson(item.arguments, `${prefix}:args`, meta);
  if ('response' in item) {
    builder.pushJson(item.response, `${prefix}:resp`, meta);
  }
}

/** Tool Span 只扫描述 / 参数 / 结果，不走输入输出页签 */
function collectToolHits(builder: HitBuilder, observation: ReturnType<typeof parseToolObservation>) {
  const meta = { sectionId: LLM_SEARCH_SECTION.tool, tab: 'tool' };
  builder.pushText(observation.name.trim(), { ...meta, blockId: 'tool:name' });
  builder.pushText(observation.description.trim(), { ...meta, blockId: 'tool:desc' });
  builder.pushJson(observation.arguments, 'tool:args', meta);
  builder.pushJson(observation.result, 'tool:result', meta);
}

/** 同一段文本的多次命中共用 meta，index 取全局递增序号 */
function createHitBuilder(keyword: string): HitBuilder {
  const hits: LlmSearchHit[] = [];

  const pushText = (text: string, meta: HitMeta) => {
    const total = countMatches(text, keyword);
    for (let index = 0; index < total; index++) {
      hits.push({ ...meta, index: hits.length });
    }
  };

  const pushJson = (data: unknown, rootPath: string, meta: Omit<HitMeta, 'blockId'>) => {
    for (const item of collectJsonSearchTexts(data, rootPath)) {
      pushText(item.text, { ...meta, blockId: item.blockId });
    }
  };

  return { hits, pushJson, pushText };
}

/** 与 vue-json-pretty 展平 path 的规则对齐 */
function jsonChildPath(parentPath: string, key: string): string {
  return /^[a-zA-Z_]\w*$/.test(key) ? `${parentPath}.${key}` : `${parentPath}["${key}"]`;
}
