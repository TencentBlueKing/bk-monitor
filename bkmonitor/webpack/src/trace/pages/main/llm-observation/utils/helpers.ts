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
import type { LlmObservationKind, LlmTextItem } from './typings';

/** LLM 观测通用解析 / 展示工具 */

/** 模型类 operation.name */
const MODEL_OPERATIONS = new Set(['chat', 'generate_content', 'text_completion', 'fetch_response', 'embeddings']);
/** 工具类 operation.name */
const TOOL_OPERATIONS = new Set(['execute_tool']);
/** Agent 类 operation.name */
const AGENT_OPERATIONS = new Set(['invoke_workflow', 'create_agent', 'invoke_agent', 'plan']);

/**
 * @description 将 Token 数量格式化为千分位文本
 */
export function formatTokenCount(value: number): string {
  return value.toLocaleString('en-US');
}

/**
 * @description 按 gen_ai.operation.name 区分模型 / 工具 / Agent 页面，未知值按模型页展示
 */
export function getObservationKind(attributes: Record<string, unknown>): LlmObservationKind {
  const name = String(getByPath(attributes, 'gen_ai.operation.name') || '')
    .trim()
    .toLowerCase();
  if (TOOL_OPERATIONS.has(name)) return 'tool';
  if (AGENT_OPERATIONS.has(name)) return 'agent';
  if (MODEL_OPERATIONS.has(name)) return 'model';
  return 'model';
}

/**
 * @description 按路径读取属性，兼容扁平 key（如 gen_ai.tool.name）与嵌套对象
 */
export function getByPath(source: unknown, path: string): unknown {
  if (!source || typeof source !== 'object') return undefined;
  const record = source as Record<string, unknown>;
  if (path in record) return record[path];
  return path.split('.').reduce<unknown>((acc, key) => {
    if (!acc || typeof acc !== 'object') return undefined;
    return (acc as Record<string, unknown>)[key];
  }, source);
}

/**
 * @description 从 Span 原始数据提取 attributes，兼容数组与对象两种后端结构
 */
export function getSpanAttributes(originalData: null | Record<string, unknown>): Record<string, unknown> {
  if (!originalData) return {};
  const attrs = originalData.attributes;
  if (Array.isArray(attrs)) {
    return attrs.reduce<Record<string, unknown>>((acc, item) => {
      if (!item || typeof item !== 'object') return acc;
      const rec = item as Record<string, unknown>;
      if (rec.key == null) return acc;
      const queryValue = rec.query_value;
      acc[String(rec.key)] =
        Array.isArray(queryValue) || (queryValue && typeof queryValue === 'object')
          ? queryValue
          : (rec.value ?? queryValue);
      return acc;
    }, {});
  }
  if (attrs && typeof attrs === 'object') {
    return attrs as Record<string, unknown>;
  }
  return {};
}

/** 是否为普通对象（排除数组 / null） */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * @description 递归解析 JSON 字符串；解析失败则返回原值
 */
export function parseJsonValue(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  try {
    const parsed = JSON.parse(trimmed);
    return typeof parsed === 'string' ? parseJsonValue(parsed) : parsed;
  } catch {
    return value;
  }
}

/**
 * @description 按候选 key 依次取值，返回第一个可解析为数组的结果
 */
export function pickList(source: Record<string, unknown>, keys: string[]): unknown[] {
  for (const key of keys) {
    const parsed = parseJsonValue(getByPath(source, key));
    if (Array.isArray(parsed)) return parsed;
  }
  return [];
}

/**
 * @description 按候选 key 依次取值，返回第一个有限数字，找不到则返回 0
 */
export function pickNumber(source: Record<string, unknown>, keys: string[]): number {
  for (const key of keys) {
    const num = toFiniteNumber(getByPath(source, key));
    if (num !== undefined) return num;
  }
  return 0;
}

/**
 * @description 将任意值转成可展示文本；对象使用缩进 JSON
 */
export function stringifyContent(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/**
 * @description 转成 vue-json-pretty 可渲染的对象；标量包一层 { value }
 */
export function toJsonPrettyData(value: unknown): object {
  const parsed = parseJsonValue(value);
  if (parsed && typeof parsed === 'object') return parsed;
  return { value: parsed ?? '' };
}

/**
 * @description 将任意值转成文本条目；空内容返回 null
 */
export function toTextItem(id: string, value: unknown): LlmTextItem | null {
  const content = stringifyContent(value).trim();
  if (!content) return null;
  return { id, content };
}

/** 转有限数字，无法转换时返回 undefined */
function toFiniteNumber(value: unknown): number | undefined {
  if (value == null || value === '') return undefined;
  const num = Number(value);
  return Number.isFinite(num) ? num : undefined;
}
