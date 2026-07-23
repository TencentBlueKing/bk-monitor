/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import {
  applyPositionalWildcard,
  buildContainsQuery,
  buildPhraseQuery,
  escapeQueryStringPhraseLiteral,
  escapeQueryStringWildcardLiteral,
} from '../lexer/escape';
import type { AstNode, QueryCompilerOptions, SelectionContext } from '../types';

const buildLeaf = (
  node: AstNode,
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): string => {
  const value = String(node.value ?? '');
  if (!value) return '';

  const neg = node.negative ? 'NOT ' : '';

  // 全局检索：引号短语
  if (node.matchMode === 'global' || node.type === 'Global' || !node.field) {
    const inner = options.escape ? escapeQueryStringPhraseLiteral(value) : value;
    return `${neg}"${inner}"`;
  }

  // keyword / flattened：按字段分词位置补通配（唯一分词不加 *）
  if (node.matchMode === 'wildcard') {
    const wildOpts = {
      isSoleToken: Boolean(ctx.isSoleToken),
      tokenIndex: ctx.tokenIndex,
      tokenCount: ctx.tokenCount,
    };
    if (!options.escape) {
      const wild = applyPositionalWildcard(value, ctx.fullText, wildOpts);
      return `${neg}${node.field}: ${wild}`;
    }
    try {
      return `${neg}${buildContainsQuery(node.field, value, ctx.fullText, wildOpts)}`;
    } catch {
      // 含 <> 无法进 wildcard：降级为引号短语
      return `${neg}${buildPhraseQuery(node.field, value)}`;
    }
  }

  // text / 其他：引号短语
  if (!options.escape) {
    return `${neg}${node.field}: "${value}"`;
  }
  return `${neg}${buildPhraseQuery(node.field, value)}`;
};

const buildNode = (
  node: AstNode,
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): string => {
  if (node.type === 'Root') {
    const parts = (node.children ?? []).map(child => buildNode(child, ctx, options)).filter(Boolean);
    return parts.join(` ${options.defaultBoolean} `);
  }

  if (node.type === 'Boolean') {
    const op = node.operator || options.defaultBoolean;
    const parts = (node.children ?? []).map(child => buildNode(child, ctx, options)).filter(Boolean);
    return parts.join(` ${op} `);
  }

  return buildLeaf(node, ctx, options);
};

/**
 * 仅压缩「引号外」空白；保留短语内部空白与 `\ ` 转义空格。
 * 禁止对整串做 /\s+/g，否则会破坏 `"a  b"` / 换行字面量。
 */
const collapseOutsideQuotes = (input: string): string => {
  let result = '';
  let i = 0;
  let inQuote = false;
  while (i < input.length) {
    const ch = input[i];
    if (ch === '\\' && i + 1 < input.length) {
      result += ch + input[i + 1];
      i += 2;
      continue;
    }
    if (ch === '"') {
      inQuote = !inQuote;
      result += ch;
      i += 1;
      continue;
    }
    if (!inQuote && (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r')) {
      if (result && !result.endsWith(' ')) {
        result += ' ';
      }
      while (i < input.length && /\s/.test(input[i])) {
        i += 1;
      }
      continue;
    }
    result += ch;
    i += 1;
  }
  return result.trim();
};

/** Query String Builder（语句模式主输出；转义仅在 leaf 发生一次） */
export const buildQueryString = (
  ast: AstNode,
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): string => collapseOutsideQuotes(buildNode(ast, ctx, options));

export {
  escapeQueryStringPhraseLiteral,
  escapeQueryStringWildcardLiteral,
  buildContainsQuery,
  buildPhraseQuery,
};
