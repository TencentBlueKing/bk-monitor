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
export default class StaticUtil {
  static getRegExp(
    reg: RegExp | boolean | number | string,
    defaultFlags = '',
    fullMatch = false,
    formatRegStr = true,
  ): RegExp {
    // 如果已经是 RegExp 对象，直接返回
    if (reg instanceof RegExp) {
      return reg;
    }

    const regString = String(reg).trim();

    // 判定是否为标准正则表达式字符串 /pattern/flags
    if (regString.startsWith('/') && regString.lastIndexOf('/') > 0) {
      const lastSlashIndex = regString.lastIndexOf('/');
      const pattern = regString.slice(1, lastSlashIndex); // 提取正则表达式的主体部分
      let flags = regString.slice(lastSlashIndex + 1); // 提取正则表达式的 flags（可能为空）
      flags = Array.from(new Set(...flags.split(''), ...(defaultFlags ?? '').split(''))).join('');

      // 如果 flags 中包含非法字符，直接将整个字符串作为普通字符串处理
      if (!/^[gimsuy]*$/.test(flags)) {
        const formatRegString = formatRegStr ? regString.replace(/([.*+?^${}()|[\]\\])/g, '\\$1') : regString;
        const wrapperReg = fullMatch ? `^${formatRegString}$` : formatRegString;
        return new RegExp(wrapperReg, defaultFlags); // 转义特殊字符
      }

      try {
        return new RegExp(pattern, flags); // 创建 RegExp 对象
      } catch (error) {
        console.error(`Invalid regular expression: ${regString}`, error);
        throw error; // 如果正则表达式无效，抛出错误
      }
    }

    // 如果不是标准正则表达式字符串，将字符串作为整体处理
    try {
      const formatRegString = formatRegStr ? regString.replace(/([.*+?^${}()|[\]\\])/g, '\\$1') : regString;
      const wrapperReg = fullMatch ? `^${formatRegString}$` : formatRegString;
      return new RegExp(wrapperReg, defaultFlags); // 转义特殊字符
    } catch (error) {
      console.error(`Invalid regular expression: ${regString}`, error);
      throw error; // 如果正则表达式无效，抛出错误
    }
  }
}
