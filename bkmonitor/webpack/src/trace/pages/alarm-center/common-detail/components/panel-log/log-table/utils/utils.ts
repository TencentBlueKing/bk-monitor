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
    const MARK_REGEX = /<mark>(.*?)<\/mark>/gis;

    const segments = str.split(/(<mark>.*?<\/mark>)/gi);

    for (const segment of segments) {
      if (tokens.length >= MAX_TOKENS) {
        break;
      }
      const isMark = MARK_REGEX.test(segment);

      const segmengtSplitList = segment.replace(MARK_REGEX, '$1').split(DELIMITER_REGEX).filter(Boolean);
      const normalTokens = segmengtSplitList.slice(0, MAX_TOKENS - tokens.length);

      if (isMark) {
        processedLength += '<mark>'.length;

        if (normalTokens.length === segmengtSplitList.length) {
          processedLength += '</mark>'.length;
        }
      }

      for (const t of normalTokens) {
        processedLength += t.length;
        tokens.push({
          text: t,
          isMark,
          isCursorText: !DELIMITER_REGEX.test(t),
        });
      }
    }
  }

  if (processedLength < str.length) {
    const remaining = str.slice(processedLength);

    const segments = remaining.split(/(<mark>.*?<\/mark>)/gi);
    for (const segment of segments) {
      const MARK_REGEX = /<mark>(.*?)<\/mark>/gis;
      const isMark = MARK_REGEX.test(segment);
      const chunkCount = Math.ceil(segment.length / CHUNK_SIZE);

      if (isMark) {
        tokens.push({
          text: segment.replace(MARK_REGEX, '$1'),
          isMark: true,
          isCursorText: false,
          isBlobWord: false,
        });
      } else {
        for (let i = 0; i < chunkCount; i++) {
          tokens.push({
            text: segment.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE),
            isMark: false,
            isCursorText: false,
            isBlobWord: false,
          });
        }
      }
    }
  }

  return tokens;
};

export const isNestedField = (fieldKeys, obj) => {
  if (!obj) {
    return false;
  }

  if (fieldKeys.length > 1) {
    if (obj[fieldKeys[0]] !== undefined && obj[fieldKeys[0]] !== null) {
      if (typeof obj[fieldKeys[0]] === 'object') {
        if (Array.isArray(obj[fieldKeys[0]])) {
          return true;
        }

        return isNestedField(fieldKeys.slice(1), obj[fieldKeys[0]]);
      }

      return false;
    }

    if (obj[fieldKeys[0]] === undefined) {
      return isNestedField([`${fieldKeys[0]}.${fieldKeys[1]}`, ...fieldKeys.slice(2)], obj);
    }
  }

  return false;
};
