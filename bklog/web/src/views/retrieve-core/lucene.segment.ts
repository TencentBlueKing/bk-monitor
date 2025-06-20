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
  static split(input: string, MAX_TOKENS: number): { text: string; isMark: boolean }[] {
    const result: { text: string; isMark: boolean }[] = [];
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
        });
        lastIndex = offset + match.length;
        return match;
      }

      // 添加 <mark> 之前的普通文本
      if (offset > lastIndex) {
        const plainText = input.slice(lastIndex, offset);
        result.push(...LuceneSegment.processBuffer(plainText));
      }

      // 添加 <mark> 内的文本
      result.push({
        text: markedText,
        isMark: true,
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
          });
          return match;
        });
      } else {
        result.push(...LuceneSegment.processBuffer(remainingText));
      }
    }

    return result;
  }

  /**
   * 处理普通文本的拆分逻辑
   * @param buffer 当前缓冲区内容
   * @returns 拆分后的结果数组
   */
  private static processBuffer(buffer: string): { text: string; isMark: boolean }[] {
    const result: { text: string; isMark: boolean }[] = [];
    let segment = '';

    for (let i = 0; i < buffer.length; i++) {
      const char = buffer[i];
      const nextChar = buffer[i + 1] || '';

      // 判断是否需要触发拆分
      if (LuceneSegment.shouldSplit(segment, char, nextChar)) {
        result.push({ text: segment, isMark: false });
        segment = char; // 当前字符作为新段的起始
      } else {
        segment += char; // 当前字符加入缓冲区
      }
    }

    // 将最后的缓冲区内容加入结果
    if (segment) {
      result.push({ text: segment, isMark: false });
    }

    return result;
  }

  /**
   * 判断是否需要拆分
   * @param buffer 当前缓冲区内容
   * @param char 当前字符
   * @param nextChar 下一个字符
   * @returns 是否需要拆分
   */
  private static shouldSplit(buffer: string, char: string, nextChar: string): boolean {
    // ':' 在 \p{WB:MidLetter} 中，需两侧为字母才不拆分
    if (char === ':' && !(LuceneSegment.isLetter(buffer.slice(-1)) && LuceneSegment.isLetter(nextChar))) {
      return true;
    }

    // '.' 在 \p{WB:MidNumLet} 中，需两侧为字母或数字才不拆分
    if (char === '.' && !(LuceneSegment.isLetterOrDigit(buffer.slice(-1)) && LuceneSegment.isLetterOrDigit(nextChar))) {
      return true;
    }

    // ',' 在 \p{WB:MidNum} 中，需两侧为数字才不拆分
    if (char === ',' && !(LuceneSegment.isDigit(buffer.slice(-1)) && LuceneSegment.isDigit(nextChar))) {
      return true;
    }

    // 混合连续的 \p{WB:MidLetter} 和 \p{WB:MidNumLet} 触发拆分
    if ((char === ':' || char === '.') && (nextChar === ':' || nextChar === '.')) {
      return true;
    }

    // 混合连续的 \p{WB:MidNum} 和 \p{WB:MidNumLet} 触发拆分
    if ((char === ',' || char === '.') && (nextChar === ',' || nextChar === '.')) {
      return true;
    }

    // '_' 在 \p{WB:ExtendNumLet} 中，不触发拆分
    if (char === '_') {
      return false;
    }

    return false;
  }

  /**
   * 判断字符是否为字母
   * @param char 字符
   * @returns 是否为字母
   */
  private static isLetter(char: string): boolean {
    return /^[a-zA-Z]$/.test(char);
  }

  /**
   * 判断字符是否为数字
   * @param char 字符
   * @returns 是否为数字
   */
  private static isDigit(char: string): boolean {
    return /^[0-9]$/.test(char);
  }

  /**
   * 判断字符是否为字母或数字
   * @param char 字符
   * @returns 是否为字母或数字
   */
  private static isLetterOrDigit(char: string): boolean {
    return /^[a-zA-Z0-9]$/.test(char);
  }
}
