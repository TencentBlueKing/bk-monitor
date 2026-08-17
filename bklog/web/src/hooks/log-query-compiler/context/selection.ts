/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { SelectionContext } from '../types';

/** 划词上下文浅校验与默认填充 */
export const normalizeSelectionContext = (ctx: SelectionContext): SelectionContext => {
  const text = String(ctx?.text ?? '');
  return {
    ...ctx,
    text,
    fullText: ctx.fullText === undefined || ctx.fullText === null ? undefined : String(ctx.fullText),
    isSoleToken: Boolean(ctx.isSoleToken),
    tokenIndex: typeof ctx.tokenIndex === 'number' ? ctx.tokenIndex : undefined,
    tokenCount: typeof ctx.tokenCount === 'number' ? ctx.tokenCount : undefined,
    field: ctx.field || ctx.column || '',
    column: ctx.column || ctx.field || '',
    fieldType: ctx.fieldType || 'text',
  };
};
