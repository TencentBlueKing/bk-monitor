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

const COLUMN_DELIMITER = ',';

export const csvToArr = (csv: string) => {
  const table = [] as string[][];
  let row = [];
  let cell = '';
  let openQuote = false;
  let i = 0;

  const pushCell = () => {
    row.push(cell);
    cell = '';
  };

  const pushRow = () => {
    pushCell();
    table.push(row);
    row = [];
  };
  // 处理行分隔符和列分隔符
  const handleSeparator = (n: number) => {
    const c = csv.charAt(n);
    if (c === COLUMN_DELIMITER) {
      pushCell();
    } else if (c === '\r') {
      if (csv.charAt(n + 1) === '\n') {
        i += 1;
      }
      pushRow();
    } else if (c === '\n') {
      pushRow();
    } else {
      return false;
    }
    return true;
  };

  while (i < csv.length) {
    const c = csv.charAt(i);
    const next = csv.charAt(i + 1);
    if (!openQuote && !cell && c === '"') {
      // 遇到单元第一个字符为双引号时假设整个单元都是被双引号括起来
      openQuote = true;
    } else if (openQuote) {
      // 双引号还未成对的时候
      if (c !== '"') {
        // 如非双引号，直接添加进单元内容
        cell += c;
      } else if (next === '"') {
        // 处理双引号转义
        cell += c;
        i += 1;
      } else {
        // 确认单元结束
        openQuote = false;
        i += 1;
        if (!handleSeparator(i)) {
          throw new Error('Wrong CSV format!');
        }
      }
    } else if (!handleSeparator(i)) {
      // 没有双引号包起来时，如非行列分隔符，一律直接加入单元内容
      cell += c;
    }
    i += 1;
  }
  if (cell) {
    pushRow();
  }
  return table;
};
