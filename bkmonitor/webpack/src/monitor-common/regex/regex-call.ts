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
export default class RegexCall {
  eval = '';
  flags = '';
  regex = '';
  constructor(regex?: RegexCall | string, flags?: string) {
    if (!(this instanceof RegexCall)) {
      return new RegexCall(regex);
    }
    this.regex = '';
    this.flags = flags || '';
    this.eval = '';
    if (regex instanceof RegexCall) {
      this.regex = regex.regex;
    } else if (typeof regex === 'string') {
      this.regex = regex;
    }
  }
  a(re: RegexCall | string, m?: number, n?: number) {
    if (re instanceof RegexCall) {
      this.regex += re.regex;
    } else if (typeof re === 'string') {
      this.regex += re;
    }
    return this.n(m, n);
  }
  contain(str: string) {
    return new RegExp(this.regex, `${this.flags}g`).test(typeof str === 'string' ? str : this.eval);
  }
  e(str?: string) {
    if (typeof str === 'string') {
      this.eval = str;
      return this;
    }
    return new RegExp(this.regex, this.flags);
  }
  exact() {
    this.regex = `(?:^${this.regex}$)`;
    return this;
  }
  is(str: string) {
    return new RegExp(`(?:^${this.regex}$)`, this.flags).test(typeof str === 'string' ? str : this.eval);
  }
  match(str: string) {
    return (typeof str === 'string' ? str : this.eval).match(new RegExp(this.regex, `${this.flags}g`));
  }
  n(m?: number | string, n?: number) {
    if (typeof m === 'number' && typeof n === 'number') {
      if (m >= 0 && n >= m) {
        this.regex += `{${m},${n}}`;
      }
    } else if (typeof m === 'number' && typeof n === 'undefined') {
      if (m >= 0) this.regex += `{${m}}`;
    } else if (typeof m === 'string' && typeof n === 'undefined') {
      this.regex += m;
    }
    return this;
  }
  opt(opts?: string) {
    if (/^[img]+$/i.test(opts)) {
      this.flags = opts || '';
    } else {
      this.flags = opts || '';
    }
    return this;
  }
  or(re?: RegexCall | string, m?: number, n?: number) {
    if (re instanceof RegexCall) {
      this.regex += `|${re.regex}`;
    } else if (typeof re === 'string' && re !== '') {
      this.regex += `|${re}`;
    } else {
      this.regex += '|';
    }
    return this.n(m, n);
  }
  p(regex?: number | RegexCall | string, m?: number | string, n?: number) {
    if (regex instanceof RegexCall) {
      this.regex += `(?:${regex.regex})`;
    } else if (typeof regex === 'string' && regex !== '') {
      this.regex += `(?:${regex})`;
    } else {
      this.regex = `(?:${this.regex})`;
    }
    return this.n(m, n);
  }
}

export function r(regex?: RegexCall | string, flags?: string) {
  return new RegexCall(regex, flags);
}
