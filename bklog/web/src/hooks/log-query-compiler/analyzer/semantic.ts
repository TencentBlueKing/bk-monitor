/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import { isDateLikeField, isKeywordLikeField, isNumberLikeField, isTextLikeField } from '../context/field';
import type { AstNode, QueryCompilerOptions, SelectionContext } from '../types';

const mapNode = (node: AstNode, visitor: (n: AstNode) => AstNode): AstNode => {
  const next = visitor({ ...node });
  if (next.children?.length) {
    next.children = next.children.map(child => mapNode(child, visitor));
  }
  return next;
};

/**
 * Semantic Analyzer：结合 fieldType / operatorHint 决定 matchMode。
 * 与本项目既有划词规则对齐：
 * - text → phrase / match_phrase（语句模式引号短语）
 * - keyword/flattened → wildcard（语句模式位置通配）
 * - 其他 → term（完整值等值）
 * - IP/UUID/... → global
 */
export const analyzeSemantics = (
  ast: AstNode,
  ctx: SelectionContext,
  options: QueryCompilerOptions,
): AstNode => {
  const negative = Boolean(options.negative)
    || ['is not', 'not contains match phrase', 'not contains', '!='].includes(String(ctx.operatorHint ?? ''));

  return mapNode(ast, (node) => {
    const next: AstNode = { ...node, negative: node.negative ?? negative };

    if (next.type === 'Global') {
      next.matchMode = 'global';
      return next;
    }

    if (next.type === 'Field') {
      // 显式 field:value —— value 内可能仍含冒号（sha256:xxx）
      next.matchMode = isKeywordLikeField(next.fieldType) ? 'wildcard' : 'term';
      return next;
    }

    if (next.type === 'Phrase' || next.type === 'Value' || next.type === 'Comparison') {
      const fieldType = next.fieldType || ctx.fieldType;
      next.field = next.field || ctx.field;

      if (isTextLikeField(fieldType)) {
        next.matchMode = 'phrase';
      } else if (isKeywordLikeField(fieldType)) {
        next.matchMode = options.wildcardForKeyword === false ? 'term' : 'wildcard';
      } else if (isNumberLikeField(fieldType) || isDateLikeField(fieldType) || fieldType === 'boolean' || fieldType === 'ip') {
        // 其他类型：补齐为完整 FieldValue（由 resolver 写入）
        next.matchMode = 'term';
        if (ctx.fullText && ctx.fullText !== '--' && ctx.fullText !== '[object Object]') {
          next.value = ctx.fullText;
        }
      } else {
        next.matchMode = 'phrase';
      }
      return next;
    }

    return next;
  });
};
