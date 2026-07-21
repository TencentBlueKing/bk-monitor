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
 * 操作符必须落在字段 field_operator 内（与后端 OPERATORS 对齐）：
 * - keyword/flattened：完整值 → `=` / `!=`；部分值 → `contains` / `not contains`
 * - text：完整值 → `is` / `is not`；部分值 → `contains match phrase` / …
 * 不在此做 SQL 字符串拼装。
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
  const full = ctx.fullText && ctx.fullText !== '--' ? String(ctx.fullText) : '';
  const isExactValue = Boolean(full && full === value);

  if (leaf.type === 'Global' || !leaf.field) {
    return {
      field: '*',
      operator: negative ? 'not contains match phrase' : 'contains match phrase',
      value: [value],
    };
  }

  // keyword/flattened：必须用 `=` / `contains`，禁止输出 text 专用的 contains match phrase，
  // 否则标签靠 mapping 显示「包含」，编辑回填却因不在 field_operator 内回退成 `=`。
  if (isKeywordLikeField(fieldType)) {
    return {
      field,
      operator: isExactValue
        ? (negative ? '!=' : '=')
        : (negative ? 'not contains' : 'contains'),
      value: [value],
    };
  }

  if (isTextLikeField(fieldType)) {
    const operator = isExactValue
      ? (negative ? 'is not' : 'is')
      : (negative ? 'not contains match phrase' : 'contains match phrase');
    return { field, operator, value: [value] };
  }

  return {
    field,
    operator: negative ? 'is not' : 'is',
    value: [full || value],
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
