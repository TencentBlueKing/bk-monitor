/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { AstNode, LexToken, QueryCompilerOptions, SelectionContext, TokenizerMode } from '../types';
import { findFirstFieldColonIndex, isValueToken } from '../lexer/detector';
import { tokensWithoutWhitespace } from '../lexer/tokenizer';

const GLOBAL_KINDS = new Set(['IP', 'IPv6', 'UUID', 'URL', 'URI', 'MAC', 'Email', 'Hash']);

const joinTokenValues = (tokens: LexToken[]) =>
  tokens.map(t => (t.kind === 'QuotedString' ? t.raw : t.value)).join('');

/**
 * 将连续普通词合并为 Phrase；特殊类型 token 单独成节点。
 */
const buildSmartNodes = (
  tokens: LexToken[],
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): AstNode[] => {
  const meaningful = tokensWithoutWhitespace(tokens);
  const nodes: AstNode[] = [];
  let phraseBuf: LexToken[] = [];

  const flushPhrase = () => {
    if (!phraseBuf.length) return;
    const value = phraseBuf.map(t => t.value).join(' ');
    nodes.push({
      type: 'Phrase',
      field: ctx.field,
      fieldType: ctx.fieldType,
      value,
      valueKind: 'Phrase',
      matchMode: 'phrase',
    });
    phraseBuf = [];
  };

  meaningful.forEach((token) => {
    if (token.kind === 'Operator' || token.kind === 'Keyword') {
      flushPhrase();
      return;
    }

    if (GLOBAL_KINDS.has(token.kind) && options.detectField) {
      flushPhrase();
      nodes.push({
        type: 'Global',
        value: token.value,
        valueKind: token.kind,
        matchMode: 'global',
      });
      return;
    }

    if (['QuotedString', 'JSON'].includes(token.kind)) {
      flushPhrase();
      nodes.push({
        type: 'Phrase',
        field: ctx.field,
        fieldType: ctx.fieldType,
        value: token.kind === 'QuotedString' ? token.value : token.raw,
        valueKind: token.kind,
        matchMode: 'phrase',
      });
      return;
    }

    phraseBuf.push(token);
  });

  flushPhrase();
  return nodes;
};

const buildTokenNodes = (tokens: LexToken[], ctx: SelectionContext): AstNode[] => {
  const meaningful = tokensWithoutWhitespace(tokens).filter(isValueToken);
  return meaningful.map(token => ({
    type: GLOBAL_KINDS.has(token.kind) ? 'Global' : 'Value',
    field: GLOBAL_KINDS.has(token.kind) ? undefined : ctx.field,
    fieldType: ctx.fieldType,
    value: token.value,
    valueKind: token.kind,
    matchMode: GLOBAL_KINDS.has(token.kind) ? 'global' : 'term',
  }));
};

const buildPhraseNode = (tokens: LexToken[], ctx: SelectionContext): AstNode[] => {
  // 保留空白：join 全部 token（含 Whitespace），避免 "thread": 139 丢空格
  const value = tokens
    .map(t => t.raw)
    .join('')
    .replace(/^\s+|\s+$/g, '');
  if (!value) return [];
  return [{
    type: 'Phrase',
    field: ctx.field,
    fieldType: ctx.fieldType,
    value,
    valueKind: 'Phrase',
    matchMode: 'phrase',
  }];
};

/**
 * Parser：Lexer 不管语义；此处生成 AST。
 * 规则：仅首个 `:` 解析为 field:value。
 */
export const parseTokens = (
  tokens: LexToken[],
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): AstNode => {
  const meaningful = tokensWithoutWhitespace(tokens);
  const colonIdx = options.detectField === false ? -1 : findFirstFieldColonIndex(meaningful);

  // field:value（仅首个冒号；compileFieldValue 场景 detectField=false 跳过）
  if (
    colonIdx > 0
    && meaningful[colonIdx - 1]
    && ['Identifier', 'Keyword'].includes(meaningful[colonIdx - 1].kind)
  ) {
    const fieldToken = meaningful[colonIdx - 1];
    const valueTokens = meaningful.slice(colonIdx + 1);
    const value = joinTokenValues(valueTokens).trim()
      || valueTokens.map(t => t.value).join('');
    return {
      type: 'Root',
      children: [{
        type: 'Field',
        field: fieldToken.value,
        fieldType: ctx.fieldType,
        operator: ':',
        value,
        valueKind: valueTokens[0]?.kind ?? 'Identifier',
        matchMode: 'term',
      }],
    };
  }

  const mode: TokenizerMode = options.tokenizerMode;
  let children: AstNode[] = [];
  if (mode === 'token') {
    children = buildTokenNodes(tokens, ctx);
  } else if (mode === 'phrase' || mode === 'strict') {
    children = buildPhraseNode(tokens, ctx);
  } else {
    children = buildSmartNodes(tokens, ctx, options);
  }

  // 划词默认：若只有普通文本且有当前字段，整段绑定当前字段更符合「最小惊讶」
  // Smart 已按类型拆分；若结果为空则回退整段 Phrase
  if (!children.length) {
    children = buildPhraseNode(tokens, ctx);
  }

  return {
    type: 'Root',
    children: children.length > 1
      ? [{
        type: 'Boolean',
        operator: options.defaultBoolean,
        children,
      }]
      : children,
  };
};
