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
// 压缩ipv6
export function compressIPv6(ip: string) {
  if (ip?.length < 4) return ip;
  let output = ip
    .split(':')
    .map(s => s.replace(/\b0+/g, '') || '0')
    .join(':');
  const zeroList = [...output.matchAll(/\b:?(?:0+:?){2,}/g)];
  if (zeroList.length > 0) {
    const max = zeroList.reduce((a, b) => (a[0].replace(/:/g, '').length > b[0].replace(/:/g, '').length ? a : b));
    output = output.replace(max[0], '::');
  }
  return output;
}
// 是否是ipv6全格式
export function isFullIpv6(ip: string) {
  return /^([\da-fA-F]{4}:){7}[\da-fA-F]{4}$/.test(ip.toString());
}
// 补全ipv6
export function padIPv6(ip: string) {
  if (ip?.length < 4) return ip;
  const count = (x: string) => x.split(':').length - 1;
  return ip
    .replace(/::/, () => `:${Array(7 - count(ip) + 1).join(':')}:`)
    .split(':')
    .map(x => x.padStart(4, '0'))
    .join(':');
}
