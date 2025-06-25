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

import { incidentTopN, incidentList, incidentOverview } from 'monitor-api/modules/incident';

import { AlarmService } from './base';

import type {
  AlarmType,
  CommonFilterParams,
  AnalysisTopNDataResponse,
  AnalysisFieldAggItem,
  IncidentTableItem,
  FilterTableResponse,
  QuickFilterItem,
  TableColumnItem,
} from '../typings';
import type { IFilterField } from '@/components/retrieval-filter/typing';
const INCIDENT_TABLE_COLUMNS = [
  {
    colKey: 'id',
    title: window.i18n.t('故障ID'),
    is_default: false,
    align: 'left',
    width: 160,
    fixed: 'left',
  },
  {
    colKey: 'incident_name',
    title: window.i18n.t('故障名称'),
    is_default: true,
    align: 'left',
    width: 180,
    ellipsis: true,
  },
  {
    colKey: 'status',
    title: window.i18n.t('故障状态'),
    is_default: true,
    align: 'left',
    width: 110,
  },
  {
    colKey: 'alert_count',
    title: window.i18n.t('告警数量'),
    is_default: true,
    align: 'left',
    width: 100,
    sorter: true,
  },
  {
    colKey: 'labels',
    title: window.i18n.t('标签'),
    is_default: true,
    align: 'left',
    width: 120,
    ellipsis: true,
  },
  {
    colKey: 'end_time',
    title: window.i18n.t('开始时间 / 结束时间'),
    is_default: true,
    align: 'left',
    width: 174,
  },
  {
    colKey: 'incident_duration',
    title: window.i18n.t('持续时间'),
    is_default: false,
    align: 'left',
    width: 100,
  },
  {
    colKey: 'assignee',
    title: window.i18n.t('负责人'),
    is_default: true,
    align: 'left',
    width: 150,
  },
  {
    colKey: 'incident_reason',
    title: window.i18n.t('故障原因'),
    is_default: true,
    align: 'left',
    width: 240,
    ellipsis: true,
  },
] as const;

export const INCIDENT_FILTER_FIELDS: IFilterField[] = [];

export class IncidentService extends AlarmService<AlarmType.INCIDENT> {
  readonly storageKey = '__INCIDENT_EVENT_COLUMN__';
  get allTableColumns(): TableColumnItem[] {
    return [...INCIDENT_TABLE_COLUMNS];
  }
  get analysisFields(): string[] {
    return ['incident_name', 'incident_type', 'operator', 'duration', 'strategy_name', 'operate_target_string'];
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
    params: Partial<CommonFilterParams>
  ): Promise<FilterTableResponse<T>> {
    const data = await incidentList({
      ...params,
      show_overview: false, // 是否展示概览
      show_aggs: false, // 是否展示聚合
    })
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
  async getQuickFilterList(params: Partial<CommonFilterParams>): Promise<QuickFilterItem[]> {
    const data = await incidentOverview({
      ...params,
      show_overview: true, // 是否展示概览
      show_aggs: true, // 是否展示聚合
    })
      .then(({ aggs, overview }) => {
        const myIncidentList = [];
        const incidentLevelList = [];
        for (const item of overview?.children || []) {
          if (['MY_ASSIGNEE_INCIDENT', 'MY_HANDLER_INCIDENT'].includes(item.id)) {
            myIncidentList.push(item);
            continue;
          }
          incidentLevelList.push(item);
        }
        return [
          {
            id: 'MINE',
            name: window.i18n.t('与我相关'),
            children: myIncidentList,
          },
          {
            id: 'INCIDENT_LEVEL',
            name: window.i18n.t('状态'),
            children: incidentLevelList,
          },
          ...(aggs || []),
        ];
      })
      .catch(() => []);
    console.info('IncidentService getQuickFilterList', data, '==========');
    return data;
  }
}
