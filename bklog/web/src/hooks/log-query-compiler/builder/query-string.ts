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

  // keyword / flattened：wildcard contains
  if (node.matchMode === 'wildcard') {
    if (!options.escape) {
      const wild = applyPositionalWildcard(value, ctx.fullText);
      return `${neg}${node.field}: ${wild}`;
    }
    try {
      return `${neg}${buildContainsQuery(node.field, value, ctx.fullText)}`;
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

/** Query String Builder（语句模式主输出） */
export const buildQueryString = (
  ast: AstNode,
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): string => buildNode(ast, ctx, options).replace(/\s+/g, ' ').trim();

export {
  escapeQueryStringPhraseLiteral,
  escapeQueryStringWildcardLiteral,
  buildContainsQuery,
  buildPhraseQuery,
};
