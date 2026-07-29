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
  /**
   * 语句模式是否转义 ES/Query String 保留字符（wildcard 路径）。
   * - true：划词弹层「添加到本次检索」
   * - false：点击分词
   * 默认 true（兼容旧调用）。
   */
  escape?: boolean;
  /**
   * 语句模式 Value 完全匹配：输出 KEY: "{value}"（引号短语）。
   * 点击分词（添加到本次检索 / 新建检索）为 true；划词为 false（通配逻辑）。
   */
  exactPhrase?: boolean;
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

  // 划词：escape + 通配；点击分词：exactPhrase → KEY: "{value}"
  const shouldEscape = input.escape !== false;
  const exactPhrase = Boolean(input.exactPhrase);

  if (isFulltext) {
    const inner = shouldEscape || exactPhrase ? escapeQueryStringPhraseLiteral(value) : value;
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

  // 点击分词语句模式：完全匹配短语，与划词通配路径分离
  if (input.searchMode === 'sql' && exactPhrase) {
    const inner = escapeQueryStringPhraseLiteral(value);
    return {
      field,
      operator: operatorHint,
      value: [value],
      fieldType,
      fullPlain,
      queryString: negative ? `NOT ${field}: "${inner}"` : `${field}: "${inner}"`,
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
    escape: shouldEscape,
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
  // 保留 new-search-page-is，供 setQueryCondition 识别「新建检索」开新页
  const preserveNewSearch = operatorHint === 'new-search-page-is';
  return {
    field: ui?.field || field,
    operator: preserveNewSearch ? operatorHint : (ui?.operator || operatorHint),
    value: ui?.value || [value],
    fieldType,
    fullPlain,
  };
};
