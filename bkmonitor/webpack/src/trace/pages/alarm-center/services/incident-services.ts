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

import { incidentList, incidentOverview, incidentTopN } from 'monitor-api/modules/incident';

import {
  type AlarmType,
  type AnalysisFieldAggItem,
  type AnalysisTopNDataResponse,
  type CommonFilterParams,
  type FilterTableResponse,
  type IncidentTableItem,
  type QuickFilterItem,
  type TableColumnItem,
  AlarmLevelIconMap,
  IncidentIconMap,
} from '../typings';
import { type RequestOptions, AlarmService } from './base';
import { type IFilterField, EFieldType } from '@/components/retrieval-filter/typing';
const INCIDENT_TABLE_COLUMNS = [
  // {
  //   colKey: 'id',
  //   title: window.i18n.t('故障ID'),
  //   is_default: false,
  //   width: 160,
  //   fixed: 'left',
  // },
  {
    colKey: 'incident_name',
    title: window.i18n.t('故障名称'),
    is_default: true,
    width: 354,
    ellipsis: true,
    fixed: 'left',
  },
  {
    colKey: 'status',
    title: window.i18n.t('故障状态'),
    is_default: true,
    width: 110,
  },
  {
    colKey: 'alert_count',
    title: window.i18n.t('告警数量'),
    is_default: true,
    width: 100,
    sorter: true,
  },
  {
    colKey: 'labels',
    title: window.i18n.t('标签'),
    is_default: true,
    width: 120,
    ellipsis: true,
  },
  {
    colKey: 'end_time',
    title: window.i18n.t('开始时间 / 结束时间'),
    is_default: true,
    width: 174,
  },
  {
    colKey: 'duration',
    title: window.i18n.t('持续时间'),
    is_default: false,
    width: 100,
  },
  {
    colKey: 'assignees',
    title: window.i18n.t('负责人'),
    is_default: true,
    width: 150,
  },
  {
    colKey: 'incident_reason',
    title: window.i18n.t('故障原因'),
    is_default: true,
    width: 240,
    ellipsis: true,
  },
] as const;

export const INCIDENT_FILTER_FIELDS: IFilterField[] = [
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
    alias: window.i18n.t('故障ID'),
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
    name: 'incident_name',
    alias: window.i18n.t('故障名称'),
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
    name: 'incident_reason',
    alias: window.i18n.t('故障原因'),
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
    name: 'status',
    alias: window.i18n.t('故障状态'),
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
    name: 'level',
    alias: window.i18n.t('故障级别'),
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
    name: 'assignees',
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
    name: 'handlers',
    alias: window.i18n.t('处理人'),
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
    name: 'labels',
    alias: window.i18n.t('标签'),
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
    alias: window.i18n.t('故障检出时间'),
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
    name: 'update_time',
    alias: window.i18n.t('故障更新时间'),
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
    name: 'begin_time',
    alias: window.i18n.t('故障开始时间'),
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
    alias: window.i18n.t('故障结束时间'),
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
    name: 'snapshot',
    alias: window.i18n.t('故障图谱快照'),
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

export const INCIDENT_STORAGE_KEY = '__INCIDENT_EVENT_COLUMN__';
export class IncidentService extends AlarmService<AlarmType.INCIDENT> {
  readonly storageAnalysisKey = '__INCIDENT_ANALYZE_STORAGE_KEY__';
  readonly storageKey = INCIDENT_STORAGE_KEY;
  get allTableColumns(): TableColumnItem[] {
    return [...INCIDENT_TABLE_COLUMNS];
  }
  get analysisDefaultSettingsFields(): string[] {
    return ['incident_name', 'incident_type', 'operator', 'duration'];
  }
  get analysisFields(): string[] {
    return ['incident_name', 'incident_type', 'operator', 'duration', 'strategy_name', 'operate_target_string'];
  }
  get analysisFieldsMap(): Record<string, string> {
    return {
      incident_name: window.i18n.t('故障名称'),
      incident_type: window.i18n.t('故障类型'),
      operator: window.i18n.t('负责人'),
      duration: window.i18n.t('处理时长'),
      strategy_name: window.i18n.t('策略名称'),
      operate_target_string: window.i18n.t('执行对象'),
    };
  }
  get filterFields(): IFilterField[] {
    return [...INCIDENT_FILTER_FIELDS];
  }
  async getAnalysisTopNData(
    params: Partial<CommonFilterParams>,
    isAll = false
  ): Promise<AnalysisTopNDataResponse<AnalysisFieldAggItem>> {
    const data = await incidentTopN({
      ...params,
      size: isAll ? 100 : 10,
    }).catch(() => ({
      doc_count: 0,
      fields: [],
    }));
    return data;
  }
  async getFilterTableList<T = IncidentTableItem>(
    params: Partial<CommonFilterParams>,
    options?: RequestOptions
  ): Promise<FilterTableResponse<T>> {
    const data = await incidentList(
      {
        ...params,
        show_overview: false, // 是否展示概览
        show_aggs: false, // 是否展示聚合
      },
      options
    )
      .then(({ total, incidents }) => ({
        total,
        data: incidents,
      }))
      .catch(() => ({
        total: 0,
        data: [],
      }));
    console.info('IncidentService getFilterTableList', data, '==========');
    return data;
  }

  async getIncidentLevelList(params: Partial<CommonFilterParams>) {
    const data = await incidentList({
      ...params,
      show_overview: false, // 是否展示概览
      show_aggs: true, // 是否展示聚合
    })
      .then(({ aggs }) => {
        return aggs.map(item => {
          if (item.id === 'level') {
            return {
              ...item,
              children: item.children.map(child => ({
                ...child,
                ...AlarmLevelIconMap[child.id],
              })),
            };
          }
          return item;
        });
      })
      .catch(() => []);
    return data;
  }

  async getQuickFilterList(params: Partial<CommonFilterParams>): Promise<QuickFilterItem[]> {
    const level = await this.getIncidentLevelList(params);
    const data = await incidentOverview({
      ...params,
      show_overview: true, // 是否展示概览
      show_aggs: true, // 是否展示聚合
    })
      .then(({ overview }) => {
        const myIncidentList = [];
        const incidentLevelList = [];
        for (const item of overview?.children || []) {
          if (['MY_ASSIGNEE_INCIDENT', 'MY_HANDLER_INCIDENT'].includes(item.id)) {
            myIncidentList.push({
              ...item,
              ...IncidentIconMap[item.id],
            });
            continue;
          }
          if (IncidentIconMap[item.id]) {
            incidentLevelList.push({ ...item, ...IncidentIconMap[item.id] });
          }
        }
        return [
          {
            id: 'MINE',
            name: window.i18n.t('与我相关'),
            children: myIncidentList,
          },
          ...level,
          {
            id: 'INCIDENT_LEVEL',
            name: window.i18n.t('状态'),
            children: incidentLevelList,
          },
        ];
      })
      .catch(() => []);

    return data;
  }

  async getRetrievalFilterValues(params: Partial<CommonFilterParams>, config = {}) {
    const data = await incidentTopN(
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
