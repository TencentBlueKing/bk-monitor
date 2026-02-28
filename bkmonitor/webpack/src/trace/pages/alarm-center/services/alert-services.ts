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

import { isEn } from '@/i18n/i18n';

import { alertTopN, editDataMeaning, searchAlert } from 'monitor-api/modules/alert_v2';
import { getMethodIdForLowerCase } from 'monitor-pc/pages/query-template/components/utils/utils';
import { MetricDetailV2, QueryConfig } from 'monitor-pc/pages/query-template/typings';

import {
  type AlertContentNameEditInfo,
  type AlertTableItem,
  type AnalysisFieldAggItem,
  type AnalysisTopNDataResponse,
  type CommonFilterParams,
  type FilterTableResponse,
  type QuickFilterItem,
  type TableColumnItem,
  AlarmLevelIconMap,
  AlarmStatusIconMap,
} from '../typings';
import { type RequestOptions, AlarmService } from './base';
import { type IFilterField, EFieldType } from '@/components/retrieval-filter/typing';
const ALERT_TABLE_COLUMNS = [
  {
    colKey: 'alert_name',
    title: window.i18n.t('告警名称'),
    is_default: true,
    is_locked: true,
    minWidth: 160,
    fixed: 'left',
    sorter: false,
  },
  {
    colKey: 'create_time',
    title: window.i18n.t('创建时间'),
    is_default: true,
    is_locked: false,
    minWidth: 150,
    sorter: true,
  },
  {
    colKey: 'description',
    title: window.i18n.t('告警内容'),
    is_default: true,
    is_locked: false,
    minWidth: 300,
  },
  {
    colKey: 'target_key',
    title: window.i18n.t('监控目标'),
    is_default: true,
    is_locked: false,
    minWidth: 300,
  },

  {
    colKey: 'plugin_display_name',
    title: window.i18n.t('告警来源'),
    is_default: false,
    is_locked: false,
    minWidth: 110,
  },
  {
    colKey: 'category_display',
    title: window.i18n.t('分类'),
    is_default: false,
    is_locked: false,
    minWidth: 160,
  },
  {
    colKey: 'metric',
    title: window.i18n.t('告警指标'),
    is_default: false,
    is_locked: false,
    minWidth: 240,
    sorter: true,
  },
  {
    colKey: 'event_count',
    title: window.i18n.t('关联事件'),
    is_default: false,
    is_locked: false,
    minWidth: 140,
  },

  {
    colKey: 'begin_time',
    title: window.i18n.t('开始时间'),
    is_default: false,
    is_locked: false,
    minWidth: 150,
    sorter: true,
  },
  {
    colKey: 'end_time',
    title: window.i18n.t('结束时间'),
    is_default: false,
    is_locked: false,
    minWidth: 150,
    sorter: true,
  },
  {
    colKey: 'latest_time',
    title: window.i18n.t('最新事件时间'),
    is_default: false,
    is_locked: false,
    minWidth: 150,
    sorter: true,
  },
  {
    colKey: 'first_anomaly_time',
    title: window.i18n.t('首次异常时间'),
    is_default: false,
    is_locked: false,
    minWidth: 150,
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
    colKey: 'tags',
    title: window.i18n.t('维度'),
    is_default: false,
    is_locked: false,
    minWidth: 240,
  },
  {
    colKey: 'extend_info',
    title: window.i18n.t('关联信息'),
    is_default: false,
    is_locked: false,
    minWidth: 250,
  },
  {
    colKey: 'appointee',
    title: window.i18n.t('负责人'),
    is_default: false,
    is_locked: false,
    minWidth: 200,
  },
  {
    colKey: 'assignee',
    title: window.i18n.t('通知人'),
    is_default: false,
    is_locked: false,
    minWidth: 200,
  },
  {
    colKey: 'follower',
    title: window.i18n.t('关注人'),
    is_default: false,
    is_locked: false,
    minWidth: 200,
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
    minWidth: 240,
  },
  {
    colKey: 'bk_biz_name',
    title: window.i18n.t('空间名'),
    is_default: true,
    is_locked: true,
    minWidth: 100,
    sorter: false,
    fixed: 'right',
  },
  {
    colKey: 'stage_display',
    title: window.i18n.t('处理阶段'),
    is_default: true,
    is_locked: false,
    fixed: 'right',
    minWidth: 110,
  },
  {
    colKey: 'status',
    title: window.i18n.t('状态'),
    is_default: true,
    is_locked: true,
    fixed: 'right',
    minWidth: isEn ? 120 : 80,
    sorter: true,
  },
] as const;

export const ALERT_FILTER_FIELDS: IFilterField[] = [
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
    name: 'alert_name',
    alias: '告警（策略）名称',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'id',
    alias: '告警ID',
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
    alias: '状态',
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
    name: 'description',
    alias: '告警内容',
    type: EFieldType.text,
    methods: [
      {
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'severity',
    alias: '级别',
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
    name: 'metric',
    alias: '指标ID',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'ip',
    alias: '目标IP',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'ipv6',
    alias: '目标IPv6',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'bk_host_id',
    alias: '主机ID',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'bk_cloud_id',
    alias: '目标云区域ID',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'bk_service_instance_id',
    alias: '目标服务实例ID',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'appointee',
    alias: '负责人',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'assignee',
    alias: '通知人',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'follower',
    alias: '关注人',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'strategy_name',
    alias: '策略名称', //
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'strategy_id',
    alias: '策略ID',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'labels',
    alias: '策略标签',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'tags',
    alias: '维度',
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
  // tags 维度查询示例：
  // {
  //	"key": "tags.auto_instance_id_0",
  //  "value":["node-30-167-61-50"],
  //  "method":"eq",
  //  "condition":"and"
  // }
  {
    name: 'plugin_id',
    alias: '告警来源',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'action_name',
    alias: '处理套餐名',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  {
    name: 'bk_topo_node',
    alias: 'cmdb集群',
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
        alias: '包含',
        value: 'include',
      },
      {
        alias: '不包含',
        value: 'exclude',
      },
    ],
  },
  // {
  //   name: 'bk_topo_node',
  //   alias: 'cmdb模块',
  //   type: EFieldType.keyword,
  //   isEnableOptions: true,
  //   methods: [
  //     {
  //       alias: '=',
  //       value: 'eq',
  //     },
  //     {
  //       alias: '!=',
  //       value: 'neq',
  //     },
  //     {
  //       alias: '包含',
  //       value: 'include',
  //     },
  //     {
  //       alias: '不包含',
  //       value: 'exclude',
  //     },
  //   ],
  // },
  {
    name: 'action_id',
    alias: '处理记录ID',
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
];

export const ALERT_STORAGE_KEY = '__ALERT_EVENT_COLUMN__';
export class AlertService extends AlarmService {
  readonly storageAnalysisKey = '__ALERT_ANALYZE_STORAGE_KEY__';
  readonly storageKey = ALERT_STORAGE_KEY;
  get allTableColumns(): TableColumnItem[] {
    return [...ALERT_TABLE_COLUMNS];
  }
  get analysisDefaultSettingsFields(): string[] {
    return ['alert_name', 'metric', 'duration', 'ip'];
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
  async getFilterTableList<T = AlertTableItem>(
    params: Partial<CommonFilterParams>,
    options?: RequestOptions
  ): Promise<FilterTableResponse<T>> {
    const data = await searchAlert(
      {
        ...params,
        show_overview: false, // 是否展示概览
        show_aggs: false, // 是否展示聚合
      },
      options
    )
      .then(({ alerts, total }) => {
        // 将后端queryConfig相关数转换组装为前端定义统一的 QueryConfig 格式
        for (const alert of alerts || []) {
          const sourceQueryConfigs = alert.items[0]?.query_configs || [];
          const queryConfigs: QueryConfig[] = [];
          for (const source of sourceQueryConfigs) {
            const metricDetail = alert?.metric_display?.find?.(metric => metric.id === source.metric_id);
            queryConfigs.push(
              new QueryConfig(
                new MetricDetailV2({
                  metric_id: source.metric_id,
                  metric_field_name: metricDetail?.name || '',
                  dimensions: Object.entries(source.agg_dimension).map(([key, value]) => ({
                    id: key,
                    // @ts-expect-error
                    name: value?.display_name || '',
                  })),
                }),
                {
                  agg_condition: source.agg_condition,
                  agg_dimension: Object.keys(source.agg_dimension),
                  functions: source.functions,
                  metric_id: source.metric_id,
                  agg_interval: source.agg_interval,
                  alias: source.alias,
                  agg_method: getMethodIdForLowerCase(source.agg_method) || 'AVG',
                }
              )
            );
          }
          alert.items[0].query_configs = queryConfigs;
        }
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

/**
 * @description 保存告警内容数据含义
 * @param {AlertContentNameEditInfo} saveInfo 保存接口参数信息
 * @returns {Promise<boolean>} 是否保存成功
 */
export const saveAlertContentName = async (saveInfo: AlertContentNameEditInfo) => {
  return await editDataMeaning(saveInfo);
};
