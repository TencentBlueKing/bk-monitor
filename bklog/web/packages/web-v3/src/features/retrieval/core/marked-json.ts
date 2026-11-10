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

// JSON 字面量扫描 + 检索高亮 <mark> 保真解析。
// 纯计算模块，不依赖 vue / DOM，可被 Worker 直接引用（与 highlight-range.ts 同约束）。

import { parseResultMarkedText, type HighlightRange } from './highlight-range';

export type JsonLiteralKind = 'primitive' | 'string';

export interface JsonLiteralSpan {
  /** 字面量内容区间：字符串不含首尾引号 */
  start: number;
  end: number;
  path: string;
  role: 'key' | 'value';
  kind: JsonLiteralKind;
}

/** 结构路径根节点；JSON 树侧必须使用同一套拼接规则才能命中侧通道 */
export const MARKED_JSON_ROOT_PATH = '$';

export const joinMarkedJsonPath = (parentPath: string, key: number | string) =>
  `${parentPath || MARKED_JSON_ROOT_PATH}.${key}`;

const unescapeJsonText = (raw: string) => {
  if (!raw.includes('\\')) return raw;
  try {
    return JSON.parse(`"${raw}"`);
  } catch {
    return raw;
  }
};

/**
 * 扫描 JSON 原文中所有 KEY / VALUE 字面量的字符区间与结构路径。
 * 与 getJsonSegmentRanges 共用，避免两套 JSON 游标实现漂移。
 * 入参必须是结构合法的 JSON 文本（不含 mark 等额外标签）。
 */
export const scanJsonLiterals = (text: string, rootPath: string = MARKED_JSON_ROOT_PATH): JsonLiteralSpan[] => {
  const spans: JsonLiteralSpan[] = [];
  let cursor = 0;

  const skipSpace = () => {
    while (/\s/.test(text[cursor] ?? '')) cursor += 1;
  };

  const readString = () => {
    const start = cursor;
    cursor += 1;
    while (cursor < text.length) {
      if (text[cursor] === '\\') {
        cursor += 2;
      } else if (text[cursor] === '"') {
        cursor += 1;
        return { start, end: cursor, contentStart: start + 1, contentEnd: cursor - 1 };
      } else {
        cursor += 1;
      }
    }
    return undefined;
  };

  const readPrimitive = () => {
    const start = cursor;
    while (cursor < text.length && !/[\s,}\]]/.test(text[cursor])) cursor += 1;
    return { start, end: cursor };
  };

  const readValue = (path: string) => {
    skipSpace();
    if (text[cursor] === '"') {
      const stringRange = readString();
      if (stringRange) {
        spans.push({
          start: stringRange.contentStart,
          end: stringRange.contentEnd,
          path,
          role: 'value',
          kind: 'string',
        });
      }
      return;
    }

    if (text[cursor] === '{') {
      cursor += 1;
      skipSpace();
      while (cursor < text.length && text[cursor] !== '}') {
        const key = readString();
        if (!key) return;
        skipSpace();
        if (text[cursor] !== ':') return;
        cursor += 1;
        const childPath = joinMarkedJsonPath(path, unescapeJsonText(text.slice(key.contentStart, key.contentEnd)));
        spans.push({
          start: key.contentStart,
          end: key.contentEnd,
          path: childPath,
          role: 'key',
          kind: 'string',
        });
        skipSpace();
        readValue(childPath);
        skipSpace();
        if (text[cursor] === ',') {
          cursor += 1;
          skipSpace();
        } else break;
      }
      if (text[cursor] === '}') cursor += 1;
      return;
    }

    if (text[cursor] === '[') {
      cursor += 1;
      let index = 0;
      skipSpace();
      while (cursor < text.length && text[cursor] !== ']') {
        readValue(joinMarkedJsonPath(path, index));
        index += 1;
        skipSpace();
        if (text[cursor] === ',') {
          cursor += 1;
          skipSpace();
        } else break;
      }
      if (text[cursor] === ']') cursor += 1;
      return;
    }

    const primitive = readPrimitive();
    if (primitive.end > primitive.start) {
      spans.push({ ...primitive, path, role: 'value', kind: 'primitive' });
    }
  };

  skipSpace();
  readValue(rootPath);
  return spans;
};

export interface PrimitiveMarkEntry {
  /** 命中的原始字面量文本，用于校验展示值是否与字面量一致 */
  literal: string;
  ranges: HighlightRange[];
}

export type PrimitiveMarkMap = Map<string, PrimitiveMarkEntry>;

export interface MarkedJsonResult {
  isJson: boolean;
  value: any;
  /** 数字 / 布尔 / null 字面量上的命中范围：无法内嵌到 JSON 文本，只能按结构路径透传 */
  primitiveMarks?: PrimitiveMarkMap;
}

const MARK_TAG_REG = /<\/?mark(?:\s[^>]*)?>/i;
// 整段 VALUE 命中时 <mark> 会包住 { / [ 本身，JSON 外观判定必须跳过前导标签
const JSON_LIKE_REG = /^\s*(?:<\/?mark(?:\s[^>]*)?>\s*)*[[{]/i;

/** 判断文本是否为 JSON 外观（允许前导检索高亮标签） */
export const isMarkedJsonLike = (value: unknown): value is string =>
  typeof value === 'string' && JSON_LIKE_REG.test(value);

/**
 * 计算字符串字面量内可安全插入标签的位置。
 * 禁止把 <mark> 插进 \" 或 \uXXXX 中间，否则回填后的文本不再是合法 JSON。
 */
const buildEscapeBoundaries = (text: string, start: number, end: number) => {
  const boundaries: number[] = [];
  let index = start;
  while (index < end) {
    boundaries.push(index);
    if (text[index] === '\\') {
      index += text[index + 1] === 'u' ? 6 : 2;
    } else {
      index += 1;
    }
  }
  boundaries.push(end);
  return boundaries;
};

const snapDown = (boundaries: number[], position: number) => {
  let result = boundaries[0];
  for (const value of boundaries) {
    if (value > position) break;
    result = value;
  }
  return result;
};

const snapUp = (boundaries: number[], position: number) => {
  for (const value of boundaries) {
    if (value >= position) return value;
  }
  return boundaries[boundaries.length - 1];
};

/** spans 按文档顺序升序，二分定位首个可能与 range 相交的字面量 */
const findFirstSpanIndex = (spans: JsonLiteralSpan[], position: number) => {
  let low = 0;
  let high = spans.length;
  while (low < high) {
    const mid = (low + high) >> 1;
    if (spans[mid].end <= position) {
      low = mid + 1;
    } else {
      high = mid;
    }
  }
  return low;
};

const addPrimitiveMark = (
  primitiveMarks: PrimitiveMarkMap,
  span: JsonLiteralSpan,
  literal: string,
  start: number,
  end: number,
) => {
  const entry = primitiveMarks.get(span.path) ?? { literal, ranges: [] };
  entry.ranges.push({ start, end });
  primitiveMarks.set(span.path, entry);
};

/**
 * 解析可能带检索高亮的 JSON 文本，且不丢弃任何 <mark>。
 *
 * 1. 原文直接可解析时原样返回：此时 mark 全部落在字符串字面量内部，高亮天然保留；
 * 2. 否则说明 mark 跨越了引号 / 冒号等结构字符，把命中区间收敛进它覆盖的 KEY/VALUE 内部后再解析；
 * 3. 数字 / 布尔 / null 字面量无法内嵌标签，命中范围按结构路径放入 primitiveMarks 供渲染层重新包裹。
 */
export const parseMarkedJson = (source: unknown, parse: (_text: string) => any = JSON.parse): MarkedJsonResult => {
  if (!isMarkedJsonLike(source)) {
    return { isJson: false, value: source };
  }

  try {
    return { isJson: true, value: parse(source) };
  } catch {
    // 继续判断是否为高亮标签导致的结构破坏
  }

  if (!MARK_TAG_REG.test(source)) {
    return { isJson: false, value: source };
  }

  const { plainText, markRanges } = parseResultMarkedText(source);
  if (!markRanges.length) {
    return { isJson: false, value: source };
  }

  let spans: JsonLiteralSpan[] = [];
  try {
    spans = scanJsonLiterals(plainText);
  } catch {
    spans = [];
  }

  const primitiveMarks: PrimitiveMarkMap = new Map();
  const insertions: Array<{ position: number; tag: string; order: number }> = [];
  const boundaryCache = new Map<number, number[]>();

  const getBoundaries = (span: JsonLiteralSpan) => {
    if (!boundaryCache.has(span.start)) {
      boundaryCache.set(span.start, buildEscapeBoundaries(plainText, span.start, span.end));
    }
    return boundaryCache.get(span.start);
  };

  for (const range of markRanges) {
    for (let index = findFirstSpanIndex(spans, range.start); index < spans.length; index += 1) {
      const span = spans[index];
      if (span.start >= range.end) break;

      const clippedStart = Math.max(span.start, range.start);
      const clippedEnd = Math.min(span.end, range.end);
      if (clippedEnd <= clippedStart) continue;

      if (span.kind === 'primitive') {
        addPrimitiveMark(
          primitiveMarks,
          span,
          plainText.slice(span.start, span.end),
          clippedStart - span.start,
          clippedEnd - span.start,
        );
        continue;
      }

      const boundaries = getBoundaries(span);
      const safeStart = snapDown(boundaries, clippedStart);
      const safeEnd = snapUp(boundaries, clippedEnd);
      if (safeEnd <= safeStart) continue;

      insertions.push({ position: safeStart, tag: '<mark>', order: 1 });
      insertions.push({ position: safeEnd, tag: '</mark>', order: 0 });
    }
  }

  const markedPrimitives = primitiveMarks.size ? primitiveMarks : undefined;

  if (insertions.length) {
    insertions.sort((a, b) => a.position - b.position || a.order - b.order);
    let repaired = '';
    let cursor = 0;
    for (const insertion of insertions) {
      repaired += plainText.slice(cursor, insertion.position) + insertion.tag;
      cursor = insertion.position;
    }
    repaired += plainText.slice(cursor);

    try {
      return { isJson: true, value: parse(repaired), primitiveMarks: markedPrimitives };
    } catch {
      // 回填后仍不可解析时降级为纯文本解析，保证层级展示不被高亮阻断
    }
  }

  try {
    return { isJson: true, value: parse(plainText), primitiveMarks: markedPrimitives };
  } catch {
    return { isJson: false, value: source };
  }
};

/** 按侧通道命中范围为标量叶子重新包裹 <mark>，供分词层映射成 resultRanges */
export const applyPrimitiveMarkText = (leafText: string, entry?: PrimitiveMarkEntry) => {
  const text = String(leafText ?? '');
  if (!entry?.ranges.length || !text) {
    return text;
  }

  if (entry.literal === text) {
    const ranges = [...entry.ranges].sort((a, b) => a.start - b.start || a.end - b.end);
    let output = '';
    let cursor = 0;
    for (const range of ranges) {
      const start = Math.max(cursor, Math.min(text.length, range.start));
      const end = Math.max(start, Math.min(text.length, range.end));
      if (end <= start) continue;
      output += `${text.slice(cursor, start)}<mark>${text.slice(start, end)}</mark>`;
      cursor = end;
    }
    return output + text.slice(cursor);
  }

  // 展示值与字面量不一致（如 1.50 展示为 1.5）：仅在整段命中时整体高亮，避免偏移错位
  const coversWholeLiteral = entry.ranges.some(range => range.start <= 0 && range.end >= entry.literal.length);
  return coversWholeLiteral ? `<mark>${text}</mark>` : text;
};

/** 把嵌套 JSON 字符串解析出的侧通道并入父级映射，路径统一加上父节点前缀 */
export const mergePrimitiveMarks = (target: PrimitiveMarkMap, parentPath: string, source?: PrimitiveMarkMap) => {
  if (!source?.size) return target;

  for (const [path, entry] of source) {
    const suffix = path.startsWith(MARKED_JSON_ROOT_PATH) ? path.slice(MARKED_JSON_ROOT_PATH.length) : path;
    target.set(`${parentPath}${suffix}`, entry);
  }

  return target;
};
