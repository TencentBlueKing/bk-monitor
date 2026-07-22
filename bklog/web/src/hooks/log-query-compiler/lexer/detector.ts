/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import type { LexToken } from '../types';

/** 仅首个冒号作为 field:value 分隔 */
export const findFirstFieldColonIndex = (tokens: LexToken[]): number => {
  for (let i = 0; i < tokens.length; i++) {
    if (tokens[i].kind === 'Operator' && tokens[i].value === ':') {
      return i;
    }
  }
  return -1;
};

export const isValueToken = (token: LexToken) =>
  !['Whitespace', 'Operator', 'Keyword'].includes(token.kind)
  || (token.kind === 'Keyword' && !['AND', 'OR', 'NOT', 'and', 'or', 'not'].includes(token.value));
