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

import { type AlarmType } from './constants';
import { type EMode } from '@/components/retrieval-filter/typing';

export * from './alarm-chart';
export * from './alarm-info';
export * from './constants';
export * from './detail';
export * from './dialog';
export * from './panel-host';
export * from './panel-k8s';
export * from './panel-trace';
export * from './services';
export * from './shield';
export * from './table';

/**
 * @description: 告警中心URL参数
 */
export interface AlarmUrlParams {
  /** 告警ID */
  alarmId: string;
  /** 告警类型 */
  alarmType: AlarmType;
  /** 业务ID列表 */
  bizIds: string;
  /** 告警条件 */
  conditions: string;
  /** 当前页码 */
  currentPage: number;
  /** 筛选模式 */
  filterMode: EMode;
  /** 开始时间 */
  from: string;
  /** 查询字符串 */
  queryString: string;
  /** 快速筛选值 */
  quickFilterValue: string;
  /** 刷新时间间隔 */
  refreshInterval: string;
  /** 常驻条件 */
  residentCondition: string;
  /** 是否显示详情 */
  showDetail: string;
  /** 表格排序顺序 */
  sortOrder: string;
  /** 时区 */
  timezone: string;
  /** 结束时间 */
  to: string;
}
