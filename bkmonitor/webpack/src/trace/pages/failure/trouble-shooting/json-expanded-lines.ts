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

/** 通用事件 JSON 预览最多展示的展开行数，超出则显示「查看完整」 */
export const GENERAL_EVENT_MAX_EXPANDED_LINES = 7;

const isObject = (value: unknown): value is object => value !== null && typeof value === 'object';

/**
 * 判断 JSON 完全展开后的行数是否超过上限。
 * 行数口径对齐 vue-json-pretty flatten：objectStart / arrayStart / 叶子 / objectEnd / arrayEnd 各占 1 行。
 * 根节点的 `{` / `}` 或 `[` / `]` 不计入，以保持「7 个顶层原始字段」不展示按钮。
 * 一旦超过 max 立即返回，避免无意义的全量递归。
 */
export const isExpandedJsonOverLineLimit = (
  data: unknown,
  max = GENERAL_EVENT_MAX_EXPANDED_LINES
): boolean => {
  if (!isObject(data)) {
    return false;
  }

  let count = 0;
  const seen = new WeakSet<object>();

  const exceed = (): boolean => {
    count += 1;
    return count > max;
  };

  const walk = (value: unknown, isRoot: boolean): boolean => {
    if (!isObject(value)) {
      return exceed();
    }
    if (seen.has(value)) {
      return exceed();
    }
    seen.add(value);

    if (Array.isArray(value)) {
      if (!isRoot && exceed()) {
        return true;
      }
      for (const item of value) {
        if (walk(item, false)) {
          return true;
        }
      }
      return !isRoot && exceed();
    }

    if (!isRoot && exceed()) {
      return true;
    }
    for (const key of Object.keys(value as Record<string, unknown>)) {
      const child = (value as Record<string, unknown>)[key];
      if (isObject(child)) {
        if (walk(child, false)) {
          return true;
        }
      } else if (exceed()) {
        return true;
      }
    }
    return !isRoot && exceed();
  };

  return walk(data, true);
};
