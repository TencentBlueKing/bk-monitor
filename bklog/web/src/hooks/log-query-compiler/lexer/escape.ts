/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

/**
 * Query String 保留字（用于 wildcard term 内部字面量）。
 *
 * 与 Lucene/ES query_string 对齐；刻意排除连字符 `-`：
 * 词内连字符（bk-system）转义为 bk\-system 会导致匹配副作用，
 * 产品约定保持原文：key: *bk-system*。
 *
 * 必须单次 replace，避免把本次插入的反斜杠再次转义。
 */
const QUERY_STRING_WILDCARD_RESERVED = /&&|\|\||[+\-=!(){}[\]^"~*?:\\/ ]/g;

/**
 * 转义即将放进 wildcard term 内部的用户字面量。
 * 例：a:b"c → a\:b\"c ；空格 → \ 
 *
 * Query String 无法可靠转义 < 和 >，遇到则抛错，由 Builder 降级为 phrase。
 */
export const escapeQueryStringWildcardLiteral = (value: string): string => {
  const text = String(value ?? '');
  if (/[<>]/.test(text)) {
    throw new Error('Query String 不支持包含 < 或 > 的字面量 wildcard');
  }
  // 去掉字符类中的 `-`：产品要求 bk-system 不转义
  return text.replace(/&&|\|\||[+ =!(){}[\]^"~*?:\\/]/g, '\\$&');
};

/**
 * 转义 Query String 双引号短语内部的字面量。
 *
 * abc def     → abc def
 * a "test"    → a \"test\"
 * C:\logs\app → C:\\logs\\app
 */
export const escapeQueryStringPhraseLiteral = (value: string): string =>
  String(value ?? '').replace(/["\\]/g, '\\$&');

/** 按完整 VALUE 位置补通配（不转义；转义须先行） */
export const applyPositionalWildcard = (selectedValue: string, fullPlainValue?: string): string => {
  const selected = String(selectedValue ?? '');
  if (!selected) return selected;
  if (selected.includes('*')) return selected;

  const plain = String(fullPlainValue ?? '');
  if (!plain || plain === '--') return `*${selected}*`;
  if (plain === selected) return selected;
  if (plain.startsWith(selected)) return `${selected}*`;
  if (plain.endsWith(selected)) return `*${selected}`;
  if (plain.includes(selected)) return `*${selected}*`;
  return `*${selected}*`;
};

export const buildContainsQuery = (field: string, selectedText: string, fullPlain?: string): string => {
  const escapedValue = escapeQueryStringWildcardLiteral(selectedText);
  const wild = applyPositionalWildcard(escapedValue, fullPlain);
  return `${field}: ${wild}`;
};

export const buildPhraseQuery = (field: string, selectedText: string): string => {
  const escapedValue = escapeQueryStringPhraseLiteral(selectedText);
  return `${field}: "${escapedValue}"`;
};

/**
 * 兼容旧调用：按场景分派到 phrase / wildcard 转义。
 * @deprecated 新代码请直接用 escapeQueryStringPhraseLiteral / escapeQueryStringWildcardLiteral
 */
export const escapeQueryValue = (
  value: string,
  options: { keepWildcards?: boolean; quoted?: boolean } = {},
): string => {
  if (options.quoted) {
    return escapeQueryStringPhraseLiteral(value);
  }
  try {
    return escapeQueryStringWildcardLiteral(value);
  } catch {
    // 含 <> 时无法做 wildcard 字面量，退回仅转义引号/反斜杠，交给上层改 phrase
    return escapeQueryStringPhraseLiteral(value);
  }
};

export { QUERY_STRING_WILDCARD_RESERVED };
