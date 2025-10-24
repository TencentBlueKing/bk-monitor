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

import type { AlgorithmType } from '../components/template-form/typing';
import type { DetectionAlgorithmLevelEnumType } from './constants';

export interface AlarmAlgorithmItem {
  level: DetectionAlgorithmLevelEnumType;
  type: AlgorithmType;
  unit_prefix?: string;
  config: {
    method: string;
    threshold: number;
  };
}

export interface AlarmListRequestParams {
  /** apm 应用名称 */
  app_name?: string;
  /** 业务ID */
  bk_biz_id?: number;
  /** 搜索，支持模板名称，模板说明，创建人，更新人 */
  conditions?: { key: string; value: string[] }[];
  simple?: boolean;
}

export interface AlarmTemplateAlertRequestParams {
  app_name: string;
  bk_biz_id?: number;
  ids: AlarmTemplateListItem['id'][];
  need_strategies: boolean;
}

export interface AlarmTemplateAlertsItem extends Pick<AlarmTemplateListItem, 'alert_number' | 'id'> {
  strategies?: StrategiesItem[];
}
export interface AlarmTemplateBatchUpdateParams {
  /** apm 应用名称 */
  app_name?: string;
  /** 更新的数据 */
  edit_data: Partial<AlarmTemplateListItem>;
  /** 需要更新的模板id数组 */
  ids: AlarmTemplateListItem['id'][];
}

export interface AlarmTemplateConditionParamItem {
  key: string;
  value: string[];
}

export interface AlarmTemplateDestroyParams {
  /** apm 应用名称 */
  app_name: string;
  /** 需要删除的模板id数组 */
  strategy_template_id: AlarmTemplateListItem['id'];
}

export type AlarmTemplateField = string;

export interface AlarmTemplateListItem {
  /** 关联告警数 */
  alert_number?: number;
  algorithms: AlarmAlgorithmItem[];
  applied_service_names: string[];
  create_time: string;
  create_user: string;
  id: number;
  is_auto_apply: boolean;
  is_enabled: boolean;
  name: string;
  type: string;
  update_time: string;
  update_user: string;
  user_group_list: AlarmUserGroupItem[];
  category: {
    alias: string;
    value: string;
  };
  system: {
    alias: string;
    value: string;
  };
}

export interface AlarmTemplateOptionsItem {
  id: string;
  name: string;
  value: boolean | number | string;
}

export interface AlarmUserGroupItem {
  id: number;
  name: string;
}

export interface GetAlarmTemplateOptionsParams {
  /** apm 应用名称 */
  app_name: string;
  /** 需要获取候选项值的字段 */
  fields: string[];
}

/** 表格排序属性 */
export interface ITableSort {
  order: 'ascending' | 'descending' | null;
  prop: string;
}

export interface StrategiesItem {
  alert_number: number;
  service_name: string;
  strategy_id: number;
}
