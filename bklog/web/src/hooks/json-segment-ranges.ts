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

export type JsonSegmentRange = {
  start: number;
  end: number;
  fieldName: string;
  role?: 'key' | 'value';
};

/**
 * 解析 JSON 原文中 KEY/VALUE 的字符区间与字段路径。
 * KEY 绑定自身完整路径（与 use-json-formatter 历史行为一致），供截断尾巴偏移回落使用。
 */
export const getJsonSegmentRanges = (text: string, rootFieldName: string): JsonSegmentRange[] => {
  const ranges: JsonSegmentRange[] = [];
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
        ranges.push({
          start: stringRange.contentStart,
          end: stringRange.contentEnd,
          fieldName: path,
          role: 'value',
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
        const childPath = `${path}.${text.slice(key.contentStart, key.contentEnd)}`;
        ranges.push({
          start: key.contentStart,
          end: key.contentEnd,
          fieldName: childPath,
          role: 'key',
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
        readValue(`${path}.${index}`);
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
      ranges.push({ ...primitive, fieldName: path, role: 'value' });
    }
  };

  try {
    const parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== 'object') return [];
    skipSpace();
    readValue(rootFieldName);
  } catch {
    return [];
  }
  return ranges;
};

/** 在 ranges 中查找覆盖指定字符偏移的 KEY/VALUE 区间 */
export const findJsonSegmentRangeAtOffset = (
  ranges: JsonSegmentRange[],
  offset: number,
): JsonSegmentRange | undefined => {
  if (!ranges.length || offset < 0) {
    return undefined;
  }
  return ranges.find(item => offset >= item.start && offset < item.end)
    ?? ranges.find(item => offset >= item.start && offset <= item.end);
};
