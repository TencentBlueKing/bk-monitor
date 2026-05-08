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
import { issueSearch, issueTopN } from 'monitor-api/modules/issue';
import { type IFilterField, EFieldType } from 'trace/components/retrieval-filter/typing';

import {
  ISSUES_ASSIGNEE_MAP,
  ISSUES_PRIORITY_MAP,
  ISSUES_REGRESSION_MAP,
  ISSUES_STATUS_MAP,
} from '../alarm-issues/constant';
import { type RequestOptions, AlarmService } from './base';

import type { IssueItem, IssueSearchParams, IssueSearchResponse } from '../alarm-issues/typing';
import type {
  AnalysisFieldAggItem,
  AnalysisTopNDataResponse,
  CommonFilterParams,
  FilterTableResponse,
  QuickFilterItem,
  TableColumnItem,
} from '../typings';
import type { AlarmType } from '../typings';

/** Issues 表格静态列配置（纯数据，不含渲染逻辑） */
const ISSUES_TABLE_COLUMNS: TableColumnItem[] = [
  {
    colKey: 'name',
    title: 'Issues',
    width: 200,
    fixed: 'left',
    is_default: true,
    is_locked: true,
  },
  {
    colKey: 'labels',
    title: window.i18n.t('标签'),
    width: 160,
    is_default: true,
  },
  {
    colKey: 'last_alert_time',
    title: window.i18n.t('最后出现时间'),
    width: 220,
    sorter: true,
    is_default: true,
  },
  {
    colKey: 'first_alert_time',
    title: window.i18n.t('最早发生时间'),
    width: 220,
    sorter: true,
    is_default: true,
  },
  {
    colKey: 'trend',
    title: window.i18n.t('趋势'),
    width: 200,
    is_default: true,
  },
  {
    colKey: 'impact_scope',
    title: window.i18n.t('影响范围'),
    width: 150,
    is_default: true,
  },
  {
    colKey: 'priority',
    title: window.i18n.t('优先级'),
    width: 86,
    is_default: true,
  },
  {
    colKey: 'status',
    title: window.i18n.t('状态'),
    width: 120,
    is_default: true,
  },
  {
    colKey: 'assignee',
    title: window.i18n.t('负责人'),
    width: 160,
    is_default: true,
  },
  {
    colKey: 'operation',
    title: window.i18n.t('操作'),
    width: 150,
    fixed: 'right',
    is_default: true,
    is_locked: true,
  },
];

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
  {
    name: 'name',
    alias: window.i18n.t('Issue 名称'),
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: window.i18n.t('包含'),
        value: 'include',
      },
      {
        alias: window.i18n.t('不包含'),
        value: 'exclude',
      },
    ],
  },
  {
    name: 'status',
    alias: window.i18n.t('状态'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'priority',
    alias: window.i18n.t('优先级'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'assignee',
    alias: window.i18n.t('负责人'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'strategy_id',
    alias: window.i18n.t('策略 ID'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'strategy_name',
    alias: window.i18n.t('策略名称'),
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: window.i18n.t('包含'),
        value: 'include',
      },
      {
        alias: window.i18n.t('不包含'),
        value: 'exclude',
      },
    ],
  },
  {
    name: 'bk_biz_id',
    alias: window.i18n.t('业务ID'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'labels',
    alias: window.i18n.t('标签'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'is_regression',
    alias: window.i18n.t('是否回归'),
    type: EFieldType.boolean,
    isEnableOptions: true,
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
    name: 'alert_count',
    alias: window.i18n.t('告警数量'),
    type: EFieldType.integer,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: '>',
        value: 'gt',
      },
      {
        alias: '>=',
        value: 'gte',
      },
      {
        alias: '<',
        value: 'lt',
      },
      {
        alias: '<=',
        value: 'lte',
      },
    ],
  },
  {
    name: 'impact_dimensions',
    alias: window.i18n.t('影响范围维度'),
    type: EFieldType.keyword,
    isEnableOptions: true,
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
    name: 'first_alert_time',
    alias: window.i18n.t('首次告警时间'),
    type: EFieldType.date,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: '>',
        value: 'gt',
      },
      {
        alias: '>=',
        value: 'gte',
      },
      {
        alias: '<',
        value: 'lt',
      },
      {
        alias: '<=',
        value: 'lte',
      },
    ],
  },
  {
    name: 'last_alert_time',
    alias: window.i18n.t('最近告警时间'),
    type: EFieldType.date,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: '>',
        value: 'gt',
      },
      {
        alias: '>=',
        value: 'gte',
      },
      {
        alias: '<',
        value: 'lt',
      },
      {
        alias: '<=',
        value: 'lte',
      },
    ],
  },
  {
    name: 'create_time',
    alias: window.i18n.t('创建时间'),
    type: EFieldType.date,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: '>',
        value: 'gt',
      },
      {
        alias: '>=',
        value: 'gte',
      },
      {
        alias: '<',
        value: 'lt',
      },
      {
        alias: '<=',
        value: 'lte',
      },
    ],
  },
  {
    name: 'update_time',
    alias: window.i18n.t('更新时间'),
    type: EFieldType.date,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: '>',
        value: 'gt',
      },
      {
        alias: '>=',
        value: 'gte',
      },
      {
        alias: '<',
        value: 'lt',
      },
      {
        alias: '<=',
        value: 'lte',
      },
    ],
  },
  {
    name: 'resolved_time',
    alias: window.i18n.t('解决时间'),
    type: EFieldType.date,
    methods: [
      {
        alias: '=',
        value: 'eq',
      },
      {
        alias: '!=',
        value: 'neq',
      },
      {
        alias: '>',
        value: 'gt',
      },
      {
        alias: '>=',
        value: 'gte',
      },
      {
        alias: '<',
        value: 'lt',
      },
      {
        alias: '<=',
        value: 'lte',
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
  async getFilterTableList<T = IssueItem>(
    params: Partial<CommonFilterParams>,
    options?: RequestOptions
  ): Promise<FilterTableResponse<T>> {
    // 计算告警趋势图时间范围：trend_end_time 跟随 end_time，trend_start_time 为往前 24 小时
    const trendEndTime = params.end_time;
    const trendStartTime = trendEndTime ? trendEndTime - 24 * 60 * 60 : undefined;

    const data = await issueSearch<Partial<IssueSearchParams>, IssueSearchResponse>(
      {
        ...params,
        show_aggs: false,
        show_dsl: false,
        trend_end_time: trendEndTime,
        trend_start_time: trendStartTime,
      },
      options
    )
      .then(({ issues, total }) => {
        return {
          total,
          data: issues || ([] as IssueItem[]),
        };
      })
      .catch(() => ({
        total: 0,
        data: [] as IssueItem[],
      }));
    return data as FilterTableResponse<T>;
  }
  async getQuickFilterList(params: Partial<CommonFilterParams>, options?: RequestOptions): Promise<QuickFilterItem[]> {
    const data = await issueSearch<Partial<IssueSearchParams>, IssueSearchResponse>(
      {
        ...params,
        page_size: 0, // 不返回告警列表数据
        show_aggs: true, // 是否展示聚合
      },
      options
    )
      .then(({ aggs }) => {
        return aggs.map(agg => {
          if (agg.id === 'priority') {
            return {
              ...agg,
              children: agg.children.map(child => {
                const priority = ISSUES_PRIORITY_MAP[child.id];
                return {
                  ...child,
                  name: priority.alias || child.name,
                  textColor: priority?.color,
                  extCls: `priority priority-${child.id}`,
                };
              }),
            };
          }
          if (agg.id === 'status') {
            return {
              ...agg,
              children: agg.children.map(child => {
                const status = ISSUES_STATUS_MAP[child.id];
                return {
                  ...child,
                  name: status.alias || child.name,
                  icon: status?.icon,
                  iconColor: status?.color,
                  textColor: status?.color,
                };
              }),
            };
          }
          if (agg.id === 'assignee') {
            return {
              ...agg,
              children: agg.children.map(child => {
                const assignee = ISSUES_ASSIGNEE_MAP[child.id];
                return {
                  ...child,
                  name: assignee.alias || child.name,
                  icon: assignee?.icon,
                  iconColor: assignee?.color,
                };
              }),
            };
          }
          if (agg.id === 'is_regression') {
            return {
              ...agg,
              children: agg.children.map(child => {
                const regression = ISSUES_REGRESSION_MAP[child.id];
                return {
                  ...child,
                  name: regression.alias || child.name,
                  icon: regression?.icon,
                  iconColor: regression?.color,
                  extCls: `regression regression-${child.id}`,
                };
              }),
            };
          }
          return agg;
        });
      })
      .catch(() => []);
    return data;
  }

  async getRetrievalFilterValues(params: Partial<CommonFilterParams>, config = {}) {
    const data = await issueTopN(
      {
        ...params,
        need_time_partition: true,
      },
      config
    ).catch(() => ({
      doc_count: 0,
      fields: [],
    }));
    return data;
  }
}
