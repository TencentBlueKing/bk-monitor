import { alertTopN } from 'monitor-api/modules/alert_v2';
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

import { IssuesAssigneeMap, IssuesPriorityMap, IssuesRegressionMap, IssuesStatusMap } from '../alarm-issues/constant';
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

/** Issues 表格静态列配置（纯数据，不含渲染逻辑） */
const ISSUES_TABLE_COLUMNS: TableColumnItem[] = [
  {
    colKey: 'name',
    title: 'Issues',
    minWidth: 200,
    fixed: 'left',
    is_default: true,
    is_locked: true,
  },
  {
    colKey: 'labels',
    title: window.i18n.t('标签'),
    minWidth: 180,
    is_default: true,
  },
  {
    colKey: 'last_alert_time',
    title: window.i18n.t('最后出现时间'),
    width: 180,
    sorter: true,
    is_default: true,
  },
  {
    colKey: 'first_alert_time',
    title: window.i18n.t('最早发生时间'),
    width: 180,
    sorter: true,
    is_default: true,
  },
  {
    colKey: 'trend',
    title: window.i18n.t('趋势'),
    width: 160,
    is_default: true,
  },
  {
    colKey: 'impact_scope',
    title: window.i18n.t('影响范围'),
    minWidth: 160,
    is_default: true,
  },
  {
    colKey: 'priority',
    title: window.i18n.t('优先级'),
    width: 86,
    minWidth: 84,
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
    minWidth: 120,
    is_default: true,
  },
  {
    colKey: 'operation',
    title: window.i18n.t('操作'),
    width: 120,
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
    type: EFieldType.text,
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
    type: EFieldType.text,
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
    alias: window.i18n.t('业务 ID'),
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
    name: 'first_alert_time',
    alias: window.i18n.t('首次告警时间'),
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
    name: 'last_alert_time',
    alias: window.i18n.t('最近告警时间'),
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
    name: 'create_time',
    alias: window.i18n.t('创建时间'),
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
    name: 'update_time',
    alias: window.i18n.t('更新时间'),
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
    name: 'resolved_time',
    alias: window.i18n.t('解决时间'),
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
    const aggs = [
      {
        id: 'priority',
        name: '优先级',
        count: 128,
        children: [
          { id: 'P0', name: '高', count: 15 },
          { id: 'P1', name: '中', count: 53 },
          { id: 'P2', name: '低', count: 60 },
        ],
      },
      {
        id: 'status',
        name: '状态',
        count: 128,
        children: [
          { id: 'pending_review', name: '待审核', count: 30 },
          { id: 'unresolved', name: '未解决', count: 12 },
          { id: 'resolved', name: '已解决', count: 80 },
          { id: 'archived', name: '归档', count: 6 },
        ],
      },
      {
        id: 'assignee',
        name: '负责人',
        count: 30,
        children: [
          { id: 'my_assignee', name: '我负责的', count: 20 },
          { id: 'no_assignee', name: '未分配', count: 10 },
        ],
      },
      {
        id: 'is_regression',
        name: '类型',
        count: 128,
        children: [
          { id: 'true', name: '回归问题', count: 8 },
          { id: 'false', name: '新问题', count: 120 },
        ],
      },
    ];

    const res = aggs.map(agg => {
      if (agg.id === 'priority') {
        return {
          ...agg,
          children: agg.children.map(child => {
            const priority = IssuesPriorityMap[child.id];
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
            const status = IssuesStatusMap[child.id];
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
            const assignee = IssuesAssigneeMap[child.id];
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
            const regression = IssuesRegressionMap[child.id];
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
    return res;
  }

  async getRetrievalFilterValues(params: Partial<CommonFilterParams>, config = {}) {
    const data = await alertTopN(
      {
        ...params,
      },
      config
    ).catch(() => ({
      doc_count: 0,
      fields: [],
    }));
    return data;
  }
}
