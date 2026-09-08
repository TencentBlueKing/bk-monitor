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
import { scanJsonLiterals } from '@/views/retrieve-core/marked-json';

export type JsonSegmentRange = {
  start: number;
  end: number;
  fieldName: string;
  role?: 'key' | 'value';
};

/**
 * 解析 JSON 原文中 KEY/VALUE 的字符区间与字段路径。
 * KEY 绑定自身完整路径（与 use-json-formatter 历史行为一致），供截断尾巴偏移回落使用。
 * 游标扫描复用 retrieve-core/marked-json 的 scanJsonLiterals，避免两套实现漂移。
 */
export const getJsonSegmentRanges = (text: string, rootFieldName: string): JsonSegmentRange[] => {
  try {
    const parsed = JSON.parse(text);
    if (parsed === null || typeof parsed !== 'object') return [];
  } catch {
    return [];
  }

  return scanJsonLiterals(text, rootFieldName).map(span => ({
    start: span.start,
    end: span.end,
    fieldName: span.path,
    role: span.role,
  }));
};

/** 在 ranges 中查找覆盖指定字符偏移的 KEY/VALUE 区间 */
export const findJsonSegmentRangeAtOffset = (
  ranges: JsonSegmentRange[],
  offset: number,
): JsonSegmentRange | undefined => {
  if (!ranges.length || offset < 0) {
    return undefined;
  }
  return (
    ranges.find(item => offset >= item.start && offset < item.end) ??
    ranges.find(item => offset >= item.start && offset <= item.end)
  );
};
