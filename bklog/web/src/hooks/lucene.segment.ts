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
    const markRegStr = '<mark>(.*?)</mark>';
    const markRegex = new RegExp(markRegStr, 'g');
    let lastIndex = 0;

    // 处理 <mark></mark> 的拆分逻辑
    input.replace(markRegex, (match, markedText, offset) => {
      // 如果当前 result.length 超过 MAX_TOKENS，则只进行 mark 标签的拆分
      if (result.length >= MAX_TOKENS) {
        result.push({
          text: markedText,
          isMark: true,
          isCursorText: true,
        });
        lastIndex = offset + match.length;
        return match;
      }

      // 添加 <mark> 之前的普通文本
      if (offset > lastIndex) {
        const plainText = input.slice(lastIndex, offset);
        result.push(...LuceneSegment.processBuffer(plainText, MAX_TOKENS, result.length));
      }

      // 添加 <mark> 内的文本
      result.push({
        text: markedText,
        isMark: true,
        isCursorText: true,
      });

      lastIndex = offset + match.length;
    });

    // 添加剩余的普通文本或仅拆分 mark 标签
    if (lastIndex < input.length) {
      const remainingText = input.slice(lastIndex);
      if (result.length >= MAX_TOKENS) {
        // 如果超过 MAX_TOKENS，只拆分 mark 标签
        remainingText.replace(markRegex, (match, markedText) => {
          result.push({
            text: markedText,
            isMark: true,
            isCursorText: true,
          });
          return match;
        });
      } else {
        result.push(...LuceneSegment.processBuffer(remainingText, MAX_TOKENS, result.length));
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
    if (this.isMidLetter(c)) {
      return Boolean(prev && next && this.isLetter(prev) && this.isLetter(next));
    }
    if (this.isMidNumLet(c)) {
      return Boolean(
        prev && next && ((this.isLetter(prev) && this.isLetter(next)) || (this.isNumber(prev) && this.isNumber(next))),
      );
    }
    if (this.isMidNum(c)) {
      return Boolean(prev && next && this.isNumber(prev) && this.isNumber(next));
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
      if (this.isExtendNumLet(c)) {
        currentToken += c;
        currentMidSequence = false;
        continue;
      }

      // 处理 Mid 字符
      if (this.isMidLetter(c) || this.isMidNumLet(c) || this.isMidNum(c)) {
        // 连续 Mid 字符触发切分
        if (currentMidSequence) {
          if (currentToken) {
            result.push({ text: currentToken, isMark: false, isCursorText: true });
            if (result.length + currentTokenCount >= MAX_TOKENS) return result;
          }
          // 分词符号本身也要保留
          result.push({ text: c, isMark: false, isCursorText: false });
          if (result.length + currentTokenCount >= MAX_TOKENS) return result;
          currentToken = '';
          currentMidSequence = true;
          continue;
        }
        currentMidSequence = true;
        // 检查是否满足连接条件
        const keepAsPartOfToken = this.canBePartOfToken(c, prev, next);
        if (keepAsPartOfToken) {
          currentToken += c;
        } else {
          if (currentToken) {
            result.push({ text: currentToken, isMark: false, isCursorText: true });
            if (result.length + currentTokenCount >= MAX_TOKENS) return result;
          }
          // 分词符号本身也要保留
          result.push({ text: c, isMark: false, isCursorText: false });
          if (result.length + currentTokenCount >= MAX_TOKENS) return result;
          currentToken = '';
        }
      } else if (c === '-' || c === ' ' || c === '\t') {
        // 其它常见分隔符
        if (currentToken) {
          result.push({ text: currentToken, isMark: false, isCursorText: true });
          if (result.length + currentTokenCount >= MAX_TOKENS) return result;
        }
        result.push({ text: c, isMark: false, isCursorText: false });
        if (result.length + currentTokenCount >= MAX_TOKENS) return result;
        currentToken = '';
        currentMidSequence = false;
      } else {
        // 非 Mid 字符结束连续 Mid 序列
        currentMidSequence = false;
        if (this.isLetter(c) || this.isNumber(c)) {
          currentToken += c;
        } else {
          // 其它所有符号都要保留
          if (currentToken) {
            result.push({ text: currentToken, isMark: false, isCursorText: true });
            if (result.length + currentTokenCount >= MAX_TOKENS) return result;
            currentToken = '';
          }
          result.push({ text: c, isMark: false, isCursorText: false });
          if (result.length + currentTokenCount >= MAX_TOKENS) return result;
        }
      }
    }
    if (currentToken) {
      result.push({ text: currentToken, isMark: false, isCursorText: true });
    }
    return result;
  }
}
