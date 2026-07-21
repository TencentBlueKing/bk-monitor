/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

export { compile, compileFieldValue, compileFieldValueToQueryString, compileToQueryString } from './compiler';
export { buildSelectionContext, isKeywordLikeField, isTextLikeField, normalizeFieldType } from './context/field';
export {
  escapeQueryValue,
  escapeQueryStringPhraseLiteral,
  escapeQueryStringWildcardLiteral,
  applyPositionalWildcard,
  buildContainsQuery,
  buildPhraseQuery,
} from './lexer/escape';
export { normalizeInput } from './lexer/normalize';
export {
  resolveAddToSearch,
  type AddToSearchInput,
  type AddToSearchMode,
  type AddToSearchPayload,
} from './resolve-add-to-search';
export type {
  AstNode,
  CompileResult,
  CompilerOutputMode,
  LexToken,
  LogFieldType,
  QueryCompilerOptions,
  SelectionContext,
  TokenizerMode,
} from './types';
export { DEFAULT_COMPILER_OPTIONS } from './types';
