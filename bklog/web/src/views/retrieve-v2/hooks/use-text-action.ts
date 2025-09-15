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

import { copyMessage, formatDate } from '@/common/util';
import useFieldNameHook from '@/hooks/use-field-name';
import useStore from '@/hooks/use-store';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { bkMessage } from 'bk-magic-vue';
import { useRoute, useRouter } from 'vue-router/composables';

import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import { getConditionRouterParams } from '../search-result-panel/panel-util';

export default (emit?: (event: string, ...args: any[]) => void, from?: string) => {
  const store = useStore();
  const router = useRouter();
  const route = useRoute();

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

  // 处理搜索条件操作
  const handleSearchCondition = (
    field: any,
    operator: string,
    value: string,
    isLink: boolean,
    depth?: number,
    isNestedField?: string,
  ) => {
    const { getQueryAlias } = useFieldNameHook({ store });
    const fieldName = field?.field_name ? getQueryAlias(field) : field;
    const searchValue = value === '--' ? [] : [value];
    handleAddCondition(fieldName, operator, searchValue, isLink, depth, isNestedField);
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

  // 添加条件
  const handleAddCondition = (field, operator, value, isLink = false, depth, isNestedField = 'false') => {
    return store
      .dispatch('setQueryCondition', { field, operator, value, isLink, depth, isNestedField })
      .then(([newSearchList, searchMode, isNewSearchPage]) => {
        setRouteParams();
        if (from === 'origin') {
          RetrieveHelper.fire(RetrieveEvent.TREND_GRAPH_SEARCH);
        }
        if (isLink) {
          const openUrl = getConditionRouterParams(newSearchList, searchMode, isNewSearchPage);
          window.open(openUrl, '_blank');
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
      window.open(url, '_blank');
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
    } = params;

    // 获取实际值
    let actualValue = value;
    let isParamsChange = false;
    if (field && row) {
      actualValue = ['date', 'date_nanos'].includes(field.field_type) ? row[field.field_name] : content;
      actualValue = String(actualValue)
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
      case 'new-search-page-is': {
        isParamsChange = true;
        const operator = operation === 'not' ? 'is not' : operation;
        handleSearchCondition(fieldName || field, operator, actualValue, isLink, depth, isNestedField);
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

  return {
    handleOperation,
    handleHighlight,
    handleCopy,
    handleSearchCondition,
    handleAddCondition,
    setRouteParams,
    handleTraceIdClick,
  };
};
