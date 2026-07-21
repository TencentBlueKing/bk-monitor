/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 兼容层：语句模式工具统一委托给 @/hooks/log-query-compiler。
 * 新代码请直接使用 compile / compileFieldValue / escapeQueryValue。
 */

import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '@/store/store.type';
import {
  applyPositionalWildcard,
  compileFieldValue,
  escapeQueryValue,
  isKeywordLikeField,
  isTextLikeField,
} from '@/hooks/log-query-compiler';

const CONTAINS_OPERATORS = new Set(['contains match phrase', 'not contains match phrase', 'contains', 'not contains']);

export const KEYWORD_LIKE_FIELD_TYPES = new Set(['keyword', 'flattened']);

export const isSqlSearchMode = (storageSearchType?: number | string) => {
  if (storageSearchType === undefined || storageSearchType === null || storageSearchType === '') {
    return false;
  }
  return SEARCH_MODE_DIC[storageSearchType] === 'sql';
};

export const isContainsOperator = (operator?: string) => CONTAINS_OPERATORS.has(String(operator ?? ''));

export const isKeywordLikeFieldType = (fieldType?: string) => isKeywordLikeField(fieldType);

export const isTextFieldType = (fieldType?: string) => isTextLikeField(fieldType);

/** @deprecated 使用 escapeQueryValue */
export const escapeEsReservedChars = (
  value: string,
  options: { keepWildcards?: boolean } = {},
) => escapeQueryValue(value, options);

/** @deprecated 使用 applyPositionalWildcard */
export const formatSqlContainsWildcardValue = (selectedValue: string, fullPlainValue?: string) =>
  applyPositionalWildcard(selectedValue, fullPlainValue);

export const formatSqlContainsValues = (
  operator: string,
  values: string[],
  fullPlainValue: string | undefined,
  storageSearchType?: number | string,
  fieldType?: string,
) => {
  if (!isSqlSearchMode(storageSearchType) || !isContainsOperator(operator)) {
    return values;
  }
  if (fieldType && !isKeywordLikeFieldType(fieldType)) {
    return values;
  }
  return (values ?? []).map((item) => {
    const escaped = escapeQueryValue(item, { keepWildcards: true });
    return applyPositionalWildcard(escaped, fullPlainValue);
  });
};

/**
 * 语句模式字段类型格式化 —— 委托 Compiler，返回仍兼容旧 operator/value 结构。
 * 完整 query string 请直接用 compileFieldValue。
 */
export const resolveSqlFieldTypeFormat = (params: {
  fieldType?: string;
  operator: string;
  values: string[];
  fullPlainValue?: string;
  isNegative?: boolean;
  field?: string;
}): { operator: string; values: string[]; queryString?: string } => {
  const { fieldType, operator, values, fullPlainValue, field } = params;
  const isNegative = params.isNegative
    || ['is not', 'not contains match phrase', 'not contains', '!='].includes(operator);
  const raw = values?.[0] ?? '';

  const queryString = compileFieldValue({
    field: field || '_field',
    value: raw,
    fieldType,
    fullText: fullPlainValue,
    operatorHint: operator,
    negative: isNegative,
  }).queryString;

  if (isTextFieldType(fieldType)) {
    return {
      operator: isNegative ? 'is not' : 'is',
      values: [raw],
      queryString,
    };
  }

  if (isKeywordLikeFieldType(fieldType)) {
    const escaped = escapeQueryValue(raw, { keepWildcards: true });
    const wild = applyPositionalWildcard(escaped, fullPlainValue);
    return {
      operator: isNegative ? 'not contains match phrase' : 'contains match phrase',
      values: [wild],
      queryString,
    };
  }

  const full = fullPlainValue && fullPlainValue !== '--' ? fullPlainValue : raw;
  return {
    operator: isNegative ? 'is not' : 'is',
    values: full ? [full] : values,
    queryString,
  };
};

export { BK_LOG_STORAGE, SEARCH_MODE_DIC, compileFieldValue, escapeQueryValue };
