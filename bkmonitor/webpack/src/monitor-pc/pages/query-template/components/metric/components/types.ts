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

import { MetricType } from '@/pages/strategy-config/strategy-config-set-new/typings';

import type { MetricDetailV2 } from '@/pages/query-template/typings';

export type MetricSearchTag = {
  id: string;
  name: string;
};

export const MetricSearchTagModeMap = {
  /** 数据类型 */
  DataType: 'data_type',
  /** 监控场景 */
  MonitorScenes: 'scenes',
} as const;

export const MetricSearchTags = {
  [MetricSearchTagModeMap.DataType]: {
    name: window.i18n.t('数据类型'),
    tags: [
      {
        id: 'all',
        name: window.i18n.t('全部'),
      },
      {
        id: 'time_series',
        name: window.i18n.t('指标'),
      },
      {
        id: 'event',
        name: window.i18n.t('事件'),
      },
      {
        id: 'log',
        name: window.i18n.t('日志'),
      },
    ],
  },
  [MetricSearchTagModeMap.MonitorScenes]: {
    name: window.i18n.t('监控场景'),
    tags: [
      {
        id: 'all',
        name: window.i18n.t('全部'),
      },
      {
        id: 'bk_apm',
        name: window.i18n.t('APM'),
      },
      {
        id: 'rum',
        name: window.i18n.t('RUM'),
      },
      {
        id: 'host',
        name: window.i18n.t('主机'),
      },
      {
        id: 'performance',
        name: window.i18n.t('拨测'),
      },
      {
        id: 'k8s',
        name: window.i18n.t('容器'),
      },
    ],
  },
} as const;

export type MetricSearchTagMode = (typeof MetricSearchTagModeMap)[keyof typeof MetricSearchTagModeMap];

export const MetricDataSourceLabelMap = {
  // 监控指标
  [MetricType.TimeSeries]: [
    { id: 'bk_monitor', name: window.i18n.t('监控采集指标'), count: 0 },
    { id: 'bk_data', name: window.i18n.t('计算平台指标'), count: 0 },
    { id: 'custom', name: window.i18n.t('自定义指标'), count: 0 },
    { id: 'bk_log_search', name: window.i18n.t('日志平台指标'), count: 0 },
    { id: 'bk_apm', name: 'APM', count: 0 },
  ],
  // 事件数据
  [MetricType.EVENT]: [
    { id: 'bk_monitor', name: window.i18n.t('系统事件'), count: 0 },
    { id: 'custom', name: window.i18n.t('自定义事件'), count: 0 },
    { id: 'bk_fta', name: window.i18n.t('第三方告警'), count: 0 },
  ],
  // 日志数据
  [MetricType.LOG]: [
    { id: 'bk_monitor', name: window.i18n.t('监控采集'), count: 0 },
    { id: 'bk_log_search', name: window.i18n.t('日志平台'), count: 0 },
    { id: 'bk_apm', name: window.i18n.t('应用监控'), count: 0 },
  ],
  // 关联告警
  [MetricType.ALERT]: [
    { id: 'bk_monitor', name: window.i18n.t('告警策略'), count: 0 },
    { id: 'bk_fta', name: window.i18n.t('第三方告警'), count: 0 },
  ],
};

/** 指标维度 */
/** 数据源项 */
export interface IDataSourceItem {
  count: number;
  data_source_label: string;
  data_type_label: string;
  id: string;
  name: string;
}

/** 触发器默认配置 */
export interface IDefaultTriggerConfig {
  check_window: number;
  count: number;
}

/** 获取指标列表数据结构 */
export interface IGetMetricListData {
  count: number;
  data_source_list: IDataSourceItem[];
  metric_list: MetricDetailV2[];
  scenario_list: IScenarioItem[];
  tag_list: ITagItem[];
}

export interface IGetMetricListParams {
  conditions?: Record<string, unknown>[];
  data_type_label?: string;
  keyword?: string;
  page: number;
  page_size: number;
  tag?: string;
}

/** 指标维度 */
export interface IMetricDimension {
  id: string;
  is_dimension: boolean;
  name: string;
  type: string;
}

/** 场景项 */
export interface IScenarioItem {
  count: number;
  id: string;
  name: string;
}

/** 标签项 */
export interface ITagItem {
  id: string;
  name: string;
}
