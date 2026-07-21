/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import { mapOperatorHint } from './analyzer/mapping';
import { resolveFields } from './analyzer/resolver';
import { analyzeSemantics } from './analyzer/semantic';
import { buildQueryString } from './builder/query-string';
import { buildUiCondition } from './builder/ui-condition';
import { normalizeSelectionContext } from './context/selection';
import { normalizeInput, normalizeInputLight } from './lexer/normalize';
import { shieldProtectedSpans } from './lexer/shield';
import { tokenize } from './lexer/tokenizer';
import { parseTokens } from './parser/parser';
import {
  DEFAULT_COMPILER_OPTIONS,
  type CompileResult,
  type CompilerOutputMode,
  type QueryCompilerOptions,
  type SelectionContext,
} from './types';

export type CompileInput = SelectionContext;

const mergeOptions = (
  outputMode?: CompilerOutputMode,
  options?: Partial<QueryCompilerOptions>,
): QueryCompilerOptions => ({
  ...DEFAULT_COMPILER_OPTIONS,
  ...options,
  output: outputMode ?? options?.output ?? DEFAULT_COMPILER_OPTIONS.output,
});

/**
 * 全局唯一 Compiler 入口。
 *
 * Pipeline（无状态）：
 * SelectionContext → Normalize → Shield → Lexer → Parser
 * → Semantic → FieldResolver → Builder → Output
 */
export const compile = (
  selectionContext: SelectionContext,
  outputMode: CompilerOutputMode = 'query-string',
  options?: Partial<QueryCompilerOptions>,
): CompileResult => {
  const opts = mergeOptions(outputMode, options);
  const ctx = normalizeSelectionContext(selectionContext);

  // 1) Normalize
  const normalizedText = opts.normalizeMode === 'light'
    ? normalizeInputLight(ctx.text)
    : normalizeInput(ctx.text);
  if (!normalizedText) {
    return {
      queryString: '',
      ast: { type: 'Root', children: [] },
      tokens: [],
      options: opts,
    };
  }

  // 2) Shield（light 模式跳过，避免已解析 Value 内引号被抽槽）
  const shielded = opts.normalizeMode === 'light'
    ? { text: normalizedText, slots: [] }
    : shieldProtectedSpans(normalizedText);

  // 3) Lexer
  const tokens = tokenize(shielded.text, { slots: shielded.slots });

  // 4) Parser → AST
  let ast = parseTokens(tokens, { ...ctx, text: normalizedText }, opts);

  // 5) Semantic + Field resolve + operator mapping
  ast = analyzeSemantics(ast, ctx, opts);
  ast = resolveFields(ast, ctx);
  ast = mapOperatorHint(ast, ctx);

  // 6) Builder
  const queryString = buildQueryString(ast, ctx, opts);
  const uiCondition = buildUiCondition(ast, ctx);

  return {
    queryString,
    uiCondition,
    ast,
    tokens,
    options: opts,
  };
};

/**
 * 语句模式快捷编译：按字段类型输出 query string。
 */
export const compileToQueryString = (
  selectionContext: SelectionContext,
  options?: Partial<QueryCompilerOptions>,
) => compile(selectionContext, 'query-string', {
  tokenizerMode: 'phrase',
  quoteStrategy: 'auto',
  wildcardForKeyword: true,
  ...options,
}).queryString;

/**
 * 从「已解析的 field + value + fieldType」直接编译（跳过 Smart 拆词与深度 Normalize）。
 * 适用于：划词最小分词补齐之后、点击分词、Tag 添加等上游已完成 Value 语义的场景。
 *
 * 返回完整 CompileResult：语句模式用 queryString，UI 模式用 uiCondition。
 */
export const compileFieldValue = (params: {
  field: string;
  value: string;
  fieldType?: string;
  fullText?: string;
  operatorHint?: string;
  negative?: boolean;
}): CompileResult => compile({
  text: params.value,
  field: params.field,
  column: params.field,
  fieldType: params.fieldType as SelectionContext['fieldType'],
  fullText: params.fullText,
  operatorHint: params.operatorHint,
}, 'query-string', {
  tokenizerMode: 'phrase',
  negative: params.negative,
  detectField: false,
  normalizeMode: 'light',
});

/** 仅取语句模式 query string（兼容旧调用） */
export const compileFieldValueToQueryString = (
  params: Parameters<typeof compileFieldValue>[0],
) => compileFieldValue(params).queryString;
