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

import { alertTopN, searchAlert } from 'monitor-api/modules/alert';

import { AlarmService } from './base';

import type {
  CommonFilterParams,
  AnalysisTopNDataResponse,
  AnalysisFieldAggItem,
  AlertTableItem,
  FilterTableResponse,
  QuickFilterItem,
  TableColumnItem,
} from '../typings';

export class AlertService extends AlarmService {
  readonly storageKey = '__ALERT_EVENT_COLUMN__';
  get allTableColumns(): TableColumnItem[] {
    return [
      {
        colKey: 'id',
        title: window.i18n.t('告警ID'),
        is_default: true,
        align: 'left',
        width: 140,
        fixed: 'left',
        sorter: true,
      },
      {
        colKey: 'bk_biz_name',
        title: window.i18n.t('空间名'),
        is_default: true,
        align: 'left',
        width: 100,
        fixed: 'left',
        sorter: true,
      },
      {
        colKey: 'alert_name',
        title: window.i18n.t('告警名称'),
        is_default: true,
        align: 'left',
        width: 160,
        fixed: 'left',
        sorter: true,
      },
      {
        colKey: 'plugin_display_name',
        title: window.i18n.t('告警来源'),
        is_default: false,
        align: 'left',
        width: 110,
      },
      {
        colKey: 'category_display',
        title: window.i18n.t('分类'),
        is_default: true,
        align: 'left',
        width: 160,
      },
      {
        colKey: 'metric',
        title: window.i18n.t('告警指标'),
        is_default: true,
        align: 'left',
        width: 180,
        sorter: true,
      },
      {
        colKey: 'event_count',
        title: window.i18n.t('关联事件'),
        is_default: true,
        align: 'left',
        width: 140,
      },
      {
        colKey: 'create_time',
        title: window.i18n.t('创建时间'),
        is_default: false,
        align: 'left',
        width: 150,
        sorter: true,
      },
      {
        colKey: 'begin_time',
        title: window.i18n.t('开始时间'),
        is_default: false,
        align: 'left',
        width: 150,
        sorter: true,
      },
      {
        colKey: 'end_time',
        title: window.i18n.t('结束时间'),
        is_default: false,
        align: 'left',
        width: 150,
        sorter: true,
      },
      {
        colKey: 'latest_time',
        title: window.i18n.t('最新事件时间'),
        is_default: false,
        align: 'left',
        width: 150,
        sorter: true,
      },
      {
        colKey: 'first_anomaly_time',
        title: window.i18n.t('首次异常时间'),
        is_default: false,
        align: 'left',
        width: 150,
        sorter: true,
      },
      {
        colKey: 'duration',
        title: window.i18n.t('持续时间'),
        is_default: false,
        align: 'left',
        sorter: true,
      },
      {
        colKey: 'description',
        title: window.i18n.t('告警内容'),
        is_default: true,
        align: 'left',
        width: 300,
      },
      {
        colKey: 'tags',
        title: window.i18n.t('维度'),
        is_default: false,
        align: 'left',
        width: 200,
      },
      {
        colKey: 'extend_info',
        title: window.i18n.t('关联信息'),
        is_default: false,
        align: 'left',
        width: 250,
      },
      {
        colKey: 'appointee',
        title: window.i18n.t('负责人'),
        is_default: true,
        align: 'left',
        width: 200,
      },
      {
        colKey: 'assignee',
        title: window.i18n.t('通知人'),
        is_default: true,
        align: 'left',
        width: 200,
      },
      {
        colKey: 'follower',
        title: window.i18n.t('关注人'),
        is_default: true,
        align: 'left',
        width: 200,
      },
      {
        colKey: 'strategy_name',
        title: window.i18n.t('策略名称'),
        is_default: false,
        align: 'left',
      },
      {
        colKey: 'labels',
        title: window.i18n.t('策略标签'),
        is_default: false,
        align: 'left',
        width: 200,
      },
      {
        colKey: 'stage_display',
        title: window.i18n.t('处理阶段'),
        is_default: true,
        align: 'left',
        fixed: 'right',
        width: 110,
      },
      {
        colKey: 'status',
        title: window.i18n.t('状态'),
        is_default: true,
        align: 'left',
        fixed: 'right',
        width: this.isEn ? 120 : 80,
        sorter: true,
      },
    ];
  }
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
    })
      .then(({ alerts, total }) => {
        return {
          total,
          data: alerts || [],
        };
      })
      .catch(() => ({
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
