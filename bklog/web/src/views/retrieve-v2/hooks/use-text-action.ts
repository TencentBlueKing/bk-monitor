/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { copyMessage, formatDate, getRowFieldValue } from '@/common/util';
import { resolveAddToSearch } from '@/hooks/log-query-compiler';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '@/store/store.type';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { bkMessage } from 'bk-magic-vue';
import { useRoute, useRouter } from 'vue-router/composables';

import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import { getConditionRouterParams } from '../search-result-panel/panel-util';

/** 对象/数组不能 String()，否则会得到 "[object Object]" */
const formatScalarFullPlain = (raw: any): string | undefined => {
  if (raw === null || raw === undefined || raw === '') {
    return undefined;
  }
  if (typeof raw === 'object') {
    if (raw._isBigNumber) {
      return String(raw).replace(/<\/?mark>/gim, '');
    }
    return undefined;
  }
  return String(raw).replace(/<\/?mark>/gim, '');
};

export default (emit?: (_event: string, ..._args: any[]) => void, from?: string) => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

  const getSearchMode = (): 'ui' | 'sql' => {
    const mode = SEARCH_MODE_DIC[store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE]];
    return mode === 'sql' ? 'sql' : 'ui';
  };

  // 处理高亮操作
  const handleHighlight = (value: string, fieldType?: string) => {
    RetrieveHelper.fire(RetrieveEvent.HILIGHT_TRIGGER, {
      event: 'mark',
      value: fieldType === 'date' ? formatDate(Number(value)) : value,
    });
  };

  // 处理复制操作
  const handleCopy = (value: string) => {
    copyMessage(value);
  };

  /**
   * 点击分词「添加到本次检索」：统一走 resolveAddToSearch（UI + 语句）。
   */
  const handleSearchCondition = (
    field: any,
    operator: string,
    value: string,
    isLink: boolean,
    depth?: number,
    isNestedField?: string,
    fullPlain?: string,
    isSoleToken?: boolean,
    tokenMeta?: { tokenIndex?: number; tokenCount?: number },
  ) => {
    const fieldName = typeof field === 'string' ? field : field?.field_name;
    // 始终按字段名从 store 取类型，避免 Object 叶子落到父级 object 类型
    const fieldType = (fieldName
      ? (store.getters.filteredFieldList?.find?.(item => item.field_name === fieldName)?.field_type
        ?? store.getters.visibleFields?.find?.(item => item.field_name === fieldName)?.field_type
        ?? store.state.indexFieldInfo?.fields?.find?.(item => item.field_name === fieldName)?.field_type)
      : undefined)
      ?? (typeof field === 'object' ? field?.field_type : undefined);

    if (value === '--') {
      handleAddCondition(fieldName, operator, [], isLink, depth, isNestedField);
      return;
    }

    const normalizedValue = String(value ?? '').replace(/<\/?mark>/gim, '').trim();
    const normalizedFull = fullPlain && fullPlain !== '--'
      ? String(fullPlain).replace(/<\/?mark>/gim, '').trim()
      : '';
    const soleByValue = Boolean(normalizedFull && normalizedFull === normalizedValue);
    const soleByToken = Boolean(
      isSoleToken
      || (typeof tokenMeta?.tokenCount === 'number' && tokenMeta.tokenCount === 1 && (
        !normalizedFull || soleByValue
      )),
    );

    const payload = resolveAddToSearch({
      field: fieldName || '*',
      value: normalizedValue,
      fieldType,
      fullText: normalizedFull || (soleByToken ? normalizedValue : undefined),
      operatorHint: operator,
      isSoleToken: soleByToken || soleByValue,
      tokenIndex: tokenMeta?.tokenIndex ?? (soleByToken || soleByValue ? 0 : undefined),
      tokenCount: tokenMeta?.tokenCount ?? (soleByToken || soleByValue ? 1 : undefined),
      searchMode: getSearchMode(),
    });

    handleAddCondition(
      payload.field,
      payload.operator,
      payload.value,
      isLink,
      depth,
      isNestedField,
      {
        fullPlain: payload.fullPlain,
        fieldType: payload.fieldType,
        queryString: payload.queryString,
      },
    );
  };

  // 设置路由参数
  const setRouteParams = () => {
    const query = { ...route.query };

    const resolver = new RetrieveUrlResolver({
      keyword: store.getters.retrieveParams.keyword,
      addition: store.getters.retrieveParams.addition,
    });

    Object.assign(query, resolver.resolveParamsToUrl());

    router.replace({
      query,
    });
  };

  // 添加条件（meta.queryString 优先：语句模式由 Compiler 生成）
  const handleAddCondition = (
    field,
    operator,
    value,
    isLink = false,
    depth?,
    isNestedField = 'false',
    meta: { fullPlain?: string; fieldType?: string; queryString?: string } = {},
  ) => {
    return store
      .dispatch('setQueryCondition', {
        field,
        operator,
        value,
        isLink,
        depth,
        isNestedField,
        fullPlain: meta.fullPlain,
        fieldType: meta.fieldType,
        queryString: meta.queryString,
      })
      .then(([newSearchList, searchMode, isNewSearchPage]) => {
        if (isLink) {
          const openUrl = getConditionRouterParams(newSearchList, searchMode, isNewSearchPage);
          window.open(openUrl, '_blank', 'noopener,noreferrer');
          return;
        }

        setRouteParams();
        if (from === 'origin') {
          RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
          RetrieveHelper.fire(RetrieveEvent.SEARCH_VALUE_CHANGE);
        }
      });
  };

  // 处理Trace ID点击
  const handleTraceIdClick = (traceId: string) => {
    const apmRelation = store.state.indexSetFieldConfig.apm_relation;
    if (apmRelation?.is_active) {
      const { app_name: appName, bk_biz_id: bkBizId } = apmRelation.extra;
      const path = `/?bizId=${bkBizId}#/trace/home?app_name=${appName}&search_type=accurate&trace_id=${traceId}`;
      const url = `${window.__IS_MONITOR_COMPONENT__ ? location.origin : window.MONITOR_URL}${path}`;
      window.open(url, '_blank', 'noopener,noreferrer');
    } else {
      bkMessage({
        theme: 'warning',
        message: window.$t('未找到相关的应用，请确认是否有Trace数据的接入。'),
      });
    }
  };

  // 统一的处理函数
  const handleOperation = (
    type: string,
    params: {
      content?: string;
      field?: any;
      row?: any;
      isLink?: boolean;
      depth?: number;
      isNestedField?: string;
      value?: string;
      fieldName?: string;
      operation?: string;
      displayFieldNames?: string[];
    },
  ) => {
    const {
      content,
      field,
      row,
      isLink = false,
      depth,
      isNestedField,
      value,
      fieldName,
      operation,
      displayFieldNames,
      fullPlain: fullPlainFromParams,
      isSoleToken: isSoleTokenFromParams,
      tokenIndex: tokenIndexFromParams,
      tokenCount: tokenCountFromParams,
    } = params as typeof params & {
      fullPlain?: string;
      isSoleToken?: boolean;
      tokenIndex?: number;
      tokenCount?: number;
    };

    // 获取实际值：分词点击带 value；单元格菜单带 content。二者并存时优先 value（分词原文）。
    let actualValue = value ?? content;
    let isParamsChange = false;
    const isDateField = field && ['date', 'date_nanos'].includes(field.field_type);
    if (field && row) {
      if (isDateField) {
        // 时间格式化只影响展示；构造检索条件时必须回取行内原始时间戳
        actualValue = getRowFieldValue(row, field);
      } else if (value !== undefined && value !== null && value !== '') {
        actualValue = value;
      } else if (content !== undefined && content !== null) {
        actualValue = content;
      }
      actualValue = String(actualValue ?? '')
        .replace(/<mark>/g, '')
        .replace(/<\/mark>/g, '');
    }
    // 处理不同类型的操作
    switch (type) {
      case 'highlight':
        handleHighlight(actualValue, field?.field_type);
        break;
      case 'trace-view':
        handleTraceIdClick(actualValue);
        break;
      case 'search':
        isParamsChange = true;
        handleSearchCondition(field, 'eq', actualValue, isLink, depth, isNestedField);
        break;
      case 'copy':
        handleCopy(actualValue);
        break;
      case 'is':
      case 'is not':
      case 'not':
      case 'new-search-page-is':
      case 'contains match phrase':
      case 'not contains match phrase': {
        isParamsChange = true;
        const nextOperator = operation === 'not' ? 'is not' : operation;
        let fullPlain = fullPlainFromParams;
        // date：fullPlain 若已是格式化展示串，强制回取行内原始时间戳（semantic/ui 会优先用 fullText）
        if (isDateField && field && row && typeof field === 'object') {
          fullPlain = formatScalarFullPlain(getRowFieldValue(row, field)) ?? fullPlain;
        } else if (
          (fullPlain === undefined || fullPlain === null || fullPlain === '')
          && fieldName
          && row
        ) {
          // '' 也视为缺失：Object 叶子 fullPlain 解析失败时用行数据回填
          const leafField = typeof field === 'object' && field?.field_name === fieldName
            ? field
            : { field_name: fieldName };
          const raw = getRowFieldValue(row, leafField);
          // 对象/数组禁止 String() → "[object Object]"
          fullPlain = formatScalarFullPlain(raw);
        } else if (
          (fullPlain === undefined || fullPlain === null || fullPlain === '')
          && field
          && row
          && typeof field === 'object'
        ) {
          const raw = getRowFieldValue(row, field);
          fullPlain = formatScalarFullPlain(raw);
        }
        const normalizedActual = String(actualValue ?? '').replace(/<\/?mark>/gim, '').trim();
        const normalizedFull = fullPlain
          ? String(fullPlain).replace(/<\/?mark>/gim, '').trim()
          : '';
        const isSoleToken = Boolean(
          isSoleTokenFromParams
          || (typeof tokenCountFromParams === 'number'
            && tokenCountFromParams === 1
            && (!normalizedFull || normalizedFull === normalizedActual))
          || (normalizedFull && normalizedFull === normalizedActual),
        );
        handleSearchCondition(
          fieldName || field,
          nextOperator,
          actualValue,
          isLink,
          depth,
          isNestedField,
          fullPlain,
          isSoleToken,
          {
            tokenIndex: tokenIndexFromParams ?? (isSoleToken ? 0 : undefined),
            tokenCount: tokenCountFromParams ?? (isSoleToken ? 1 : undefined),
          },
        );
        break;
      }
      case 'display':
        emit?.('fields-updated', displayFieldNames, undefined, false);
        break;
      default:
        break;
    }

    return isParamsChange;
  };

  /**
   * 获取对象中的字段值
   * @param {Object} obj 对象
   * @param {Object} field 字段信息
   * @returns {String} 字段值
   */
  const getObjectValue = (obj: Record<string, any>, field: any) => {
    if (typeof obj === 'object' && obj !== null) {
      if (field.is_virtual_alias_field) {
        const fieldList = [field.field_name, ...field.source_field_names];
        for (const name of fieldList) {
          const val = obj?.[name];
          if (val !== undefined && val !== null && val !== '') {
            return val;
          }
        }
      }

      return obj?.[field.field_name] ?? '--';
    }
    return obj ?? '--';
  };

  return {
    handleOperation,
    handleHighlight,
    handleCopy,
    handleSearchCondition,
    handleAddCondition,
    setRouteParams,
    handleTraceIdClick,
    getObjectValue,
  };
};
