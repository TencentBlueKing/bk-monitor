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

import { searchAlert, searchAction, listAlertTags, alertTopN, actionTopN } from 'monitor-api/modules/alert';
import { incidentList, incidentOverview, incidentTopN } from 'monitor-api/modules/incident';

import { AlarmType } from '../typings';

import type {
  CommonFilterParams,
  QuickFilterItem,
  AnalysisFieldAggItem,
  AnalysisTopNDataResponse,
  AlertTableItem,
  ActionTableItem,
  FilterTableResponse,
  IncidentTableItem,
} from '../typings';

export abstract class AlarmService<S = AlarmType> {
  constructor(public scenes: S = AlarmType.ALERT as S) {}

  abstract get analysisFields(): string[];

  /**
   * @description: 获取告警分析维度字段列表
   * @param {Partial<CommonFilterParams>} params
   */
  async getAnalysisDimensionFields(params: Partial<CommonFilterParams>): Promise<Omit<QuickFilterItem, 'children'>[]> {
    if (this.scenes !== AlarmType.ALERT) {
      return [];
    }
    const data = await listAlertTags({
      ...params,
    }).catch(() => []);
    return data;
  }
  /**
   * @description: 获取告警分析 topN 数据
   * @param {Partial<CommonFilterParams>} params
   * @param {boolean} isAll 是否获取全部数据
   */
  abstract getAnalysisTopNData(
    params: Partial<CommonFilterParams>
  ): Promise<AnalysisTopNDataResponse<AnalysisFieldAggItem>>;

  /**
   * @description: 获取筛选的 table 数据
   * @param {Partial<CommonFilterParams>} params
   */
  abstract getFilterTableList<
    T = S extends AlarmType.ALERT ? AlertTableItem : S extends AlarmType.INCIDENT ? IncidentTableItem : ActionTableItem,
  >(params: Partial<CommonFilterParams>): Promise<FilterTableResponse<T>>;

  /**
   * @description: 获取快速筛选列表
   * @param {Partial<CommonFilterParams>} params
   */
  abstract getQuickFilterList(params: Partial<CommonFilterParams>): Promise<QuickFilterItem[]>;
}

export class AlertService extends AlarmService<AlarmType.ALERT> {
  get analysisFields(): string[] {
    return [
      'alert_name',
      'metric',
      'duration',
      'ip',
      'bk_cloud_id',
      'strategy_id',
      'strategy_name',
      'assignee',
      'bk_service_instance_id',
      'appointee',
      'labels',
      'plugin_id',
      'ipv6',
    ];
  }

  async getAnalysisTopNData(
    params: Partial<CommonFilterParams>,
    isAll = false
  ): Promise<AnalysisTopNDataResponse<AnalysisFieldAggItem>> {
    const data = await alertTopN({
      ...params,
      size: isAll ? 100 : 10,
    }).catch(() => ({
      doc_count: 0,
      fields: [],
    }));
    return data;
  }
  async getFilterTableList<T = AlertTableItem>(params: Partial<CommonFilterParams>): Promise<FilterTableResponse<T>> {
    const data = await searchAlert({
      ...params,
      show_overview: false, // 是否展示概览
      show_aggs: false, // 是否展示聚合
    }).catch(() => ({
      total: 0,
      data: [],
    }));
    console.info('AlertService getFilterTableList', data, '==========');
    return data;
  }
  async getQuickFilterList(params: Partial<CommonFilterParams>): Promise<QuickFilterItem[]> {
    const data = await searchAlert({
      ...params,
      page_size: 0, // 不返回告警列表数据
      show_overview: true, // 是否展示概览
      show_aggs: true, // 是否展示聚合
    })
      .then(({ aggs, overview }) => {
        const myAlarmList = [];
        const alarmLevelList = [];
        for (const item of overview?.children || []) {
          if (item.id === 'MY_APPOINTEE') {
            myAlarmList.push({
              ...item,
              name: window.i18n.t('分派给我的'),
            });
            continue;
          }
          if (item.id === 'MY_ASSIGNEE') {
            myAlarmList.push({
              ...item,
              name: window.i18n.t('通知给我'),
            });
            continue;
          }
          // 告警状态
          if (['NOT_SHIELDED_ABNORMAL', 'SHIELDED_ABNORMAL', 'RECOVERED'].includes(item.id)) {
            alarmLevelList.push(item);
          }
        }
        return [
          {
            id: 'MINE',
            name: window.i18n.t('与我相关'),
            children: myAlarmList,
          },
          {
            id: 'ALARM_LEVEL',
            name: window.i18n.t('状态'),
            children: alarmLevelList,
          },
          ...aggs,
        ];
      })
      .catch(() => []);
    console.info('AlertService getQuickFilterList', data, '==========');
    return data;
  }
}

export class IncidentService extends AlarmService<AlarmType.INCIDENT> {
  get analysisFields(): string[] {
    return ['incident_name', 'incident_type', 'operator', 'duration', 'strategy_name', 'operate_target_string'];
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

export class ActionService extends AlarmService<AlarmType.ACTION> {
  get analysisFields(): string[] {
    return ['action_name', 'action_plugin_type', 'operator', 'duration', 'strategy_name', 'operate_target_string'];
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
  async getFilterTableList<T = ActionTableItem>(params: Partial<CommonFilterParams>): Promise<FilterTableResponse<T>> {
    const data = await searchAction({
      ...params,
      show_overview: false, // 是否展示概览
      show_aggs: false, // 是否展示聚合
    }).catch(() => ({
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
          },
          ...aggs,
        ];
      })
      .catch(() => []);
    console.info('ActionService getQuickFilterList', data, '==========');
    return data;
  }
}

// export function AlarmServiceFactory(type: AlarmType.ALERT): AlertService;
// export function AlarmServiceFactory(type: AlarmType.INCIDENT): IncidentService;
// export function AlarmServiceFactory(type: AlarmType.ACTION): ActionService;
export function AlarmServiceFactory(type: AlarmType): ActionService | AlertService | IncidentService {
  if (type === AlarmType.ACTION) {
    return new ActionService(AlarmType.ACTION);
  }
  if (type === AlarmType.INCIDENT) {
    return new IncidentService(AlarmType.INCIDENT);
  }
  return new AlertService(AlarmType.ALERT);
}

export type AlarmServiceType<T = AlarmType> = T extends AlarmType.ACTION
  ? ActionService
  : T extends AlarmType.INCIDENT
    ? IncidentService
    : AlertService;
