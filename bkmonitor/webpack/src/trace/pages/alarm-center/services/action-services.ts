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

import { actionTopN, searchAction } from 'monitor-api/modules/alert_v2';
import { type IFilterField, EFieldType } from 'trace/components/retrieval-filter/typing';

import {
  type ActionTableItem,
  type AlarmType,
  type AnalysisFieldAggItem,
  type AnalysisTopNDataResponse,
  type CommonFilterParams,
  type FilterTableResponse,
  type QuickFilterItem,
  type TableColumnItem,
  ActionIconMap,
} from '../typings';
import { type RequestOptions, AlarmService } from './base';
const ACTION_TABLE_COLUMNS = [
  {
    colKey: 'id',
    title: 'ID',
    is_default: true,
    is_locked: true,
    fixed: 'left',
    width: 160,
  },
  {
    colKey: 'create_time',
    title: window.i18n.t('开始时间'),
    is_default: true,
    is_locked: false,
    width: 150,
    sorter: true,
  },
  {
    colKey: 'action_name',
    title: window.i18n.t('套餐名称'),
    is_default: true,
    is_locked: true,
    width: 180,
    sorter: true,
    ellipsis: true,
  },
  {
    colKey: 'action_plugin_type_display',
    title: window.i18n.t('套餐类型'),
    is_default: false,
    is_locked: false,
    width: 100,
    sorter: true,
  },
  {
    colKey: 'operate_target_string',
    title: window.i18n.t('执行对象'),
    is_default: false,
    is_locked: false,
    width: 120,
    ellipsis: true,
  },
  {
    colKey: 'operator',
    title: window.i18n.t('负责人'),
    is_default: true,
    is_locked: false,
    width: 220,
  },
  {
    colKey: 'alert_count',
    title: window.i18n.t('触发告警数'),
    is_default: true,
    is_locked: true,
    width: 120,
  },
  {
    colKey: 'converge_count',
    title: window.i18n.t('防御告警数'),
    is_default: true,
    is_locked: true,
    width: 120,
  },
  {
    colKey: 'end_time',
    title: window.i18n.t('结束时间'),
    is_default: false,
    is_locked: false,
    width: 150,
    sorter: true,
  },
  {
    colKey: 'duration',
    title: window.i18n.t('处理时长'),
    is_default: false,
    is_locked: false,
    width: 80,
    sorter: true,
  },
  {
    colKey: 'status',
    title: window.i18n.t('执行状态'),
    is_default: true,
    is_locked: true,
    width: 100,
    sorter: true,
  },
  {
    colKey: 'content',
    title: window.i18n.t('具体内容'),
    is_default: true,
    is_locked: false,
    ellipsis: true,
  },
] as const;

export const ACTION_FILTER_FIELDS: IFilterField[] = [
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
    alias: window.i18n.t('处理记录ID'),
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
    name: 'action_name',
    alias: window.i18n.t('套餐名称'),
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
    name: 'action_config_id',
    alias: window.i18n.t('套餐ID'),
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
    name: 'strategy_name',
    alias: window.i18n.t('策略名称'),
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
    name: 'alerts',
    alias: window.i18n.t('关联告警'),
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
    name: 'status',
    alias: window.i18n.t('状态'),
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
    name: 'bk_biz_name',
    alias: window.i18n.t('业务名'),
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
    name: 'bk_biz_id',
    alias: window.i18n.t('业务ID'),
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
    name: 'operate_target_string',
    alias: window.i18n.t('执行对象'),
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
    name: 'action_plugin_type',
    alias: window.i18n.t('套餐类型'),
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
    name: 'operator',
    alias: window.i18n.t('负责人'),
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
    name: 'create_time',
    alias: window.i18n.t('开始时间'),
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
    name: 'end_time',
    alias: window.i18n.t('结束时间'),
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
export const ACTION_STORAGE_KEY = '__ACTION_EVENT_COLUMN__';
export class ActionService extends AlarmService<AlarmType.ACTION> {
  readonly storageAnalysisKey = '__ACTION_ANALYZE_STORAGE_KEY__';
  readonly storageKey = ACTION_STORAGE_KEY;
  get allTableColumns(): TableColumnItem[] {
    return [...ACTION_TABLE_COLUMNS];
  }
  get analysisDefaultSettingsFields(): string[] {
    return ['action_name', 'action_plugin_type', 'operator', 'duration'];
  }
  get analysisFields(): string[] {
    return ['action_name', 'action_plugin_type', 'operator', 'duration', 'strategy_name', 'operate_target_string'];
  }
  get analysisFieldsMap(): Record<string, string> {
    return {
      action_name: window.i18n.t('套餐名称'),
      strategy_name: window.i18n.t('策略名称'),
      operator: window.i18n.t('负责人'),
      duration: window.i18n.t('处理时长'),
      action_plugin_type: window.i18n.t('套餐类型'),
      operate_target_string: window.i18n.t('执行对象'),
    };
  }

  get filterFields(): IFilterField[] {
    return [...ACTION_FILTER_FIELDS];
  }
  async getAnalysisTopNData(
    params: Partial<CommonFilterParams>,
    isAll = false
  ): Promise<AnalysisTopNDataResponse<AnalysisFieldAggItem>> {
    const data = await actionTopN({
      ...params,
      size: isAll ? 100 : 10,
    }).catch(() => ({
      doc_count: 0,
      fields: [],
    }));
    return data;
  }
  async getFilterTableList<T = ActionTableItem>(
    params: Partial<CommonFilterParams>,
    options?: RequestOptions
  ): Promise<FilterTableResponse<T>> {
    const data = await searchAction(
      {
        ...params,
        show_overview: false, // 是否展示概览
        show_aggs: false, // 是否展示聚合
      },
      options
    )
      .then(({ actions, total }) => {
        return {
          total,
          data: actions || [],
        };
      })
      .catch(() => ({
        total: 0,
        data: [],
      }));
    console.info('ActionService getFilterTableList', data, '==========');
    return data;
  }
  async getQuickFilterList(params: Partial<CommonFilterParams>): Promise<QuickFilterItem[]> {
    const data = await searchAction({
      ...params,
      show_overview: true, // 是否展示概览
      show_aggs: true, // 是否展示聚合
    })
      .then(({ aggs, overview }) => {
        return [
          {
            ...overview,
            name: window.i18n.t('执行状态'),
            children: overview.children.map(item => ({ ...item, ...ActionIconMap[item.id] })),
          },
          ...aggs,
        ];
      })
      .catch(() => []);
    console.info('ActionService getQuickFilterList', data, '==========');
    return data;
  }
  async getRetrievalFilterValues(params: Partial<CommonFilterParams>, config = {}) {
    const data = await actionTopN(
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
