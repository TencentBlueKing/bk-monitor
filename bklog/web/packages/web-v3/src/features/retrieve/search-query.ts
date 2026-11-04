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

export interface SearchChip {
  field: string;
  value: string;
}

export const parseSearchChips = (keyword: string): SearchChip[] => (
  keyword.trim().split(/\s+/).filter(Boolean).map(token => {
    const index = token.indexOf(':');
    if (index > 0) {
      return { field: token.slice(0, index), value: token.slice(index + 1) };
    }
    return { field: '*', value: token };
  })
);

export const chipsToKeyword = (chips: SearchChip[]): string => (
  chips.map(chip => (chip.field === '*' ? chip.value : `${chip.field}:${chip.value}`)).join(' ')
);

export const highlightParts = (log: string, needles: string[]) => {
  const words = needles.map(item => item.trim()).filter(Boolean);
  if (!words.length) {
    return [{ key: '0', text: log, mark: false }];
  }
  const escaped = words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return log.split(new RegExp(`(${escaped.join('|')})`, 'i')).filter(Boolean).map((text, index) => ({
    key: `${index}-${text}`,
    text,
    mark: words.some(word => word.toLowerCase() === text.toLowerCase()),
  }));
};
