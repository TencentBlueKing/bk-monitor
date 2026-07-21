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

export type PositionalWildcardOptions = {
  /**
   * 当前命中分词是字段 VALUE 的唯一可检索分词。
   * 语句模式 keyword/flattened：输出 KEY: Value（无前后 *）。
   */
  isSoleToken?: boolean;
  /**
   * 命中分词在字段「可检索分词列表」中的下标（0-based）。
   * 与 tokenCount 同时提供时，优先生效：
   * - 唯一 → 无 *
   * - 首位 → value*
   * - 末位 → *value
   * - 中间 → *value*
   */
  tokenIndex?: number;
  /** 字段可检索分词总数 */
  tokenCount?: number;
};

/** 按字符串在完整 VALUE 中的字符位置判定（部分划词兜底） */
const resolveWildcardAffixByChar = (
  selected: string,
  plain: string,
): { prefix: boolean; suffix: boolean } => {
  if (!plain || plain === '--') {
    return { prefix: true, suffix: true };
  }
  if (plain === selected) {
    return { prefix: false, suffix: false };
  }
  if (plain.startsWith(selected)) {
    return { prefix: false, suffix: true };
  }
  if (plain.endsWith(selected)) {
    return { prefix: true, suffix: false };
  }
  return { prefix: true, suffix: true };
};

/**
 * 按字段分词列表位置判定前后通配。
 * 优先 tokenIndex/tokenCount；无分词元信息时回退到字符位置。
 */
export const resolveWildcardAffix = (
  selectedValue: string,
  fullPlainValue?: string,
  options?: PositionalWildcardOptions,
): { prefix: boolean; suffix: boolean } => {
  const selected = String(selectedValue ?? '');
  if (!selected || selected.includes('*')) {
    return { prefix: false, suffix: false };
  }

  if (options?.isSoleToken) {
    return { prefix: false, suffix: false };
  }

  const plain = String(fullPlainValue ?? '');
  const count = options?.tokenCount;
  const index = options?.tokenIndex;

  if (
    typeof count === 'number'
    && count > 0
    && typeof index === 'number'
    && index >= 0
    && index < count
  ) {
    // 字段只有一个分词：整词不加 *；部分划词按字符位置补通配
    if (count === 1) {
      if (!plain || plain === '--' || plain === selected) {
        return { prefix: false, suffix: false };
      }
      return resolveWildcardAffixByChar(selected, plain);
    }
    // 首位 / 中间 / 末位
    if (index === 0) {
      return { prefix: false, suffix: true };
    }
    if (index === count - 1) {
      return { prefix: true, suffix: false };
    }
    return { prefix: true, suffix: true };
  }

  // 无分词位置元信息：回退字符位置 / 整值相等
  return resolveWildcardAffixByChar(selected, plain);
};

/** 按完整 VALUE 位置补通配（不转义；转义须在判定之后） */
export const applyPositionalWildcard = (
  selectedValue: string,
  fullPlainValue?: string,
  options?: PositionalWildcardOptions,
): string => {
  const selected = String(selectedValue ?? '');
  if (!selected) return selected;
  if (selected.includes('*')) return selected;

  const { prefix, suffix } = resolveWildcardAffix(selected, fullPlainValue, options);
  return `${prefix ? '*' : ''}${selected}${suffix ? '*' : ''}`;
};

/**
 * keyword/flattened 语句片段。
 * 先按原文判定通配位置，再转义字面量，避免 a:b 全值被误写成 *a\:b*。
 */
export const buildContainsQuery = (
  field: string,
  selectedText: string,
  fullPlain?: string,
  options?: PositionalWildcardOptions,
): string => {
  const selected = String(selectedText ?? '');
  if (!selected) {
    return `${field}: `;
  }
  if (selected.includes('*')) {
    return `${field}: ${selected}`;
  }

  const { prefix, suffix } = resolveWildcardAffix(selected, fullPlain, options);
  const escapedValue = escapeQueryStringWildcardLiteral(selected);
  return `${field}: ${prefix ? '*' : ''}${escapedValue}${suffix ? '*' : ''}`;
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
