/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type IFilterField, EFieldType } from 'trace/components/retrieval-filter/typing';

import { type RequestOptions, AlarmService } from './base';

import type {
  AnalysisFieldAggItem,
  AnalysisTopNDataResponse,
  CommonFilterParams,
  FilterTableResponse,
  QuickFilterItem,
  TableColumnItem,
} from '../typings';
import type { AlarmType } from '../typings';

const ISSUES_TABLE_COLUMNS = [
  {
    colKey: 'id',
    title: 'ID',
    is_default: true,
    is_locked: true,
    fixed: 'left',
    width: 160,
  },
] as const;

export const ISSUES_FILTER_FIELDS: IFilterField[] = [
  {
    name: 'query_string',
    alias: window.i18n.t('全字段检索'),
    type: EFieldType.all,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
    ],
  },
  {
    name: 'id',
    alias: 'Issues ID',
    isEnableOptions: true,
    type: EFieldType.keyword,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
    ],
  },
];

export const ISSUES_STORAGE_KEY = '__ISSUES_STORAGE_KEY__';

export class IssuesService extends AlarmService<AlarmType.ISSUES> {
  readonly storageAnalysisKey = '__ISSUES_ANALYZE_STORAGE_KEY__';
  readonly storageKey = ISSUES_STORAGE_KEY;
  get allTableColumns(): TableColumnItem[] {
    return [...ISSUES_TABLE_COLUMNS];
  }
  get analysisDefaultSettingsFields(): string[] {
    return [];
  }
  get analysisFields(): string[] {
    return [];
  }
  get analysisFieldsMap(): Record<string, string> {
    return {};
  }
  get filterFields(): IFilterField[] {
    return [...ISSUES_FILTER_FIELDS];
  }
  async getAnalysisTopNData(
    _params: Partial<CommonFilterParams>,
    _isAll = false,
    _options?: RequestOptions
  ): Promise<AnalysisTopNDataResponse<AnalysisFieldAggItem>> {
    return { doc_count: 0, fields: [] };
  }
  async getFilterTableList<T>(
    _params: Partial<CommonFilterParams>,
    _options?: RequestOptions
  ): Promise<FilterTableResponse<T>> {
    return { total: 0, data: [] };
  }
  async getQuickFilterList(
    _params: Partial<CommonFilterParams>,
    _options?: RequestOptions
  ): Promise<QuickFilterItem[]> {
    return [];
  }
  async getRetrievalFilterValues(_params: Partial<CommonFilterParams>, _config = {}) {
    return { doc_count: 0, fields: [] };
  }
}
