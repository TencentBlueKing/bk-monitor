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

// 分词属于纯文本计算，需在 Worker 内可用，因此与 hooks-helper 的 DOM 工具分离。
import {
  mapGlobalRangesToSegments,
  parseResultMarkedText,
} from '@/views/retrieve-core/highlight-range';

/**
 *
 * @param str
 * @param delimiterPattern
 * @param wordsplit 是否分词
 * @returns
 */
export const optimizedSplit = (str: string, delimiterPattern: string, wordsplit = true) => {
  if (!str) {
    return [];
  }

  // 先剥离 <mark> 再分词，避免高亮标签破坏 token 边界；高亮范围再映射回各 token。
  const { plainText, markRanges } = parseResultMarkedText(str);
  if (!plainText) {
    return [];
  }

  const tokens: Record<string, any>[] = [];
  let processedLength = 0;
  const CHUNK_SIZE = 200;

  if (wordsplit) {
    const MAX_TOKENS = 500;
    // 转义特殊字符，并构建用于分割的正则表达式
    const regexPattern = delimiterPattern
      .split('')
      .map(delimiter => `\\${delimiter}`)
      .join('|');

    const DELIMITER_REGEX = new RegExp(`(${regexPattern})`);
    const segmentSplitList = plainText.split(DELIMITER_REGEX).filter(Boolean);
    const normalTokens = segmentSplitList.slice(0, MAX_TOKENS);

    for (const t of normalTokens) {
      processedLength += t.length;
      tokens.push({
        text: t,
        isMark: false,
        isCursorText: !DELIMITER_REGEX.test(t),
      });
    }
  }

  if (processedLength < plainText.length) {
    const remaining = plainText.slice(processedLength);
    const chunkCount = Math.ceil(remaining.length / CHUNK_SIZE);
    for (let i = 0; i < chunkCount; i++) {
      tokens.push({
        text: remaining.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE),
        isMark: false,
        isCursorText: false,
        isBlobWord: false,
      });
    }
  }

  if (!markRanges.length) {
    return tokens.map(token => ({ ...token, resultRanges: [] }));
  }

  const perTokenRanges = mapGlobalRangesToSegments(tokens, markRanges, false);
  return tokens.map((token, index) => {
    const resultRanges = perTokenRanges[index] ?? [];
    return {
      ...token,
      isMark: resultRanges.length > 0,
      resultRanges,
    };
  });
};
