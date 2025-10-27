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
export const ROW_INDEX = '__component_row_index';
export const ROW_CONFIG = '__component_row_config';
export const ROW_KEY = '__component_row_key';
export const ROW_EXPAND = '__component_row_expand';
export const ROW_F_ORIGIN_TIME = '__component_origin_time';
export const ROW_F_ORIGIN_CTX = '__component_origin_content';
export const ROW_F_ORIGIN_OPT = '__component_table_operator';
export const ROW_F_JSON = '__component_format_json';
export const ROW_IS_IN_SECTION = '__component_is_in_section';
export const ROW_SOURCE = '__component_row_source';
// 搜索框查询条件
export const SECTION_SEARCH_INPUT = '.search-bar-wrapper';

// 搜索结果内容容器选择器
export const SEARCH_RESULT_CONTENT = '.bklog-result-container';

export const LOG_SOURCE_F = () => {
  return {
    description: null,
    es_doc_values: false,
    field_alias: '',
    field_name: (window as any).$t('日志来源'),
    field_operator: [],
    field_type: 'keyword',
    filterExpand: false,
    filterVisible: false,
    is_analyzed: false,
    is_display: false,
    is_editable: false,
    minWidth: 0,
    tag: 'union-source',
    width: 230,
  };
};

export type RowProxyData = Record<string, { visible?: boolean; height?: number; rowIndex?: number; mounted?: boolean }>;
