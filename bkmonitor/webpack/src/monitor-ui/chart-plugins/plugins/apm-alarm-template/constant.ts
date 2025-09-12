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

import type { ITableFilterItem } from 'monitor-pc/pages/monitor-k8s/typings';

/** 告警模板类型快速筛选 */
export const ALARM_TEMPLATE_QUICK_FILTER_LIST: ITableFilterItem[] = [
  {
    icon: '',
    id: 'all',
    name: window.i18n.t('全部模板') as unknown as string,
  },
  {
    icon: '',
    id: 'inner',
    name: window.i18n.t('内置模板') as unknown as string,
  },
  {
    icon: '',
    id: 'app',
    name: window.i18n.t('克隆模板') as unknown as string,
  },
];

/** 批量操作类型 Enum 枚举 */
export const BatchOperationTypeEnum = {
  /** 开启自动下发 */
  AUTO_APPLY: 'auto_apply',
  /** 关闭自动下发 */
  AUTO_CANCEL: 'auto_cancel',
} as const;

/** apm 告警模板 侧弹详情抽屉面板 Tab 枚举 */
export const AlarmTemplateDetailTabEnum = {
  /** 基础信息 */
  BASE_INFO: 'base_info',
  /** 关联服务&告警 */
  RELATE_SERVICE_ALARM: 'relate_service_alarm',
} as const;

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
