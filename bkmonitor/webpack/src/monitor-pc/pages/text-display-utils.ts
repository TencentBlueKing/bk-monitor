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

interface IHighlightFragment {
  highlight: boolean;
  start: number;
  text: string;
}

interface IItemDescription {
  val: string;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** 获取策略描述的纯文本提示配置 */
export function getItemDescriptionTooltip(data: IItemDescription[]) {
  return {
    allowHTML: false,
    content: data.map(item => item.val).join('\n'),
    extCls: 'strategy-item-description-tooltips',
  };
}

/** 将搜索结果拆分为可直接渲染的文本片段 */
export function splitHighlightFragments(content: string, searchValue: string): IHighlightFragment[] {
  const keywords = searchValue.trim().split(/\s+/).filter(Boolean).map(escapeRegExp);
  if (!keywords.length) {
    return [{ text: content, start: 0, highlight: false }];
  }

  const keywordPattern = keywords.join('|');
  const splitRegExp = new RegExp(`(${keywordPattern})`, 'gi');
  const exactMatchRegExp = new RegExp(`^(?:${keywordPattern})$`, 'i');
  let start = 0;

  return content
    .split(splitRegExp)
    .filter(Boolean)
    .map(text => {
      const fragment = {
        text,
        start,
        highlight: exactMatchRegExp.test(text),
      };
      start += text.length;
      return fragment;
    });
}
