/* 判断是否为非法字符串 */
export function judgeIsIllegal(value: string) {
  return /^[_a-zA-Z][a-zA-Z0-9_]*$/.test(value);
}
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
/* 指标名称转换 */
export function metricNameTransFrom(value: string) {
  if (!judgeIsIllegalNew(value)) {
    let str = value.replace(/[^_a-zA-Z0-9]/g, '_');
    if (!judgeIsIllegalNew(str)) {
      let i = 0;
      while (true) {
        i += 1;
        str = str.replace(/^[_0-9]/g, '');
        if (judgeIsIllegalNew(str) || i === 100 || !str) {
          break;
        }
      }
    }
    return str;
  }
  return value;
}
function judgeIsIllegalNew(value: string) {
  return /^[a-zA-Z][a-zA-Z0-9_]*$/.test(value);
}
