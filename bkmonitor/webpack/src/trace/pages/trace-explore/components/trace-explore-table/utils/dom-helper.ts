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

/**
 * 检测单行文本是否显示省略号
 * @param {HTMLElement} element 要检测的容器元素
 *
 */
export function isEllipsisActiveSingleLine(element: HTMLElement): {
  content: string;
  isEllipsisActive: boolean;
} {
  // 验证是否应用了必要样式
  const style = window.getComputedStyle(element);
  if (style.textOverflow !== 'ellipsis' || style.whiteSpace !== 'nowrap') {
    return { content: '', isEllipsisActive: false };
  }
  const range = document.createRange();
  range.setStart(element, 0);
  range.setEnd(element, element.childNodes.length);

  let rangeWidth = range.getBoundingClientRect().width;

  const offsetWidth = rangeWidth - Math.floor(rangeWidth);
  if (offsetWidth < 0.001) {
    rangeWidth = Math.floor(rangeWidth);
  }
  const paddingLeft = Number.parseInt(style.paddingLeft, 10) || 0;
  const paddingRight = Number.parseInt(style.paddingRight, 10) || 0;
  const horizontalPadding = paddingLeft + paddingRight;

  return {
    content: range.toString(),
    // @ts-ignore
    isEllipsisActive: range.scrollWidth > element.clientWidth || rangeWidth + horizontalPadding > element.clientWidth,
  };
}
