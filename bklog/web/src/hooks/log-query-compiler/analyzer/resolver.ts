/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { AstNode, SelectionContext } from '../types';

/**
 * Field Resolver：
 * - IP / UUID / URL / MAC / Hash → Global（不绑当前字段）
 * - Text / Phrase → Current Field
 */
export const resolveFields = (ast: AstNode, ctx: SelectionContext): AstNode => {
  const walk = (node: AstNode): AstNode => {
    const next: AstNode = { ...node };
    if (next.children) {
      next.children = next.children.map(walk);
    }

    if (next.type === 'Global') {
      next.field = undefined;
      return next;
    }

    if (['Phrase', 'Value', 'Comparison', 'Wildcard'].includes(next.type)) {
      next.field = next.field || ctx.field;
      next.fieldType = next.fieldType || ctx.fieldType;
    }

    return next;
  };

  return walk(ast);
};
