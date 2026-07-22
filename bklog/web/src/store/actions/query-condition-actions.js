/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import DOMPurify from 'dompurify';

import {
  compileFieldValueToQueryString,
  escapeQueryStringPhraseLiteral,
} from '@/hooks/log-query-compiler';
import { storeCacheService } from '@/storage';


import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '../store.type.ts';

export function setQueryConditionAction({ state, dispatch }, payload) {
  const newQueryList = Array.isArray(payload) ? payload : [payload];
  const isLink = newQueryList[0]?.isLink;
  let searchMode = SEARCH_MODE_DIC[state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui';

  if (state.aiMode.active) {
    searchMode = 'sql';
  }

  const depth = Number(payload.depth ?? '0');
  const isNestedField = payload?.isNestedField ?? 'false';
  const isNewSearchPage = newQueryList[0].operator === 'new-search-page-is';
  const from = newQueryList[0].from ?? 'origin';

  const getTargetField = field => state.visibleFields?.find(item => item.field_name === field)
    ?? state.indexFieldInfo?.fields?.find?.(item => item.field_name === field);
  const getFieldType = (field, fallbackType) => getTargetField(field)?.field_type ?? fallbackType ?? '';

  const getAdditionMappingOperator = ({ operator, field, value }) => {
    let mappingKey = {
      is: '=',
      'is not': '!=',
    };

    const textMappingKey = {
      is: 'contains match phrase',
      'is not': 'not contains match phrase',
    };

    const keywordMappingKey = {
      is: 'contains',
      'is not': 'not contains',
    };

    const boolMapping = {
      is: `is ${value[0]}`,
      'is not': `is ${/true/i.test(value[0]) ? 'false' : 'true'}`,
    };

    const targetField = getTargetField(field);
    const textType = targetField?.field_type ?? '';
    const isVirtualObjNode = targetField?.is_virtual_obj_node ?? false;

    if (isVirtualObjNode && textType === 'object') {
      mappingKey = textMappingKey;
    }

    if (textType === 'text') {
      mappingKey = textMappingKey;
    }

    if (textType === 'boolean') {
      mappingKey = boolMapping;
      if (value.length) {
        value.splice(0, value.length);
      }
    }

    if ((depth > 1 || isNestedField === 'true') && textType === 'keyword') {
      mappingKey = keywordMappingKey;
    }
    return mappingKey[operator] ?? operator;
  };

  /**
   * 语句模式兜底：上游未带 queryString 时，统一走 Compiler。
   */
  const buildSqlQueryFragment = ({ field, operator, value, fieldType, fullPlain }) => {
    const raw = Array.isArray(value) ? value[0] : value;
    const textType = getFieldType(field, fieldType);
    const safeValue = typeof raw === 'string' ? DOMPurify.sanitize(raw) : raw;

    if (field === '*' || !field) {
      // 与 resolveAddToSearch / Builder 同一套短语转义，避免旁路二次实现
      const inner = escapeQueryStringPhraseLiteral(String(safeValue ?? ''));
      const neg = ['is not', 'not contains match phrase', 'not contains', '!='].includes(operator);
      return neg ? `NOT "${inner}"` : `"${inner}"`;
    }

    return compileFieldValueToQueryString({
      field,
      value: String(safeValue ?? ''),
      fieldType: textType,
      fullText: fullPlain,
      operatorHint: operator,
    });
  };

  const searchValueIsExist = (newSearchValue, targetSearchMode) => {
    let isExist;
    if (targetSearchMode === 'ui') {
      isExist = state.indexItem.addition.some((addition) => {
        return (
          addition.field === newSearchValue.field
          && addition.operator === newSearchValue.operator
          && addition.value.toString() === newSearchValue.value.toString()
        );
      });
    }
    if (targetSearchMode === 'sql') {
      const keyword = state.indexItem.keyword.replace(/^\s*\*\s*$/, '');
      isExist = keyword.indexOf(newSearchValue) !== -1;
    }
    return isExist;
  };

  const filterQueryList = newQueryList
    .map((item) => {
      const isNewSearchPageItem = item.operator === 'new-search-page-is';
      item.operator = isNewSearchPageItem ? 'is' : item.operator;
      const { field, operator, value } = item;
      const targetField = getTargetField(field);

      let newSearchValue = null;
      if (searchMode === 'ui') {
        const mapOperator = getAdditionMappingOperator({ field, operator, value });
        newSearchValue = Object.assign({ field, value }, { operator: mapOperator });
      }
      if (searchMode === 'sql') {
        if (item.queryString) {
          newSearchValue = item.queryString;
        } else if (targetField?.is_virtual_obj_node) {
          const inner = String(value?.[0] ?? '').replace(/"/g, '\\"');
          newSearchValue = `"${inner}"`;
        } else {
          newSearchValue = buildSqlQueryFragment({
            field,
            operator,
            value,
            fieldType: item.fieldType,
            fullPlain: item.fullPlain,
          });
        }
      }
      const isExist = searchValueIsExist(newSearchValue, searchMode);
      return !isExist || isNewSearchPageItem ? newSearchValue : null;
    })
    .filter(Boolean);

  if (state.aiMode.active) {
    const newSearchKeywords = filterQueryList.filter(item => !state.aiMode.filterList.includes(item));
    if (newSearchKeywords.length) {
      state.aiMode.filterList.push(...newSearchKeywords);
    }

    if (from === 'origin') {
      dispatch('requestIndexSetQuery');
    }

    return Promise.resolve([filterQueryList, searchMode, isNewSearchPage]);
  }

  if (!filterQueryList.length) return Promise.resolve([filterQueryList, searchMode, isNewSearchPage]);

  if (!isLink) {
    if (searchMode === 'ui') {
      const startIndex = state.indexItem.addition.length;
      state.indexItem.addition.splice(startIndex, 0, ...filterQueryList);
      if (from === 'origin') {
        dispatch('requestIndexSetQuery');
      }
    }

    if (searchMode === 'sql') {
      const keyword = state.indexItem.keyword.replace(/^\s*\*\s*$/, '');
      const keywords = keyword.length > 0 ? [keyword] : [];
      const newSearchKeywords = filterQueryList.filter(item => keyword.indexOf(item) === -1);
      if (newSearchKeywords.length) {
        const lastIndex = newSearchKeywords.length - 1;
        newSearchKeywords[lastIndex] = newSearchKeywords[lastIndex].replace(/\s*$/, ' ');
      }

      if (keywords.length > 0 && !/\s$/.test(keywords[0])) {
        keywords[0] = `${keywords[0]} `;
      }

      state.indexItem.keyword = (keywords ?? []).concat(newSearchKeywords).join('AND ');

      if (from === 'origin') {
        dispatch('requestIndexSetQuery');
      }
    }
  }

  storeCacheService.setApiCache('store/query-condition-result', state.indexId || 'default', {
    filterQueryList,
    searchMode,
    isNewSearchPage,
    addition: state.indexItem.addition,
    keyword: state.indexItem.keyword,
  }).catch(() => {});

  return Promise.resolve([filterQueryList, searchMode, isNewSearchPage]);
}
