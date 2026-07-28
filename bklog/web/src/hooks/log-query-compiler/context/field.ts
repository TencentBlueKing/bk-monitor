/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { LogFieldType, SelectionContext } from '../types';

const KEYWORD_LIKE = new Set(['keyword', 'flattened']);
const TEXT_LIKE = new Set(['text', 'string']);
const NUMBER_LIKE = new Set([
  'long', 'integer', 'short', 'byte', 'double', 'float', 'half_float', 'scaled_float', 'number',
]);
const DATE_LIKE = new Set(['date', 'date_nanos']);

export const isKeywordLikeField = (fieldType?: string) => KEYWORD_LIKE.has(String(fieldType ?? ''));
export const isTextLikeField = (fieldType?: string) => TEXT_LIKE.has(String(fieldType ?? ''));
export const isNumberLikeField = (fieldType?: string) => NUMBER_LIKE.has(String(fieldType ?? ''));
export const isDateLikeField = (fieldType?: string) => DATE_LIKE.has(String(fieldType ?? ''));

export const normalizeFieldType = (fieldType?: string): LogFieldType => {
  const t = String(fieldType ?? '').trim();
  if (!t) return 'text';
  if (t === 'number') return 'long';
  return t as LogFieldType;
};

/** 从项目 field meta 构造 SelectionContext */
export const buildSelectionContext = (params: {
  text: string;
  field?: string | Record<string, any>;
  fieldType?: string;
  fullText?: string;
  row?: Record<string, any>;
  operatorHint?: string;
  startOffset?: number;
  endOffset?: number;
}): SelectionContext => {
  const fieldObj = typeof params.field === 'object' && params.field ? params.field : undefined;
  const fieldName = typeof params.field === 'string'
    ? params.field
    : (fieldObj?.field_name ?? '');
  const fieldType = normalizeFieldType(
    params.fieldType
    ?? fieldObj?.field_type
    ?? '',
  );

  return {
    text: String(params.text ?? ''),
    fullText: params.fullText,
    column: fieldName,
    field: fieldName,
    fieldType,
    row: params.row,
    operatorHint: params.operatorHint,
    startOffset: params.startOffset,
    endOffset: params.endOffset,
    mapping: fieldObj,
  };
};
