/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '@/store/store.type';

const CONTAINS_OPERATORS = new Set(['contains match phrase', 'not contains match phrase']);

/**
 * 当前是否为语句模式（SQL）。
 */
export const isSqlSearchMode = (storageSearchType?: number | string) => {
  if (storageSearchType === undefined || storageSearchType === null || storageSearchType === '') {
    return false;
  }
  return SEARCH_MODE_DIC[storageSearchType] === 'sql';
};

export const isContainsOperator = (operator?: string) => CONTAINS_OPERATORS.has(String(operator ?? ''));

/**
 * 语句模式「包含」通配：按划选/点击值在完整 VALUE 中的位置补 *
 * - 前缀（Valuexxxx）→ Value*
 * - 后缀（xxxxValue）→ *Value
 * - 中间（xxxValuexxx）→ *Value*
 *
 * Value 本身不做引号包裹，内容是什么就用什么。
 */
export const formatSqlContainsWildcardValue = (selectedValue: string, fullPlainValue?: string) => {
  const selected = String(selectedValue ?? '');
  if (!selected) {
    return selected;
  }
  // 已带通配则不再二次包裹
  if (selected.includes('*')) {
    return selected;
  }

  const plain = String(fullPlainValue ?? '');
  // 无完整 VALUE 上下文（如全文 *）：按中间包含
  if (!plain || plain === '--') {
    return `*${selected}*`;
  }
  // 与完整 VALUE 相等时不应走 contains；若仍调用则不加 *
  if (plain === selected) {
    return selected;
  }

  if (plain.startsWith(selected)) {
    return `${selected}*`;
  }
  if (plain.endsWith(selected)) {
    return `*${selected}`;
  }
  if (plain.includes(selected)) {
    return `*${selected}*`;
  }

  // 完整 VALUE 中未直接命中时，按中间包含处理
  return `*${selected}*`;
};

/**
 * 语句模式 + 包含操作时，把 value 列表格式化为带 * 的检索片段。
 */
export const formatSqlContainsValues = (
  operator: string,
  values: string[],
  fullPlainValue: string | undefined,
  storageSearchType?: number | string,
) => {
  if (!isSqlSearchMode(storageSearchType) || !isContainsOperator(operator)) {
    return values;
  }
  return (values ?? []).map(item => formatSqlContainsWildcardValue(item, fullPlainValue));
};

export { BK_LOG_STORAGE, SEARCH_MODE_DIC };
