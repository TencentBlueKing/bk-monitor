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
 * 模糊匹配（大小写不敏感）
 * @param str 被匹配的字符串
 * @param pattern 匹配模式
 * @returns 是否包含匹配模式
 */
export const fuzzyMatch = (str: string, pattern: string) => {
  const lowerStr = String(str || '').toLowerCase();
  const lowerPattern = String(pattern || '').toLowerCase();
  return lowerStr.includes(lowerPattern);
};

/**
 * 将文本复制到系统剪贴板
 * 通过创建临时 textarea 元素实现 execCommand('copy')
 * @param value 要复制的文本内容
 */
export const execCopy = (value: string) => {
  const textarea = document.createElement('textarea');
  document.body.appendChild(textarea);
  textarea.value = value;
  textarea.select();
  if (document.execCommand('copy')) {
    document.execCommand('copy');
  }
  document.body.removeChild(textarea);
};

/**
 * 通过正则表达式匹配字符串
 * @param str 被匹配的字符串
 * @param matchStr 正则表达式字符串
 * @returns 是否匹配成功，正则语法错误时返回 false
 */
export const matchRuleFn = (str: string, matchStr: string) => {
  let isMatch = false;
  try {
    const regex = new RegExp(matchStr);
    isMatch = regex.test(str);
  } catch (_) {
    isMatch = false;
  }
  return isMatch;
};
