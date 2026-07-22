/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

const FULLWIDTH_MAP: Record<string, string> = {
  '：': ':',
  '（': '(',
  '）': ')',
  '，': ',',
  '；': ';',
  '｜': '|',
  '＝': '=',
  '！': '!',
  '【': '[',
  '】': ']',
  '｛': '{',
  '｝': '}',
  '／': '/',
  '＂': '"',
  '＇': "'",
  '“': '"',
  '”': '"',
  '‘': "'",
  '’': "'",
  '『': '"',
  '』': '"',
  '「': '"',
  '」': '"',
};

const isInsideQuotes = (text: string, index: number) => {
  let inQuote = false;
  let quoteChar = '';
  for (let i = 0; i < index; i++) {
    const ch = text[i];
    if ((ch === '"' || ch === "'") && text[i - 1] !== '\\') {
      if (!inQuote) {
        inQuote = true;
        quoteChar = ch;
      } else if (ch === quoteChar) {
        inQuote = false;
        quoteChar = '';
      }
    }
  }
  return inQuote;
};

/**
 * Normalize：NFKC、换行、引号/全角统一；引号内空白不压缩。
 */
export const normalizeInput = (input: string): string => {
  let text = String(input ?? '').normalize('NFKC');
  text = text.replace(/\r\n?/g, '\n');

  // 全角 / 弯引号 → 半角 "
  text = text.replace(/./gu, (ch) => FULLWIDTH_MAP[ch] ?? ch);

  // 引号外：\t → space；连续 space 压缩为 1
  let result = '';
  let i = 0;
  while (i < text.length) {
    const ch = text[i];

    if (ch === '"' || ch === "'") {
      // 吃完整引号串（含转义）
      const quote = ch;
      result += '"'; // 统一为 "
      i += 1;
      while (i < text.length) {
        if (text[i] === '\\' && i + 1 < text.length) {
          result += text[i] + text[i + 1];
          i += 2;
          continue;
        }
        if (text[i] === quote) {
          result += '"';
          i += 1;
          break;
        }
        result += text[i];
        i += 1;
      }
      continue;
    }

    if (ch === '\t' || ch === ' ') {
      if (!result.endsWith(' ') && result.length > 0) {
        result += ' ';
      }
      while (i < text.length && (text[i] === ' ' || text[i] === '\t')) {
        i += 1;
      }
      continue;
    }

    if (ch === '\n') {
      if (result && !result.endsWith(' ')) result += ' ';
      i += 1;
      continue;
    }

    result += ch;
    i += 1;
  }

  return result.trim();
};

/**
 * 轻量 Normalize：仅 NFKC + 换行 + 全角标点。
 * 用于上游已解析的 Field Value（如 `"thread": 139...`），避免把内容里的引号当成包裹引号。
 */
export const normalizeInputLight = (input: string): string => {
  let text = String(input ?? '').normalize('NFKC');
  text = text.replace(/\r\n?/g, '\n');
  text = text.replace(/./gu, (ch) => FULLWIDTH_MAP[ch] ?? ch);
  return text;
};

export { isInsideQuotes };
