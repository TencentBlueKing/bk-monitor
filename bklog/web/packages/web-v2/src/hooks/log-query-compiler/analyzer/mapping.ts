/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { AstNode, SelectionContext } from '../types';

/** 将项目 operatorHint 映射到 AST 否定 / match 语义 */
export const mapOperatorHint = (ast: AstNode, ctx: SelectionContext): AstNode => {
  const hint = String(ctx.operatorHint ?? '');
  const negative = ['is not', 'not contains match phrase', 'not contains', '!=', 'not'].includes(hint);

  const walk = (node: AstNode): AstNode => {
    const next: AstNode = { ...node, negative: node.negative || negative };
    if (next.children) {
      next.children = next.children.map(walk);
    }
    return next;
  };

  return walk(ast);
};
