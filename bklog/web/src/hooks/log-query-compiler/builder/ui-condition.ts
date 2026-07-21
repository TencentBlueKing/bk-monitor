/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import { isKeywordLikeField, isTextLikeField } from '../context/field';
import type { AstNode, SelectionContext } from '../types';

/**
 * UI Condition Builder：输出 addition 可用的 field/operator/value。
 * 与 setQueryCondition 对齐，不在此做 SQL 字符串拼装。
 */
export const buildUiCondition = (
  ast: AstNode,
  ctx: SelectionContext,
): { field: string; operator: string; value: string[] } | undefined => {
  const leaf = findFirstValueNode(ast);
  if (!leaf) return undefined;

  const field = leaf.field || ctx.field || '*';
  const value = String(leaf.value ?? '');
  if (!value) return undefined;

  const fieldType = leaf.fieldType || ctx.fieldType;
  const negative = Boolean(leaf.negative);

  if (leaf.type === 'Global' || !leaf.field) {
    return {
      field: '*',
      operator: negative ? 'not contains match phrase' : 'contains match phrase',
      value: [value],
    };
  }

  if (isKeywordLikeField(fieldType)) {
    return {
      field,
      operator: negative ? 'not contains match phrase' : 'contains match phrase',
      value: [value],
    };
  }

  if (isTextLikeField(fieldType)) {
    const full = ctx.fullText;
    const operator = full && full === value
      ? (negative ? 'is not' : 'is')
      : (negative ? 'not contains match phrase' : 'contains match phrase');
    return { field, operator, value: [value] };
  }

  return {
    field,
    operator: negative ? 'is not' : 'is',
    value: [ctx.fullText && ctx.fullText !== '--' ? ctx.fullText : value],
  };
};

const findFirstValueNode = (node: AstNode): AstNode | null => {
  if (['Phrase', 'Value', 'Field', 'Global', 'Comparison', 'Wildcard'].includes(node.type) && node.value) {
    return node;
  }
  for (const child of node.children ?? []) {
    const hit = findFirstValueNode(child);
    if (hit) return hit;
  }
  return null;
};
