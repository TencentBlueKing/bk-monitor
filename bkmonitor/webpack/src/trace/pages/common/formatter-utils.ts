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
 * 编码类型枚举
 */
export enum EncodingType {
  ASCII = 'ascii',
  BASE64 = 'base64',
  HEX = 'hex',
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
    // 3. 时间戳 - 容易误判：纯数字但有长度限制
    { type: EncodingType.TIMESTAMP, canDecode: canDecodeTimestamp },

    // 4. 十六进制 - 支持成对字节（紧凑或空格/逗号分隔），启发式过滤无意义二进制
    { type: EncodingType.HEX, canDecode: canDecodeHex },

    // 4. Base64编码 - 特征较明显：特定字符集+长度规则
    { type: EncodingType.BASE64, canDecode: canDecodeBase64 },

    // 6. ASCII编码 - 最容易误判：数字序列，放最后
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
    case EncodingType.HEX:
      return canDecodeHex(trimmedStr);
    case EncodingType.UNICODE:
      return canDecodeUnicode(trimmedStr);
    case EncodingType.ASCII:
      return canDecodeAscii(trimmedStr);
    default:
      return false;
  }
};

/**
 * 判断字符串是否为十六进制（以字节为单位）
 * 支持形式：
 *  - 紧凑偶数长度：如 "48656C6C6F"
 *  - 分隔形式：如 "48 65 6C 6C 6F" 或 "48,65,6C,6C,6F"
 *  - 混合长度分隔：如 "48 65 6C 6C 6F E4BD A0"（支持2位和4位混合）
 */
const canDecodeHex = (str: string): boolean => {
  try {
    const s = str.trim();
    if (!s) return false;

    // 检查是否包含分隔符（空格或逗号）
    const hasSeparator = /[\s,]/.test(s);

    if (hasSeparator) {
      // 分隔符形式：支持混合长度的十六进制部分
      const parts = s.split(/[\s,]+/).filter(Boolean);
      if (parts.length === 0) return false;

      // 检查每个部分是否都是有效的十六进制（长度必须是偶数）
      if (!parts.every(p => /^[0-9A-Fa-f]+$/.test(p) && p.length % 2 === 0)) {
        return false;
      }

      // 将所有部分连接后按2位分组解析
      const connected = parts.join('');
      const bytes: number[] = [];
      for (let i = 0; i < connected.length; i += 2) {
        bytes.push(parseInt(connected.slice(i, i + 2), 16));
      }
      return evaluateBytesReadability(bytes);
    }

    // 紧凑形式：长度偶数且全部十六进制
    if (s.length % 2 !== 0) return false;
    if (!/^[0-9A-Fa-f]+$/.test(s)) return false;
    const bytes: number[] = [];
    for (let i = 0; i < s.length; i += 2) bytes.push(parseInt(s.slice(i, i + 2), 16));
    return evaluateBytesReadability(bytes);
  } catch {
    return false;
  }
};

// 复用 Base64 的可读性启发式，面向字节数组
const evaluateBytesReadability = (bytes: number[]): boolean => {
  const total = bytes.length;
  if (total === 0) return false;
  let visible = 0;
  let whitespace = 0;
  let control = 0;
  let zeroByte = 0;
  for (let i = 0; i < total; i++) {
    const code = bytes[i] & 0xff;
    if (code === 0) zeroByte++;
    if (code >= 33 && code <= 126) visible++;
    else if (code === 9 || code === 10 || code === 13 || code === 32) whitespace++;
    else control++;
  }
  const printableRatio = (visible + whitespace) / total;
  const visibleRatio = visible / total;

  // 若能按 UTF-8 成功解码且文本含有中文或可打印字符，则认为可读
  try {
    if (typeof TextDecoder !== 'undefined') {
      const td = new TextDecoder('utf-8', { fatal: true });
      const text = td.decode(new Uint8Array(bytes));
      if (hasNonAsciiChar(text) || hasPrintableAsciiRun(text, 2)) {
        return true;
      }
    }
  } catch {
    // ignore utf-8 failure, fallback to heuristics below
  }

  // 明确拒绝 3 字节 控制 + '@' + 控制
  if (total === 3 && bytes[1] === 64 && bytes[0] < 32 && bytes[2] < 32) return false;
  // 很短的结果若不是全部可见，视为不可信
  if (total <= 4 && visible < total) return false;
  // 含空字节且可读性低
  if (zeroByte > 0 && printableRatio < 0.8) return false;
  // 控制占比过高
  if (visibleRatio < 0.5 && control >= Math.ceil(total * 0.5)) return false;

  // 允许
  return printableRatio >= 0.7 && visible >= 2;
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
        try {
          const s = trimmedStr;

          // 标准化 Base64 字符串
          const core = s.replace(/=+$/g, '');
          let normalized = core.replace(/-/g, '+').replace(/_/g, '/');

          // 处理填充
          const mod = normalized.length % 4;
          if (mod === 1) {
            // 余数为 1 是非法的
            return str;
          }
          if (mod !== 0) {
            normalized = normalized + '='.repeat(4 - mod);
          }

          // 解码
          const binary = atob(normalized);

          // 转换为字节数组
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i) & 0xff;
          }

          // 尝试 UTF-8 解码
          try {
            if (typeof TextDecoder !== 'undefined') {
              const decoder = new TextDecoder('utf-8', { fatal: true });
              return decoder.decode(bytes);
            }
          } catch {
            // UTF-8 解码失败，尝试截断解码
            if (typeof TextDecoder !== 'undefined') {
              const decoder = new TextDecoder('utf-8', { fatal: true });
              // 从最长开始尝试，找到最长的有效 UTF-8 前缀
              for (let len = bytes.length; len > 0; len--) {
                try {
                  const text = decoder.decode(bytes.subarray(0, len));
                  if (text && text.length > 0) {
                    return text;
                  }
                } catch {
                  // 继续尝试更短的前缀
                }
              }

              // 如果都失败了，使用非严格模式
              const nonStrictDecoder = new TextDecoder('utf-8');
              return nonStrictDecoder.decode(bytes);
            }
          }

          // 回退到 Latin-1 解码
          return binary;
        } catch {
          return str;
        }

      case EncodingType.UNICODE:
        return trimmedStr
          .replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => {
            return String.fromCharCode(parseInt(code, 16));
          })
          .replace(/\\x([0-9a-fA-F]{2})/g, (_, code) => {
            return String.fromCharCode(parseInt(code, 16));
          });

      case EncodingType.HEX: {
        // 支持：紧凑偶数长度十六进制，或以空格/逗号分隔的字节对
        const compact = trimmedStr.replace(/[\s,]+/g, '');
        if (compact.length % 2 !== 0) return str;
        const bytes = new Uint8Array(compact.length / 2);
        for (let i = 0; i < compact.length; i += 2) {
          const byte = parseInt(compact.slice(i, i + 2), 16);
          if (Number.isNaN(byte)) return str;
          bytes[i / 2] = byte & 0xff;
        }
        try {
          if (typeof TextDecoder !== 'undefined') {
            const td = new TextDecoder('utf-8');
            return td.decode(bytes);
          }
        } catch {
          // 回退：按 Latin-1 显示
        }
        let out = '';
        for (const byte of bytes) out += String.fromCharCode(byte);
        return out;
      }

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

    // 3. 十六进制 - 支持成对字节（紧凑或空格/逗号分隔），启发式过滤无意义二进制
    { type: EncodingType.HEX, canDecode: canDecodeHex },

    // 4. Base64编码 - 特征较明显：特定字符集+长度规则
    { type: EncodingType.BASE64, canDecode: canDecodeBase64 },

    // 5. 时间戳 - 容易误判：纯数字但有长度限制
    { type: EncodingType.TIMESTAMP, canDecode: canDecodeTimestamp },

    // 6. ASCII编码 - 最容易误判：数字序列，放最后
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
 * 校验字符串是否为良好成形的 Unicode（无未配对代理项），可被安全表示为 UTF-8。
 * @param decoded 待校验的字符串
 * @returns 是否为良好成形的 Unicode
 */
const canDecodeUtf8 = (decoded: string): boolean => {
  let isUtf8 = false;
  const total = decoded.length;
  try {
    const hasTextDecoder = typeof TextDecoder !== 'undefined';
    if (hasTextDecoder) {
      const td = new TextDecoder('utf-8', { fatal: true });
      const bytes = new Uint8Array(total);
      for (let i = 0; i < total; i++) bytes[i] = decoded.charCodeAt(i) & 0xff;
      td.decode(bytes); // 若无效 UTF-8 会抛异常
      isUtf8 = true;
    }
  } catch {
    isUtf8 = false;
  }
  return isUtf8;
};

/**
 * 文本可读性辅助：是否包含非 ASCII 字符
 */
const hasNonAsciiChar = (s: string): boolean => {
  for (let i = 0; i < s.length; i++) {
    if ((s.charCodeAt(i) & 0xff) > 0x7f) return true;
  }
  return false;
};

/**
 * 文本可读性辅助：是否包含至少 N 个连续的可打印 ASCII (0x20-0x7E)
 */
const hasPrintableAsciiRun = (s: string, minRunLen = 2): boolean => {
  let run = 0;
  for (let i = 0; i < s.length; i++) {
    const code = s.charCodeAt(i) & 0xff;
    if (code >= 0x20 && code <= 0x7e) {
      run++;
      if (run >= minRunLen) return true;
    } else {
      run = 0;
    }
  }
  return false;
};

/**
 * 判断字符串是否为 ASCII 编码的数字序列
 * @param str 待判断的字符串
 * @returns 是否为 ASCII 编码
 */
const canDecodeAscii = (str: string): boolean => {
  try {
    const s = str.trim();
    // 必须是 1-3 位数字，且数字之间用空格或逗号分隔，不能只出现分隔符
    const asciiPattern = /^\d{1,3}(?:[\s,]+\d{1,3})*$/;

    if (!asciiPattern.test(s)) {
      return false;
    }

    // 提取所有数字
    const numbers = s.match(/\d{1,3}/g);
    if (!numbers) {
      return false;
    }

    // 检查每个数字是否在 ASCII 范围内 (0-127)，并且至少包含 1 个可见可打印字符(33-126)
    let hasVisiblePrintable = false;
    for (const num of numbers) {
      const code = parseInt(num, 10);
      if (Number.isNaN(code) || code < 0 || code > 127) {
        return false;
      }
      if (code >= 33 && code <= 126) {
        hasVisiblePrintable = true;
      }
    }

    // 仅控制字符或仅空白（如 16、0、10 13 等）视为无意义，不可解码
    return hasVisiblePrintable;
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
    // 1. 预处理：去除前后空格，排除空字符串
    const s = str.trim();
    if (!s) {
      return false;
    }

    // 2. 基础规则1：长度必须是4的整数倍（Base64编码逻辑：3字节→4字符，不足补=）
    if (s.length % 4 !== 0) {
      return false;
    }

    // 3. 排除明显的非Base64模式（在字符集检查前）
    // HTTP路径：以/开头，可能包含状态码或路径段
    if (/^\/\d+$/.test(s) || /^\/[a-zA-Z0-9]+$/.test(s)) {
      return false;
    }

    // URL路径段：包含多个/的明显路径
    if (s.includes('/') && s.split('/').length > 2) {
      return false;
    }

    // 排除纯数字字符串（很可能是端口号、ID等，不是Base64）
    if (/^\d+$/.test(s)) {
      return false;
    }

    // 排除常见的非Base64模式
    if (/^[a-zA-Z]+$/.test(s) && s.length <= 8) {
      // 短的纯字母字符串很可能是常见单词
      const commonWords = ['main', 'root', 'user', 'home', 'test', 'data', 'info', 'demo', 'page', 'app', 'api', 'web'];
      if (commonWords.includes(s.toLowerCase())) {
        return false;
      }
    }
    // 4. 基础规则2：字符集合规 + 填充符位置合法
    // 标准Base64字符集：A-Z, a-z, 0-9, +, /；Base64URL变体：-, _；填充符：=（仅允许在末尾，最多2个）
    const base64Pattern = /^[A-Za-z0-9+/\-_]+(={0,2})$/;
    if (!base64Pattern.test(s)) {
      return false;
    }

    // 4. 核心验证：尝试解码（排除"格式合规但无效"的情况）
    let decodedData: string;
    try {
      // 先尝试标准Base64解码（处理+、/）
      decodedData = atob(s);
    } catch {
      try {
        // 若标准解码失败，尝试Base64URL解码（处理-、_）
        const normalized = s.replace(/-/g, '+').replace(/_/g, '/');
        // 补充填充符（Base64URL可能省略填充符）
        const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
        decodedData = atob(padded);
      } catch {
        return false;
      }
    }

    // 5. 增强验证：解码后数据的"合理性"（避免纯随机二进制的误判）
    // 使用新的严格验证逻辑，包含乱码检测和HTML显示能力检查
    return isValidUtf8OrText(decodedData);
  } catch {
    return false;
  }
};

/**
 * 检查解码后的数据是否是有效的UTF-8文本或可打印文本
 * @param decodedData 解码后的二进制数据字符串
 * @returns 是否为有效的文本数据
 */
const isValidUtf8OrText = (decodedData: string): boolean => {
  if (!decodedData || decodedData.length === 0) {
    return false;
  }

  // 1. 尝试UTF-8验证
  try {
    if (typeof TextDecoder !== 'undefined') {
      const decoder = new TextDecoder('utf-8', { fatal: true });
      const bytes = new Uint8Array(decodedData.length);
      for (let i = 0; i < decodedData.length; i++) {
        bytes[i] = decodedData.charCodeAt(i) & 0xff;
      }

      const text = decoder.decode(bytes);
      // 如果UTF-8解码成功，检查是否包含有意义的可读字符
      const hasReadableChars = /[a-zA-Z0-9\u4e00-\u9fff\s.,!?;:(){}[\]"'-]/.test(text);
      const hasLetters = /[a-zA-Z\u4e00-\u9fff]/.test(text); // 必须包含字母

      if (hasReadableChars && hasLetters) {
        // 如果UTF-8解码成功且包含有意义字符，直接返回true
        // 不再需要HTML显示检查，因为UTF-8本身就保证了内容的有效性
        return true;
      }
    }
  } catch {
    // UTF-8解码失败，继续其他检查
  }

  // 2. 检查是否主要由ASCII可打印字符组成
  let printableCount = 0;
  const totalCount = decodedData.length;

  for (let i = 0; i < totalCount; i++) {
    const code = decodedData.charCodeAt(i) & 0xff;
    if (
      (code >= 32 && code <= 126) || // ASCII可打印字符
      code === 9 ||
      code === 10 ||
      code === 13
    ) {
      // 常见空白字符
      printableCount++;
    }
  }

  // 如果可打印字符比例低于70%，认为不是有效文本
  const isHighlyPrintable = printableCount / totalCount >= 0.7;

  // 结合HTML显示能力检查
  return isHighlyPrintable && isHtmlDisplayable(decodedData);
};

/**
 * 检查解码后的内容是否包含乱码
 * @param decodedData 解码后的数据
 * @returns 是否包含乱码（true表示有乱码，应该排除）
 */
const hasGarbledText = (decodedData: string): boolean => {
  if (!decodedData || decodedData.length === 0) {
    return true; // 空内容视为乱码
  }

  let controlCharCount = 0;
  let extendedCharCount = 0;
  let printableCharCount = 0;
  const totalCount = decodedData.length;

  for (let i = 0; i < totalCount; i++) {
    const code = decodedData.charCodeAt(i) & 0xff;

    if (code >= 32 && code <= 126) {
      // ASCII可打印字符
      printableCharCount++;
    } else if (code >= 128 && code <= 255) {
      // 扩展ASCII字符，可能是乱码
      extendedCharCount++;
    } else if (code < 32 && code !== 9 && code !== 10 && code !== 13) {
      // 控制字符（排除常见的tab、换行、回车）
      controlCharCount++;
    }
  }

  const extendedRatio = extendedCharCount / totalCount;
  const printableRatio = printableCharCount / totalCount;

  // 判断为乱码的条件：
  // 1. 扩展字符比例过高（超过30%）
  // 2. 包含控制字符
  // 3. 可打印字符比例过低（低于60%）
  return extendedRatio > 0.3 || controlCharCount > 0 || printableRatio < 0.6;
};

/**
 * 检查解码后的内容是否可以在HTML中正常显示
 * @param decodedData 解码后的数据
 * @returns 是否可以在HTML中显示
 */
const isHtmlDisplayable = (decodedData: string): boolean => {
  if (!decodedData || decodedData.length === 0) {
    return false;
  }

  // 首先检查是否包含乱码
  if (hasGarbledText(decodedData)) {
    return false;
  }

  let htmlDisplayableCount = 0;
  const totalCount = decodedData.length;

  for (let i = 0; i < totalCount; i++) {
    const code = decodedData.charCodeAt(i) & 0xff;

    // HTML中可安全显示的字符：
    // - ASCII可打印字符（32-126），但排除 < > & 以避免HTML注入
    // - 常见空白字符：tab(9), 换行(10), 回车(13)
    const isHtmlSafe =
      (code >= 32 && code <= 126 && code !== 60 && code !== 62 && code !== 38) ||
      code === 9 ||
      code === 10 ||
      code === 13;

    if (isHtmlSafe) {
      htmlDisplayableCount++;
    }
  }

  // 要求至少80%的字符可以在HTML中安全显示
  return htmlDisplayableCount / totalCount >= 0.8;
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

    // 尝试解码 Unicode（允许混合存在 \uXXXX 与 \xXX）
    const decoded = str
      .replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => {
        return String.fromCharCode(parseInt(code, 16));
      })
      .replace(/\\x([0-9a-fA-F]{2})/g, (_, code) => {
        return String.fromCharCode(parseInt(code, 16));
      });

    // 必须有变化
    if (decoded === str) {
      return false;
    }

    // 检查解码后的内容是否可读
    return isDecodedTextReadable(decoded);
  } catch {
    return false;
  }
};

/**
 * 检查解码后的文本是否可读
 * @param decoded 解码后的字符串
 * @returns 是否可读
 */
const isDecodedTextReadable = (decoded: string): boolean => {
  if (!decoded || decoded.length === 0) {
    return false;
  }

  // 尝试常见文本编码进行验证
  if (tryCommonTextEncodings(decoded)) {
    return true;
  }

  // 统计字符类型
  let printableCount = 0; // 可打印字符 (32-126)
  let extendedCount = 0; // 扩展字符 (128-255, Latin-1)
  let unicodeCount = 0; // Unicode字符 (> 255)
  let whitespaceCount = 0; // 常见空白字符
  let controlCount = 0; // 控制字符

  for (let i = 0; i < decoded.length; i++) {
    const code = decoded.charCodeAt(i);

    if (code >= 32 && code <= 126) {
      printableCount++;
    } else if (code === 9 || code === 10 || code === 13 || code === 32) {
      whitespaceCount++; // tab, newline, carriage return, space
    } else if (code >= 128 && code <= 255) {
      extendedCount++; // Latin-1 扩展字符
    } else if (code > 255) {
      unicodeCount++; // Unicode 字符（包括中文等）
    } else {
      controlCount++; // 其他控制字符
    }
  }

  const total = decoded.length;
  const readableRatio = (printableCount + extendedCount + unicodeCount + whitespaceCount) / total;
  const controlRatio = controlCount / total;

  // 更宽松的判断标准：
  // 1. 允许少量控制字符（如二进制数据中的控制字符）
  // 2. 主要内容应该是可读的
  // 3. 控制字符比例不能太高

  // 如果控制字符比例超过30%，认为不可读
  if (controlRatio > 0.3) {
    return false;
  }

  // 如果可读字符比例超过70%，认为可读
  if (readableRatio >= 0.7) {
    return true;
  }

  // 对于短文本，更宽松的标准
  if (total <= 10) {
    // 短文本：至少50%可读字符，且控制字符不超过20%
    return readableRatio >= 0.5 && controlRatio <= 0.2;
  }

  // 检查是否包含有意义的文本模式
  const hasLetters = /[a-zA-Z\u4e00-\u9fff]/.test(decoded);
  const hasNumbers = /\d/.test(decoded);
  const hasPunctuation = /[.,:;!?(){}[\]"']/.test(decoded);

  // 如果包含字母、数字或标点符号，且可读比例合理，认为可读
  if ((hasLetters || hasNumbers || hasPunctuation) && readableRatio >= 0.6) {
    return true;
  }

  // 默认：可读比例需要达到80%
  return readableRatio >= 0.8;
};

/**
 * 尝试常见文本编码来验证文本可读性
 * @param decoded 解码后的字符串
 * @returns 是否通过编码验证
 */
const tryCommonTextEncodings = (decoded: string): boolean => {
  try {
    // 1. 尝试UTF-8验证
    if (typeof TextEncoder !== 'undefined' && typeof TextDecoder !== 'undefined') {
      const encoder = new TextEncoder();
      const decoder = new TextDecoder('utf-8', { fatal: true });

      try {
        const bytes = encoder.encode(decoded);
        const reDecoded = decoder.decode(bytes);
        if (reDecoded === decoded) {
          // UTF-8 编码/解码成功，检查内容是否有意义
          return isTextContentMeaningful(decoded);
        }
      } catch {
        // UTF-8 验证失败，继续尝试其他方法
      }
    }

    // 2. 检查是否为有效的Latin-1字符序列
    let hasExtendedLatin = false;
    let hasValidContent = false;

    for (let i = 0; i < decoded.length; i++) {
      const code = decoded.charCodeAt(i);

      // 检查是否包含Latin-1扩展字符
      if (code >= 128 && code <= 255) {
        hasExtendedLatin = true;
      }

      // 检查是否包含有意义的内容
      if ((code >= 32 && code <= 126) || code > 127) {
        hasValidContent = true;
      }
    }

    // 如果包含Latin-1扩展字符或有效内容，进一步验证
    if (hasExtendedLatin || hasValidContent) {
      return isTextContentMeaningful(decoded);
    }

    return false;
  } catch {
    return false;
  }
};

/**
 * 检查文本内容是否有意义（更宽松的标准）
 * @param text 文本内容
 * @returns 是否有意义
 */
const isTextContentMeaningful = (text: string): boolean => {
  if (!text || text.length < 1) {
    return false;
  }

  // 检查是否包含中文字符
  if (/[\u4e00-\u9fff]/.test(text)) {
    return true;
  }

  // 检查是否包含常见的英文单词模式
  if (/[a-zA-Z]{2,}/.test(text)) {
    return true;
  }

  // 检查是否包含数字和字母的组合
  if (/[a-zA-Z]/.test(text) && /\d/.test(text) && text.length >= 3) {
    return true;
  }

  // 检查是否包含常见的标点符号和文本结构
  if (/[.,:;!?(){}[\]"']/.test(text) && (/[a-zA-Z]/.test(text) || /\d/.test(text))) {
    return true;
  }

  // 检查是否为连续的可打印字符序列（如ASCII表）
  let printableRun = 0;
  let maxPrintableRun = 0;

  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    if (code >= 32 && code <= 126) {
      printableRun++;
      maxPrintableRun = Math.max(maxPrintableRun, printableRun);
    } else {
      printableRun = 0;
    }
  }

  // 如果有较长的可打印字符序列，认为有意义
  if (maxPrintableRun >= Math.min(10, text.length * 0.5)) {
    return true;
  }

  // 对于包含扩展字符的内容，更宽松的判断
  const extendedCharCount = Array.from(text).filter(char => char.charCodeAt(0) > 127).length;
  if (extendedCharCount > 0 && extendedCharCount / text.length >= 0.1) {
    return true;
  }

  return false;
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
    if (decoded === str) {
      return false;
    }

    return canDecodeUtf8(decoded) || /[\x20-\x7E]/.test(decoded);
  } catch {
    return false;
  }
};
