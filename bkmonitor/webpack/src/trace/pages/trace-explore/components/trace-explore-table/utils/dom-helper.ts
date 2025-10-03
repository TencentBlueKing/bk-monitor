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
  if (style.textOverflow !== 'ellipsis' || !['nowrap', 'pre'].includes(style.whiteSpace)) {
    return { content: '', isEllipsisActive: false };
  }
  const range = document.createRange();
  range.setStart(element, 0);
  range.setEnd(element, element.childNodes.length);

  const rangeWidth = range.getBoundingClientRect().width;
  const containerWidth = element.getBoundingClientRect().width;

  const paddingLeft = Number.parseInt(style.paddingLeft, 10) || 0;
  const paddingRight = Number.parseInt(style.paddingRight, 10) || 0;
  const horizontalPadding = paddingLeft + paddingRight;

  return {
    content: range.toString(),
    // @ts-ignore
    // isEllipsisActive: range.scrollWidth > containerWidth || rangeWidth + horizontalPadding > containerWidth,
    isEllipsisActive: rangeWidth > containerWidth - horizontalPadding,
  };
}

/**
 * 检测多行文本是否显示省略号（支持-webkit-line-clamp）
 * @param {HTMLElement} element 要检测的容器元素
 */
export function isEllipsisActiveMultiLine(element) {
  const style = window.getComputedStyle(element);
  // 检查是否应用了多行省略样式
  const lineClamp = parseInt(style.webkitLineClamp);
  // const isBoxValid = style.display === '-webkit-box'; // 浏览器可能会将 '-webkit-box' 解释为 'flow-root' | 'block' 导致校验不准确，暂未找到更好的判断方式所以直接放行
  const isOrientValid = style.webkitBoxOrient === 'vertical';
  const isLineClampValid = !Number.isNaN(lineClamp) && lineClamp > 0;
  const isWrapValid = !['nowrap', 'pre'].includes(style.whiteSpace);
  if (!isOrientValid || !isLineClampValid || !isWrapValid) {
    return { content: '', isEllipsisActive: false };
  }
  const range = document.createRange();
  range.selectNodeContents(element);
  const rangeHeight = range.getBoundingClientRect().height;
  const lineHeight = parseFloat(style.lineHeight);
  const boundaryHeight = lineHeight * lineClamp;

  return {
    content: range.toString(),
    isEllipsisActive: rangeHeight > boundaryHeight,
  };
}

/**
 * 检测文本是否显示省略号（支持单行和多行）
 * @param {HTMLElement} element 要检测的容器元素
 */
export function isEllipsisActiveLine(element: HTMLElement): {
  content: string;
  isEllipsisActive: boolean;
} {
  const style = window.getComputedStyle(element);
  // 单行检测
  if (['nowrap', 'pre'].includes(style.whiteSpace)) {
    return isEllipsisActiveSingleLine(element);
  }
  // 多行检测（支持 -webkit-line-clamp）
  return isEllipsisActiveMultiLine(element);
}
