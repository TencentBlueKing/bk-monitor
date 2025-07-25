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

import { EFieldType, EMethod, type IFilterField } from '@/components/retrieval-filter/typing';
import { isEn } from '@/i18n/i18n';
import { alertTopN, searchAlert } from 'monitor-api/modules/alert';

import {
  type CommonFilterParams,
  type AnalysisTopNDataResponse,
  type AnalysisFieldAggItem,
  type AlertTableItem,
  type FilterTableResponse,
  type QuickFilterItem,
  type TableColumnItem,
  AlarmStatusIconMap,
  AlarmLevelIconMap,
} from '../typings';
import { AlarmService } from './base';
const ALERT_TABLE_COLUMNS = [
  {
    colKey: 'alert_name',
    title: window.i18n.t('告警名称'),
    is_default: true,
    is_locked: true,
    width: 160,
    fixed: 'left',
    sorter: true,
  },
  {
    colKey: 'bk_biz_name',
    title: window.i18n.t('空间名'),
    is_default: true,
    is_locked: false,
    width: 100,
    fixed: 'left',
    sorter: true,
  },
  {
    colKey: 'plugin_display_name',
    title: window.i18n.t('告警来源'),
    is_default: false,
    is_locked: false,
    width: 110,
  },
  {
    colKey: 'category_display',
    title: window.i18n.t('分类'),
    is_default: true,
    is_locked: false,
    width: 160,
  },
  {
    colKey: 'metric',
    title: window.i18n.t('告警指标'),
    is_default: true,
    is_locked: false,
    width: 240,
    sorter: true,
  },
  {
    colKey: 'event_count',
    title: window.i18n.t('关联事件'),
    is_default: true,
    is_locked: false,
    width: 140,
  },
  {
    colKey: 'create_time',
    title: window.i18n.t('创建时间'),
    is_default: false,
    is_locked: false,
    width: 150,
    sorter: true,
  },
  {
    colKey: 'begin_time',
    title: window.i18n.t('开始时间'),
    is_default: false,
    is_locked: false,
    width: 150,
    sorter: true,
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
    colKey: 'latest_time',
    title: window.i18n.t('最新事件时间'),
    is_default: false,
    is_locked: false,
    width: 150,
    sorter: true,
  },
  {
    colKey: 'first_anomaly_time',
    title: window.i18n.t('首次异常时间'),
    is_default: false,
    is_locked: false,
    width: 150,
    sorter: true,
  },
  {
    colKey: 'duration',
    title: window.i18n.t('持续时间'),
    is_default: false,
    is_locked: false,
    sorter: true,
  },
  {
    colKey: 'description',
    title: window.i18n.t('告警内容'),
    is_default: true,
    is_locked: false,
    width: 300,
  },
  {
    colKey: 'target_key',
    title: window.i18n.t('监控目标'),
    is_default: true,
    is_locked: false,
    width: 300,
  },
  {
    colKey: 'tags',
    title: window.i18n.t('维度'),
    is_default: false,
    is_locked: false,
    width: 200,
  },
  {
    colKey: 'extend_info',
    title: window.i18n.t('关联信息'),
    is_default: false,
    is_locked: true,
    width: 250,
  },
  {
    colKey: 'appointee',
    title: window.i18n.t('负责人'),
    is_default: true,
    is_locked: false,
    width: 200,
  },
  {
    colKey: 'assignee',
    title: window.i18n.t('通知人'),
    is_default: true,
    is_locked: false,
    width: 200,
  },
  {
    colKey: 'follower',
    title: window.i18n.t('关注人'),
    is_default: true,
    is_locked: false,
    width: 200,
  },
  {
    colKey: 'strategy_name',
    title: window.i18n.t('策略名称'),
    is_default: false,
    is_locked: false,
  },
  {
    colKey: 'labels',
    title: window.i18n.t('策略标签'),
    is_default: false,
    is_locked: false,
    width: 200,
  },
  {
    colKey: 'stage_display',
    title: window.i18n.t('处理阶段'),
    is_default: true,
    is_locked: false,
    fixed: 'right',
    width: 110,
  },
  {
    colKey: 'status',
    title: window.i18n.t('状态'),
    is_default: true,
    is_locked: true,
    fixed: 'right',
    width: isEn ? 120 : 80,
    sorter: true,
  },
] as const;

export const ALERT_FILTER_FIELDS: IFilterField[] = [
  // 全字段检索
  {
    name: 'query_string',
    alias: '全字段检索',
    type: EFieldType.all,
    methods: [
      {
        alias: '包含',
        value: EMethod.include,
      },
    ],
  },
  // 告警（策略）名称
  {
    name: 'alert_name',
    alias: '告警（策略）名称',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
    ],
  },
  // 策略标签
  {
    name: 'labels',
    alias: '策略标签',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
    ],
  },
  // 指标（支持ID和名称）
  {
    name: 'event.metric',
    alias: '指标',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 告警目标（🆕，支持include/exclude，具体字段名请补充）
  {
    name: 'target', // 具体字段名请根据实际补充
    alias: '告警目标',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 状态
  {
    name: 'status',
    alias: '状态',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 告警内容
  {
    name: 'event.description',
    alias: '告警内容',
    type: EFieldType.text,
    isEnableOptions: true,
    methods: [
      {
        alias: '不等于',
        value: EMethod.ne,
      },
      {
        alias: '等于',
        value: EMethod.eq,
      },
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
    ],
  },
  // 级别
  {
    name: 'severity',
    alias: '级别',
    type: EFieldType.integer,
    isEnableOptions: true,
    methods: [
      {
        alias: '不等于',
        value: EMethod.ne,
      },
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 目标IP
  {
    name: 'event.ip',
    alias: '目标IP',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 通知人
  {
    name: 'assignee',
    alias: '通知人',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 负责人
  {
    name: 'appointee',
    alias: '负责人',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 关注人
  {
    name: 'follower',
    alias: '关注人',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 维度（query_string，单选，复用query_string字段）
  {
    name: 'tags.apiname',
    alias: '维度',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 处理套餐
  {
    name: 'action_name',
    alias: '处理套餐',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
    ],
  },
  // 告警来源
  {
    name: 'event.plugin_id',
    alias: '告警来源',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '等于',
        value: EMethod.eq,
      },
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
    ],
  },
  // 目标IPv6
  {
    name: 'event.ipv6',
    alias: '目标IPv6',
    type: EFieldType.keyword,
    isEnableOptions: true,
    methods: [
      {
        alias: '包含',
        value: EMethod.include,
      },
      {
        alias: '不包含',
        value: EMethod.exclude,
      },
      {
        alias: '等于',
        value: EMethod.eq,
      },
    ],
  },
  // 其它不支持include/exclude的字段可继续补充
];

export const ALERT_STORAGE_KEY = '__ALERT_EVENT_COLUMN__';
export class AlertService extends AlarmService {
  readonly storageAnalysisKey = '__ALERT_ANALYZE_STORAGE_KEY__';
  readonly storageKey = ALERT_STORAGE_KEY;
  get allTableColumns(): TableColumnItem[] {
    return [...ALERT_TABLE_COLUMNS];
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
  get analysisFieldsMap() {
    return {
      alert_name: window.i18n.t('告警名称'),
      metric: window.i18n.t('指标ID'),
      duration: window.i18n.t('持续时间'),
      ip: window.i18n.t('目标IP'),
      bk_cloud_id: window.i18n.t('管控区域ID'),
      strategy_id: window.i18n.t('策略ID'),
      strategy_name: window.i18n.t('策略名称'),
      assignee: window.i18n.t('通知人'),
      bk_service_instance_id: window.i18n.t('服务实例ID'),
      appointee: window.i18n.t('负责人'),
      labels: window.i18n.t('策略标签'),
      plugin_id: window.i18n.t('告警来源'),
      ipv6: window.i18n.t('目标IPv6'),
    };
  }

  get filterFields(): IFilterField[] {
    return [...ALERT_FILTER_FIELDS];
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
        const alarmStatusList = [];
        for (const item of overview?.children || []) {
          if (item.id === 'MY_APPOINTEE') {
            myAlarmList.push({
              ...item,
              icon: 'icon-gaojingfenpai',
              name: window.i18n.t('分派给我的'),
            });
            continue;
          }
          if (item.id === 'MY_ASSIGNEE') {
            myAlarmList.push({
              ...item,
              icon: 'icon-inform-circle',
              name: window.i18n.t('通知给我'),
            });
            continue;
          }
          // 告警状态
          if (['NOT_SHIELDED_ABNORMAL', 'SHIELDED_ABNORMAL', 'RECOVERED'].includes(item.id)) {
            alarmStatusList.push({
              ...item,
              ...AlarmStatusIconMap[item.id],
            });
          }
        }

        return [
          {
            id: 'MINE',
            name: window.i18n.t('与我相关'),
            count: myAlarmList.reduce((total, item) => total + item.count, 0),
            children: myAlarmList,
          },
          {
            id: 'STATUS',
            name: window.i18n.t('状态'),
            count: myAlarmList.reduce((total, item) => total + item.count, 0),
            children: alarmStatusList,
          },
          ...aggs.map(item => {
            if (item.id === 'severity') {
              return {
                ...item,
                children: item.children.map(child => ({
                  ...child,
                  ...AlarmLevelIconMap[child.id],
                })),
              };
            }
            return item;
          }),
        ];
      })
      .catch(() => []);
    console.info('AlertService getQuickFilterList', data, '==========');
    return data;
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
