/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import { compileFieldValue } from './compiler';
import { escapeQueryStringPhraseLiteral } from './lexer/escape';

export type AddToSearchMode = 'ui' | 'sql';

export type AddToSearchInput = {
  field: string;
  value: string;
  fieldType?: string;
  fullText?: string;
  operatorHint?: string;
  /** keyword/flattened：字段唯一分词时语句模式不加 * */
  isSoleToken?: boolean;
  /** 命中分词在字段分词列表中的下标 */
  tokenIndex?: number;
  /** 字段可检索分词总数 */
  tokenCount?: number;
  /** ui | sql；也可传 storage SEARCH_TYPE 对应的 dic 值 */
  searchMode: AddToSearchMode;
};

export type AddToSearchPayload = {
  field: string;
  operator: string;
  value: string[];
  fieldType?: string;
  fullPlain?: string;
  /** 语句模式专用；UI 模式为空 */
  queryString?: string;
};

const isNegativeOperator = (operator?: string) =>
  ['is not', 'not contains match phrase', 'not contains', '!=', 'not'].includes(String(operator ?? ''));

/**
 * 「添加到本次检索」唯一出口载荷。
 *
 * - UI：compileFieldValue().uiCondition → addition
 * - 语句：compileFieldValue().queryString → keyword 片段
 *
 * 点击分词 / 划词补齐之后，只应调用此函数，禁止旁路拼装。
 */
export const resolveAddToSearch = (input: AddToSearchInput): AddToSearchPayload => {
  const field = String(input.field ?? '');
  const value = String(input.value ?? '').replace(/<\/?mark>/gim, '').trim();
  const fieldType = input.fieldType;
  const fullPlainRaw = input.fullText == null ? '' : String(input.fullText).replace(/<\/?mark>/gim, '').trim();
  const fullPlain = fullPlainRaw && fullPlainRaw !== '--' && fullPlainRaw !== '[object Object]'
    ? fullPlainRaw
    : undefined;
  const operatorHint = input.operatorHint || 'contains match phrase';
  const negative = isNegativeOperator(operatorHint);
  const isFulltext = !field || field === '*';

  // keyword/flattened：唯一分词 / 整值相等 → 强制无通配
  const soleByValue = Boolean(fullPlain && fullPlain === value);
  const soleByTokenMeta = Boolean(
    input.isSoleToken
    || (typeof input.tokenCount === 'number' && input.tokenCount === 1 && (
      !fullPlain || soleByValue || !value
    )),
  );
  const isSoleToken = soleByTokenMeta || soleByValue;
  const tokenCount = input.tokenCount ?? (isSoleToken ? 1 : undefined);
  const tokenIndex = input.tokenIndex ?? (isSoleToken ? 0 : undefined);

  if (isFulltext) {
    const inner = escapeQueryStringPhraseLiteral(value);
    if (input.searchMode === 'sql') {
      return {
        field: '*',
        operator: negative ? 'not contains match phrase' : 'contains match phrase',
        value: [value],
        fieldType,
        fullPlain,
        queryString: negative ? `NOT "${inner}"` : `"${inner}"`,
      };
    }
    return {
      field: '*',
      operator: negative ? 'not contains match phrase' : 'contains match phrase',
      value: [value],
      fieldType,
      fullPlain,
    };
  }

  const compiled = compileFieldValue({
    field,
    value,
    fieldType,
    fullText: fullPlain || (isSoleToken ? value : undefined),
    operatorHint,
    negative,
    isSoleToken,
    tokenIndex,
    tokenCount,
  });

  if (input.searchMode === 'sql') {
    return {
      field,
      operator: operatorHint,
      value: [value],
      fieldType,
      fullPlain,
      queryString: compiled.queryString,
    };
  }

  const ui = compiled.uiCondition;
  return {
    field: ui?.field || field,
    operator: ui?.operator || operatorHint,
    value: ui?.value || [value],
    fieldType,
    fullPlain,
  };
};
