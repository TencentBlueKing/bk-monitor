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
export default class LuceneSegment {
  /**
   * 拆分字符串
   * @param input 输入的长字符串
   * @param MAX_TOKENS 最大拆分的 token 数量
   * @returns 拆分后的字符串数组
   */
  static split(input: string, MAX_TOKENS: number): { text: string; isMark: boolean; isCursorText: boolean }[] {
    const result: { text: string; isMark: boolean; isCursorText: boolean }[] = [];
    const markRegex = /<mark>(.*?)<\/mark>/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    let tokenCount = 0;
    while ((match = markRegex.exec(input)) !== null) {
      // 处理 mark 前的普通文本
      if (match.index > lastIndex) {
        const plainText = input.slice(lastIndex, match.index);
        if (tokenCount < MAX_TOKENS) {
          const tokens = LuceneSegment.processBuffer(plainText, MAX_TOKENS, tokenCount);
          for (const token of tokens) {
            if (tokenCount >= MAX_TOKENS) {
              break;
            }
            result.push(token);
            tokenCount++;
          }
          // 如果分词后还有剩余未处理的 plainText，整体添加
          const processedLength = tokens.map(t => t.text).join('').length;
          if (tokenCount >= MAX_TOKENS && processedLength < plainText.length) {
            const remainText = plainText.slice(processedLength);
            if (remainText) {
              result.push({ text: remainText, isMark: false, isCursorText: false });
            }
          }
        } else {
          // 超出 MAX_TOKENS 后，普通文本整体添加
          result.push({ text: plainText, isMark: false, isCursorText: false });
        }
      }
      // 处理 mark 内容，始终单独分割
      result.push({ text: match[1], isMark: true, isCursorText: true });
      tokenCount++;
      lastIndex = match.index + match[0].length;
    }
    // 处理最后剩余的普通文本
    if (lastIndex < input.length) {
      const plainText = input.slice(lastIndex);
      if (tokenCount < MAX_TOKENS) {
        const tokens = LuceneSegment.processBuffer(plainText, MAX_TOKENS, tokenCount);
        for (const token of tokens) {
          if (tokenCount >= MAX_TOKENS) {
            break;
          }
          result.push(token);
          tokenCount++;
        }
        const processedLength = tokens.map(t => t.text).join('').length;
        if (tokenCount >= MAX_TOKENS && processedLength < plainText.length) {
          const remainText = plainText.slice(processedLength);
          if (remainText) {
            result.push({ text: remainText, isMark: false, isCursorText: false });
          }
        }
      } else {
        result.push({ text: plainText, isMark: false, isCursorText: false });
      }
    }
    return result;
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
  ): { text: string; isMark: boolean; isCursorText: boolean }[] {
    const result: { text: string; isMark: boolean; isCursorText: boolean }[] = [];
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
