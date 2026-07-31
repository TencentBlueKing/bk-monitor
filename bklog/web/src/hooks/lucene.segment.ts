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
import {
  mapGlobalRangesToSegments,
  parseResultMarkedText,
  type HighlightRange,
} from '@/views/retrieve-core/page-highlight';

export type LuceneSegmentToken = {
  text: string;
  isMark: boolean;
  isCursorText: boolean;
  resultRanges?: HighlightRange[];
};

export default class LuceneSegment {
  /**
   * 拆分字符串。
   * 检索/划词 <mark> 仅用于高亮范围映射，不作为分词边界。
   */
  static split(input: string, MAX_TOKENS: number): LuceneSegmentToken[] {
    const { plainText, markRanges } = parseResultMarkedText(input);
    if (!plainText) {
      return [];
    }

    const tokens = LuceneSegment.processBuffer(plainText, MAX_TOKENS, 0);
    if (tokens.length === 0) {
      return [];
    }

    // MAX_TOKENS 截断后的剩余纯文本整体追加（与历史行为一致）
    const processedLength = tokens.map(t => t.text).join('').length;
    if (processedLength < plainText.length) {
      tokens.push({
        text: plainText.slice(processedLength),
        isMark: false,
        isCursorText: false,
      });
    }

    if (!markRanges.length) {
      return tokens.map(token => ({ ...token, isMark: false, resultRanges: [] }));
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
  }

  /**
   * 判断字符是否为 MidLetter（如:）
   */
  private static isMidLetter(c: string): boolean {
    return c === ':';
  }

  /**
   * 判断字符是否为 MidNumLet（如.）
   */
  private static isMidNumLet(c: string): boolean {
    return c === '.';
  }

  /**
   * 判断字符是否为 MidNum（如,）
   */
  private static isMidNum(c: string): boolean {
    return c === ',';
  }

  /**
   * 判断字符是否为 ExtendNumLet（如_）
   */
  private static isExtendNumLet(c: string): boolean {
    return c === '_';
  }

  /**
   * 判断字符是否为字母
   */
  private static isLetter(c: string): boolean {
    return /^[a-zA-Z]$/.test(c);
  }

  /**
   * 判断字符是否为数字
   */
  private static isNumber(c: string): boolean {
    return /^[0-9]$/.test(c);
  }

  /**
   * 判断 Mid 字符是否能作为当前词元的一部分
   * @param c 当前字符
   * @param prev 前一个字符
   * @param next 后一个字符
   */
  private static canBePartOfToken(c: string, prev: null | string, next: null | string): boolean {
    if (LuceneSegment.isMidLetter(c)) {
      return Boolean(prev && next && LuceneSegment.isLetter(prev) && LuceneSegment.isLetter(next));
    }
    if (LuceneSegment.isMidNumLet(c)) {
      return Boolean(
        prev &&
          next &&
          ((LuceneSegment.isLetter(prev) && LuceneSegment.isLetter(next)) ||
            (LuceneSegment.isNumber(prev) && LuceneSegment.isNumber(next))),
      );
    }
    if (LuceneSegment.isMidNum(c)) {
      return Boolean(prev && next && LuceneSegment.isNumber(prev) && LuceneSegment.isNumber(next));
    }
    return false;
  }

  /**
   * 处理普通文本的分词逻辑，遵循 StandardTokenizer 的 Mid 规则
   */
  private static processBuffer(
    buffer: string,
    MAX_TOKENS: number,
    currentTokenCount: number,
  ): LuceneSegmentToken[] {
    const result: LuceneSegmentToken[] = [];
    let currentToken = '';
    let currentMidSequence = false;
    for (let i = 0; i < buffer.length; i++) {
      const c = buffer[i];
      const prev = i > 0 ? buffer[i - 1] : null;
      const next = i < buffer.length - 1 ? buffer[i + 1] : null;

      // ExtendNumLet（_）不切分，直接加入 token
      if (LuceneSegment.isExtendNumLet(c)) {
        currentToken += c;
        currentMidSequence = false;
        continue;
      }

      // 处理 Mid 字符
      if (LuceneSegment.isMidLetter(c) || LuceneSegment.isMidNumLet(c) || LuceneSegment.isMidNum(c)) {
        // 连续 Mid 字符触发切分
        if (currentMidSequence === true) {
          if (currentToken !== '') {
            result.push({ text: currentToken, isMark: false, isCursorText: true });
            if (result.length + currentTokenCount >= MAX_TOKENS) {
              return result;
            }
          }
          // 分词符号本身也要保留，isCursorText: false
          result.push({ text: c, isMark: false, isCursorText: false });
          if (result.length + currentTokenCount >= MAX_TOKENS) {
            return result;
          }
          currentToken = '';
          currentMidSequence = true;
          continue;
        }
        currentMidSequence = true;
        // 检查是否满足连接条件
        const keepAsPartOfToken = LuceneSegment.canBePartOfToken(c, prev, next);
        if (keepAsPartOfToken) {
          currentToken += c;
        } else {
          if (currentToken !== '') {
            result.push({ text: currentToken, isMark: false, isCursorText: true });
            if (result.length + currentTokenCount >= MAX_TOKENS) {
              return result;
            }
          }
          // 分词符号本身也要保留，isCursorText: false
          result.push({ text: c, isMark: false, isCursorText: false });
          if (result.length + currentTokenCount >= MAX_TOKENS) {
            return result;
          }
          currentToken = '';
        }
      } else if (c === '-' || c === ' ' || c === '\t') {
        // 其它常见分隔符
        if (currentToken !== '') {
          result.push({ text: currentToken, isMark: false, isCursorText: true });
          if (result.length + currentTokenCount >= MAX_TOKENS) {
            return result;
          }
        }
        result.push({ text: c, isMark: false, isCursorText: false });
        if (result.length + currentTokenCount >= MAX_TOKENS) {
          return result;
        }
        currentToken = '';
        currentMidSequence = false;
      } else {
        // 非 Mid 字符结束连续 Mid 序列
        currentMidSequence = false;
        if (LuceneSegment.isLetter(c) || LuceneSegment.isNumber(c)) {
          currentToken += c;
        } else {
          // 其它所有符号都要保留，isCursorText: false
          if (currentToken !== '') {
            result.push({ text: currentToken, isMark: false, isCursorText: true });
            if (result.length + currentTokenCount >= MAX_TOKENS) {
              return result;
            }
            currentToken = '';
          }
          result.push({ text: c, isMark: false, isCursorText: false });
          if (result.length + currentTokenCount >= MAX_TOKENS) {
            return result;
          }
        }
      }
    }
    if (currentToken !== '') {
      result.push({ text: currentToken, isMark: false, isCursorText: true });
    }
    return result;
  }
}
