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
import type { LlmTextItem } from './typings';

/** LLM 观测通用解析 / 展示工具 */

/**
 * @description 解析后递归展开对象 / 数组里看起来像 JSON 的字符串，便于展示美化
 */
export function beautifyJsonValue(value: unknown, depth = 0): unknown {
  const parsed = parseJsonValue(value);
  if (depth > 10) return parsed;
  if (typeof parsed === 'string') {
    const trimmed = parsed.trim();
    const looksLikeJson = trimmed.startsWith('{') || trimmed.startsWith('[');
    if (!looksLikeJson) return parsed;
    const nested = parseJsonValue(parsed);
    if (nested === parsed || (typeof nested !== 'object' && nested !== null)) return parsed;
    return beautifyJsonValue(nested, depth + 1);
  }
  if (Array.isArray(parsed)) {
    return parsed.map(item => beautifyJsonValue(item, depth + 1));
  }
  if (isRecord(parsed)) {
    return Object.fromEntries(Object.entries(parsed).map(([key, val]) => [key, beautifyJsonValue(val, depth + 1)]));
  }
  return parsed;
}

/**
 * @description 将 Token 数量格式化为千分位文本
 */
export function formatTokenCount(value: number): string {
  return value.toLocaleString('en-US');
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

/** 是否为普通对象（排除数组 / null） */
export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/**
 * @description 尽力解析 JSON：标准 parse → 修复字符串内裸控制字符 / 尾逗号后再 parse；失败返回原值
 */
export function parseJsonValue(value: unknown): unknown {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim().replace(/^\uFEFF/, '');
  if (!trimmed) return value;
  const parsed = tryParseJsonText(trimmed);
  if (!parsed.ok) return value;
  return typeof parsed.value === 'string' ? parseJsonValue(parsed.value) : parsed.value;
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
export function toJsonPrettyData(value: unknown): Record<string, unknown> | unknown[] {
  const parsed = beautifyJsonValue(value);
  if (Array.isArray(parsed)) return parsed;
  if (isRecord(parsed)) return parsed;
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

function escapeJsonControlChar(ch: string): string {
  if (ch === '\n') return '\\n';
  if (ch === '\r') return '\\r';
  if (ch === '\t') return '\\t';
  return `\\u${ch.charCodeAt(0).toString(16).padStart(4, '0')}`;
}

/** 将 JSON 字符串字面量中的裸控制字符转义，并去掉对象 / 数组尾逗号 */
function repairJsonText(text: string): string {
  let result = '';
  let inString = false;
  let escaped = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inString) {
      if (escaped) {
        result += ch;
        escaped = false;
        continue;
      }
      if (ch === '\\') {
        result += ch;
        escaped = true;
        continue;
      }
      if (ch === '"') {
        result += ch;
        inString = false;
        continue;
      }
      if (ch.charCodeAt(0) <= 0x1f || ch === '\u2028' || ch === '\u2029') {
        result += escapeJsonControlChar(ch);
        continue;
      }
      result += ch;
      continue;
    }

    if (ch === '"') {
      inString = true;
      result += ch;
      continue;
    }

    if (ch === ',') {
      let next = i + 1;
      while (next < text.length && /[ \t\r\n]/.test(text[next])) next++;
      if (text[next] === '}' || text[next] === ']') continue;
    }

    result += ch;
  }

  return result;
}

/** 转有限数字，无法转换时返回 undefined */
function toFiniteNumber(value: unknown): number | undefined {
  if (value == null || value === '') return undefined;
  const num = Number(value);
  return Number.isFinite(num) ? num : undefined;
}

function tryParseJsonText(text: string): { ok: false } | { ok: true; value: unknown } {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    const repaired = repairJsonText(text);
    if (repaired === text) return { ok: false };
    try {
      return { ok: true, value: JSON.parse(repaired) };
    } catch {
      return { ok: false };
    }
  }
}
