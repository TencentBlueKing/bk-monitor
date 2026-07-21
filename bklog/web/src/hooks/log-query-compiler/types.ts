/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/** 项目内常见 ES 字段类型（扩展方案中的基础集合） */
export type LogFieldType =
  | 'keyword'
  | 'text'
  | 'flattened'
  | 'date'
  | 'date_nanos'
  | 'ip'
  | 'boolean'
  | 'long'
  | 'integer'
  | 'short'
  | 'byte'
  | 'double'
  | 'float'
  | 'half_float'
  | 'scaled_float'
  | 'object'
  | 'nested'
  | 'string'
  | '__virtual__'
  | (string & {});

export type CompilerOutputMode = 'query-string' | 'dsl' | 'sql' | 'lucene' | 'ui-condition';

export type TokenizerMode = 'smart' | 'strict' | 'token' | 'phrase';

export type QuoteStrategy = 'auto' | 'always' | 'never';

export interface QueryCompilerOptions {
  output: CompilerOutputMode;
  tokenizerMode: TokenizerMode;
  quoteStrategy: QuoteStrategy;
  escape: boolean;
  detectField: boolean;
  defaultBoolean: 'AND' | 'OR';
  preserveSeparator: boolean;
  preserveQuotedString: boolean;
  /** 语句模式：keyword 位置通配 */
  wildcardForKeyword?: boolean;
  /** 是否否定条件 */
  negative?: boolean;
  /**
   * light：仅 NFKC/换行/全角（用于已解析 Field Value，保留内容中的引号与空格）
   * full：完整 Normalize（手工输入 / 原始划词）
   */
  normalizeMode?: 'full' | 'light';
}

export const DEFAULT_COMPILER_OPTIONS: QueryCompilerOptions = {
  output: 'query-string',
  tokenizerMode: 'smart',
  quoteStrategy: 'auto',
  escape: true,
  detectField: true,
  defaultBoolean: 'AND',
  preserveSeparator: true,
  preserveQuotedString: true,
  wildcardForKeyword: true,
  negative: false,
  normalizeMode: 'full',
};

/**
 * Compiler 唯一输入模型。
 * offsets 可选：划词 DOM 场景未必能稳定拿到字符偏移。
 */
export interface SelectionContext {
  /** 划选 / 输入文本 */
  text: string;
  /** 字段完整 VALUE（用于通配位置、最小分词补齐上下文） */
  fullText?: string;
  /** 列名（展示） */
  column?: string;
  /** 检索字段名 */
  field?: string;
  fieldType?: LogFieldType;
  analyzer?: string;
  mapping?: Record<string, any>;
  row?: Record<string, any>;
  startOffset?: number;
  endOffset?: number;
  /** 上游已解析的操作意图（contains / is / not ...） */
  operatorHint?: string;
}

export type TokenKind =
  | 'Identifier'
  | 'Keyword'
  | 'Number'
  | 'Float'
  | 'Boolean'
  | 'IP'
  | 'IPv6'
  | 'MAC'
  | 'UUID'
  | 'Date'
  | 'DateTime'
  | 'Time'
  | 'URL'
  | 'URI'
  | 'Path'
  | 'Email'
  | 'JSON'
  | 'Array'
  | 'Regex'
  | 'Wildcard'
  | 'QuotedString'
  | 'Operator'
  | 'Whitespace'
  | 'Symbol'
  | 'Hash'
  | 'Phrase';

export interface LexToken {
  kind: TokenKind;
  value: string;
  raw: string;
  start: number;
  end: number;
}

export type AstNodeType =
  | 'Root'
  | 'Boolean'
  | 'Comparison'
  | 'Field'
  | 'Phrase'
  | 'Value'
  | 'Exists'
  | 'Range'
  | 'Regex'
  | 'Wildcard'
  | 'Global';

export interface AstNode {
  type: AstNodeType;
  field?: string;
  fieldType?: LogFieldType;
  operator?: string;
  value?: string;
  valueKind?: TokenKind;
  /** query-string 构建策略 */
  matchMode?: 'term' | 'phrase' | 'wildcard' | 'match_phrase' | 'global';
  children?: AstNode[];
  negative?: boolean;
  meta?: Record<string, any>;
}

export interface CompileResult {
  /** 语句模式 query string 片段 */
  queryString: string;
  /** UI addition 条件（可选） */
  uiCondition?: {
    field: string;
    operator: string;
    value: string[];
  };
  ast: AstNode;
  tokens: LexToken[];
  options: QueryCompilerOptions;
}
