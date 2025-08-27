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
 * 编码类型枚举
 */
export enum EncodingType {
  ASCII = 'ascii',
  BASE64 = 'base64',
  TIMESTAMP = 'timestamp',
  UNICODE = 'unicode',
  URL = 'url',
}

/**
 * 自动检测字符串编码并解码
 * @param str 待检测和解码的字符串
 * @returns 解码后的字符串，如果无法解码则返回原字符串
 */
export const autoDecodeString = (str: string): string => {
  if (!str || typeof str !== 'string') {
    return str;
  }

  const trimmedStr = str.trim();
  if (!trimmedStr) {
    return str;
  }

  // 按优先级检测编码类型（从特征最明显到最容易误判）
  const encodingChecks = [
    // 1. URL编码 - 特征最明显：%XX格式
    { type: EncodingType.URL, canDecode: canDecodeUrl },

    // 2. Unicode编码 - 特征明显：\uXXXX 或 \xXX格式
    { type: EncodingType.UNICODE, canDecode: canDecodeUnicode },

    // 3. Base64编码 - 特征较明显：特定字符集+长度规则
    { type: EncodingType.BASE64, canDecode: canDecodeBase64 },

    // 4. 时间戳 - 容易误判：纯数字但有长度限制
    { type: EncodingType.TIMESTAMP, canDecode: canDecodeTimestamp },

    // 5. ASCII编码 - 最容易误判：数字序列，放最后
    { type: EncodingType.ASCII, canDecode: canDecodeAscii },
  ];

  // 找到第一个匹配的编码类型并解码
  for (const check of encodingChecks) {
    if (check.canDecode(trimmedStr)) {
      return decodeString(str, check.type);
    }
  }

  // 如果没有找到匹配的编码，返回原字符串
  return str;
};

/**
 * 判断字符串是否可以解码为指定类型
 * @param str 待判断的字符串
 * @param type 编码类型
 * @returns 是否可以解码
 */
export const canDecode = (str: string, type: EncodingType): boolean => {
  if (!str || typeof str !== 'string') {
    return false;
  }

  const trimmedStr = str.trim();
  if (!trimmedStr) {
    return false;
  }

  switch (type) {
    case EncodingType.URL:
      return canDecodeUrl(trimmedStr);
    case EncodingType.TIMESTAMP:
      return canDecodeTimestamp(trimmedStr);
    case EncodingType.BASE64:
      return canDecodeBase64(trimmedStr);
    case EncodingType.UNICODE:
      return canDecodeUnicode(trimmedStr);
    case EncodingType.ASCII:
      return canDecodeAscii(trimmedStr);
    default:
      return false;
  }
};

/**
 * 解码字符串
 * @param str 待解码的字符串
 * @param type 编码类型
 * @returns 解码后的字符串，失败则返回原字符串
 */
export const decodeString = (str: string, type: EncodingType): string => {
  if (!canDecode(str, type)) {
    return str;
  }

  const trimmedStr = str.trim();

  try {
    switch (type) {
      case EncodingType.URL:
        return decodeURIComponent(trimmedStr);

      case EncodingType.TIMESTAMP: {
        const timestamp = parseInt(trimmedStr, 10);
        const date = new Date(trimmedStr.length === 10 ? timestamp * 1000 : timestamp);
        return date.toLocaleString();
      }

      case EncodingType.BASE64:
        return atob(trimmedStr);

      case EncodingType.UNICODE:
        return trimmedStr
          .replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => {
            return String.fromCharCode(parseInt(code, 16));
          })
          .replace(/\\x([0-9a-fA-F]{2})/g, (_, code) => {
            return String.fromCharCode(parseInt(code, 16));
          });

      case EncodingType.ASCII: {
        const numbers = trimmedStr.match(/\d+/g);
        if (!numbers) return str;
        return numbers.map(num => String.fromCharCode(parseInt(num, 10))).join('');
      }

      default:
        return str;
    }
  } catch {
    return str;
  }
};

/**
 * 检测字符串的编码类型（返回第一个匹配的类型）
 * @param str 待检测的字符串
 * @returns 编码类型，如果没有检测到则返回 null
 */
export const detectEncodingType = (str: string): EncodingType | null => {
  if (!str || typeof str !== 'string') {
    return null;
  }

  const trimmedStr = str.trim();
  if (!trimmedStr) {
    return null;
  }

  // 按优先级检测编码类型（从特征最明显到最容易误判）
  const encodingChecks = [
    // 1. URL编码 - 特征最明显：%XX格式
    { type: EncodingType.URL, canDecode: canDecodeUrl },

    // 2. Unicode编码 - 特征明显：\uXXXX 或 \xXX格式
    { type: EncodingType.UNICODE, canDecode: canDecodeUnicode },

    // 3. Base64编码 - 特征较明显：特定字符集+长度规则
    { type: EncodingType.BASE64, canDecode: canDecodeBase64 },

    // 4. 时间戳 - 容易误判：纯数字但有长度限制
    { type: EncodingType.TIMESTAMP, canDecode: canDecodeTimestamp },

    // 5. ASCII编码 - 最容易误判：数字序列，放最后
    { type: EncodingType.ASCII, canDecode: canDecodeAscii },
  ];

  // 返回第一个匹配的编码类型
  for (const check of encodingChecks) {
    if (check.canDecode(trimmedStr)) {
      return check.type;
    }
  }

  return null;
};

/**
 * 格式化 JSON 字符串
 * @param str 待格式化的字符串
 * @param indent 缩进空格数，默认为 2
 * @returns 格式化后的 JSON 字符串，如果不是有效 JSON 则返回原字符串
 */
export const formatJsonString = (str: string, indent = 2): string => {
  if (!shouldFormatAsJson(str)) {
    return str;
  }

  try {
    const parsed = JSON.parse(str.trim());
    return JSON.stringify(parsed, null, indent);
  } catch {
    return str;
  }
};

/**
 * 检查字符串是否为有效的 JSON 格式
 * @param str 待检查的字符串
 * @returns 是否为有效的 JSON
 */
export const isValidJson = (str: string): boolean => {
  if (!str || typeof str !== 'string') {
    return false;
  }

  try {
    JSON.parse(str.trim());
    return true;
  } catch {
    return false;
  }
};

/**
 * 判断字符串是否需要格式化为 JSON（基于 isValidJson 函数）
 * @param str 待判断的字符串
 * @returns 是否需要格式化为 JSON
 */
export const shouldFormatAsJson = (str: string): boolean => {
  if (!str || typeof str !== 'string') {
    return false;
  }

  const trimmedStr = str.trim();

  // 空字符串不需要格式化
  if (!trimmedStr) {
    return false;
  }

  // 检查是否以 JSON 对象或数组的标识符开始和结束
  const isJsonLike =
    (trimmedStr.startsWith('{') && trimmedStr.endsWith('}')) ||
    (trimmedStr.startsWith('[') && trimmedStr.endsWith(']'));

  // 必须看起来像 JSON 且是有效的 JSON
  return isJsonLike && isValidJson(trimmedStr);
};

/**
 * 尝试美化 JSON 字符串，如果不是 JSON 则返回原字符串
 * @param str 待处理的字符串
 * @param indent 缩进空格数，默认为 2
 * @returns 美化后的字符串或原字符串
 */
export const tryFormatJson = (str: string, indent = 2): string => {
  if (shouldFormatAsJson(str)) {
    return formatJsonString(str, indent);
  }
  return str;
};

/**
 * 判断字符串是否为 ASCII 编码的数字序列
 * @param str 待判断的字符串
 * @returns 是否为 ASCII 编码
 */
const canDecodeAscii = (str: string): boolean => {
  try {
    // 检查是否为用空格或逗号分隔的数字序列
    const asciiPattern = /^(\d{1,3}[\s,]*)+$/;

    if (!asciiPattern.test(str)) {
      return false;
    }

    // 提取所有数字
    const numbers = str.match(/\d+/g);
    if (!numbers) {
      return false;
    }

    // 检查每个数字是否在 ASCII 范围内 (0-127)
    return numbers.every(num => {
      const code = parseInt(num, 10);
      return code >= 0 && code <= 127;
    });
  } catch {
    return false;
  }
};

/**
 * 判断字符串是否为 Base64 编码
 * @param str 待判断的字符串
 * @returns 是否为 Base64 编码
 */
const canDecodeBase64 = (str: string): boolean => {
  try {
    // Base64 正则表达式
    const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;

    // 长度必须是 4 的倍数
    if (str.length % 4 !== 0) {
      return false;
    }

    // 检查字符格式
    if (!base64Regex.test(str)) {
      return false;
    }

    // 尝试解码
    const decoded = atob(str);
    // 再次编码验证
    const reEncoded = btoa(decoded);
    return reEncoded === str;
  } catch {
    return false;
  }
};

/**
 * 判断字符串是否为时间戳
 * @param str 待判断的字符串
 * @returns 是否为时间戳
 */
const canDecodeTimestamp = (str: string): boolean => {
  // 检查是否为纯数字
  if (!/^\d+$/.test(str)) {
    return false;
  }

  const num = parseInt(str, 10);

  // 检查时间戳范围 (10位秒级时间戳: 1970-2099年, 13位毫秒级时间戳)
  if (str.length === 10) {
    // 秒级时间戳: 1970/1/1 到 2099/12/31
    return num >= 0 && num <= 4102444800;
  } else if (str.length === 13) {
    // 毫秒级时间戳
    return num >= 0 && num <= 4102444800000;
  }

  return false;
};

/**
 * 判断字符串是否为 Unicode 编码
 * @param str 待判断的字符串
 * @returns 是否为 Unicode 编码
 */
const canDecodeUnicode = (str: string): boolean => {
  try {
    // 检查是否包含 \u 或 \x 格式的 Unicode 编码
    const unicodePattern = /\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}/;

    if (!unicodePattern.test(str)) {
      return false;
    }

    // 尝试解码 Unicode
    const decoded = str
      .replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => {
        return String.fromCharCode(parseInt(code, 16));
      })
      .replace(/\\x([0-9a-fA-F]{2})/g, (_, code) => {
        return String.fromCharCode(parseInt(code, 16));
      });

    return decoded !== str;
  } catch {
    return false;
  }
};

/**
 * 判断字符串是否为 URL 编码
 * @param str 待判断的字符串
 * @returns 是否为 URL 编码
 */
const canDecodeUrl = (str: string): boolean => {
  try {
    // 检查是否包含 URL 编码字符
    const hasEncodedChars = /%[0-9A-Fa-f]{2}/.test(str);
    if (!hasEncodedChars) {
      return false;
    }

    // 尝试解码
    const decoded = decodeURIComponent(str);
    // 解码后的字符串应该与原字符串不同
    return decoded !== str;
  } catch {
    return false;
  }
};
