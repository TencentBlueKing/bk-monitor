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

import type { AlarmTemplateTypeEnumType, DetectionAlgorithmLevelEnumType } from './typing';
import type { ITableFilterItem } from 'monitor-pc/pages/monitor-k8s/typings';

/** apm 告警模板 侧弹详情抽屉面板 Tab Enum 枚举 */
export const AlarmTemplateDetailTabEnum = {
  /** 基础信息 */
  BASE_INFO: 'base_info',
  /** 关联服务&告警 */
  RELATE_SERVICE_ALARM: 'relate_service_alarm',
} as const;

/** 告警模板类型 Enum 枚举 */
export const AlarmTemplateTypeEnum = {
  /** 内置模板 */
  INNER: 'builtin',
  /** 克隆模板 */
  APP: 'app',
} as const;

/** 批量操作类型 Enum 枚举 */
export const BatchOperationTypeEnum = {
  /** 开启自动下发 */
  AUTO_APPLY: 'auto_apply',
  /** 关闭自动下发 */
  AUTO_CANCEL: 'auto_cancel',
} as const;

/** 检测算法级别 Enum 枚举 */
export const DetectionAlgorithmLevelEnum = {
  /** 致命 */
  ERROR: 1,
  /** 预警 */
  WARNING: 2,
  /** 提示 */
  INFO: 3,
} as const;

/** 告警模板类型快速筛选 */
export const ALARM_TEMPLATE_QUICK_FILTER_LIST: ('all' | AlarmTemplateTypeEnumType)[] = [
  'all',
  AlarmTemplateTypeEnum.INNER,
  AlarmTemplateTypeEnum.APP,
];

/** apm 告警模板列表-表格默认展示字段 */
export const TABLE_DEFAULT_DISPLAY_FIELDS = [
  'name',
  'system',
  'update_time',
  'applied_service_names',
  'algorithms',
  'user_group_list',
  'is_enabled',
  'is_auto_apply',
  'operator',
];

/** 需要获取告警模板候选项值的字段 */
export const ALARM_TEMPLATE_OPTIONS_FIELDS = [
  'system',
  'update_user',
  'applied_service_name',
  'user_group_id',
  'is_enabled',
  'is_auto_apply',
];

/** 告警模板列表-搜索组件下拉选项 */
export const SEARCH_SELECT_OPTIONS = [
  {
    name: window.i18n.t('全文检索'),
    id: 'query',
    multiple: true,
  },
  {
    name: window.i18n.t('模板名称'),
    id: 'name',
    multiple: true,
    children: [],
  },
  {
    name: window.i18n.t('模板类型'),
    id: 'system',
    multiple: true,
    onlyRecommendChildren: true,
    children: [],
  },
  {
    name: window.i18n.t('最近更新人'),
    id: 'update_user',
    multiple: true,
    children: [],
  },
  {
    name: window.i18n.t('关联服务'),
    id: 'applied_service_name',
    multiple: true,
    children: [],
  },
  {
    name: window.i18n.t('告警组'),
    id: 'user_group_id',
    multiple: true,
    onlyRecommendChildren: true,
    children: [],
  },
  {
    name: window.i18n.t('启停'),
    id: 'is_enabled',
    multiple: true,
    onlyRecommendChildren: true,
    children: [],
  },
  {
    name: window.i18n.t('自动下发'),
    id: 'is_auto_apply',
    multiple: true,
    onlyRecommendChildren: true,
    children: [],
  },
];

/** 告警模板列表-表格表头允许筛选操作的字段 */
export const ALARM_TEMPLATE_TABLE_FILTER_FIELDS = new Set(['system', 'user_group_list', 'is_enabled', 'is_auto_apply']);

/** 告警模板列表-表格表头字段与筛选字段的映射 */
export const AlarmTemplateTableFieldToFilterFieldMap: Record<string, string> = {
  system: 'system',
  user_group_list: 'user_group_id',
  is_enabled: 'is_enabled',
  is_auto_apply: 'is_auto_apply',
  applied_service_names: 'applied_service_name',
};

/** 告警模板类型 Map */
export const AlarmTemplateTypeMap: Record<'all' | AlarmTemplateTypeEnumType, ITableFilterItem> = {
  all: {
    icon: '',
    id: 'all',
    name: window.i18n.t('全部模板') as unknown as string,
  },
  [AlarmTemplateTypeEnum.INNER]: {
    icon: 'icon-neizhi',
    id: AlarmTemplateTypeEnum.INNER,
    name: window.i18n.t('内置模板') as unknown as string,
  },
  [AlarmTemplateTypeEnum.APP]: {
    icon: 'icon-kelong',
    id: AlarmTemplateTypeEnum.APP,
    name: window.i18n.t('克隆模板') as unknown as string,
  },
};

/** 检测算法级别 Map */
export const DetectionAlgorithmLevelMap: Record<
  DetectionAlgorithmLevelEnumType,
  Omit<ITableFilterItem, 'id'> & { id: number }
> = {
  [DetectionAlgorithmLevelEnum.ERROR]: {
    icon: 'icon-danger',
    id: DetectionAlgorithmLevelEnum.ERROR,
    name: window.i18n.t('致命') as unknown as string,
  },
  [DetectionAlgorithmLevelEnum.WARNING]: {
    icon: 'icon-mind-fill',
    id: DetectionAlgorithmLevelEnum.WARNING,
    name: window.i18n.t('预警') as unknown as string,
  },
  [DetectionAlgorithmLevelEnum.INFO]: {
    icon: 'icon-tips',
    id: DetectionAlgorithmLevelEnum.INFO,
    name: window.i18n.t('提醒') as unknown as string,
  },
};

/** 批量操作下拉列表 */
export const BATCH_OPERATION_LIST = [
  {
    id: BatchOperationTypeEnum.AUTO_APPLY,
    name: window.i18n.t('开启自动下发') as unknown as string,
  },
  {
    id: BatchOperationTypeEnum.AUTO_CANCEL,
    name: window.i18n.t('关闭自动下发') as unknown as string,
  },
];

// 支持初始化时弹出策略模板详情侧栏
export const TEMPLATE_DETAILS_ROUTER_QUERY_KEY = 'strategy_template_details_id';
export const APM_ALARM_TEMPLATE_ROUTER_QUERY_KEYS = [TEMPLATE_DETAILS_ROUTER_QUERY_KEY];

/** 表格滚动容器元素 */
export const SCROLL_CONTAINER_DOM = '.bk-table-body-wrapper';
/** 表格滚动时需要禁用事件触发的元素 */
export const DISABLE_TARGET_DOM = '.bk-table-body';
