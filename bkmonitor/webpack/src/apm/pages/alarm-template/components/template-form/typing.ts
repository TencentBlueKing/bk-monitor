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
import type { QueryTemplateDetail } from 'monitor-pc/pages/query-template/typings';

/** 策略模板类型 */
export type TemplateType = 'EVENT' | 'K8S' | 'LOG' | 'METRIC' | 'RPC' | 'TRACE';

/** 策略模板类型枚举 */
export const TemplateTypeEnum = {
  RPC: 'RPC',
  K8S: 'K8S',
  METRIC: 'METRIC',
  LOG: 'LOG',
  TRACE: 'TRACE',
  EVENT: 'EVENT',
} as const;

/** 策略模板类型映射 */
export const TemplateTypeMap = {
  [TemplateTypeEnum.RPC]: window.i18n.tc('调用分析'),
  [TemplateTypeEnum.K8S]: window.i18n.tc('容器'),
  [TemplateTypeEnum.METRIC]: window.i18n.tc('自定义指标'),
  [TemplateTypeEnum.LOG]: window.i18n.tc('日志'),
  [TemplateTypeEnum.TRACE]: window.i18n.tc('调用链'),
  [TemplateTypeEnum.EVENT]: window.i18n.tc('事件'),
};

/** 检测算法类型 */
export type AlgorithmType = 'Threshold';

/** 检测算法枚举 */
export const AlgorithmEnum = {
  Threshold: 'Threshold',
} as const;

/** 算法告警级别 */
export const LevelMap = {
  1: window.i18n.tc('致命'),
  2: window.i18n.tc('预警'),
  3: window.i18n.tc('提醒'),
};

/** 检测算法 */
export interface AlgorithmItem {
  level: 1 | 2 | 3;
  type: AlgorithmType;
  unit_prefix?: string;
  config: {
    method: string;
    threshold: number;
  };
}

/** 触发条件 */
export interface DetectConfig {
  type: string;
  config: {
    recovery_check_window: number;
    trigger_check_window: number;
    trigger_count: number;
  };
}

/** 策略模板分类 */
export type TemplateCategoryType = 'CALLEE' | 'CALLER' | 'DEFAULT';

/** 用户组 */
export interface UserGroupItem {
  id: number;
  name: string;
}

/** 策略模板分类枚举 */
export const TemplateCategoryEnum = {
  DEFAULT: 'DEFAULT',
  CALLER: 'CALLER',
  CALLEE: 'CALLEE',
} as const;

/** 策略模板分类映射 */
export const TemplateCategoryMap = {
  [TemplateCategoryEnum.DEFAULT]: window.i18n.tc('默认'),
  [TemplateCategoryEnum.CALLER]: window.i18n.tc('主调'),
  [TemplateCategoryEnum.CALLEE]: window.i18n.tc('被调'),
};

export type EditTemplateFormData = Pick<
  TemplateDetail,
  'algorithms' | 'detect' | 'is_auto_apply' | 'name' | 'query_template' | 'system' | 'user_group_list'
>;

/** 策略模板详情 */
export interface TemplateDetail {
  algorithms: AlgorithmItem[];
  app_name: string;
  category: TemplateCategoryType;
  context: Record<string, any>;
  detect: DetectConfig;
  id: number;
  is_auto_apply: boolean;
  is_enabled: boolean;
  labels: string[];
  name: string;
  query_template: QueryTemplateDetail;
  user_group_list: UserGroupItem[];
  system: {
    alias: string;
    value: TemplateType;
  };
}
