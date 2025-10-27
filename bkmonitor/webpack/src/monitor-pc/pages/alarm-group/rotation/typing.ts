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

import type { EStatus } from '../../../../trace/pages/rotation/typings/common';

export interface DutyNotice {
  hit_first_duty?: boolean; // api 生成的轮值数据
  personal_notice?: PersonalNotice;
  plan_notice?: PlanNotice;
}

// 添加类型定义
export interface DutyRule {
  // 根据实际使用情况补充字段
  [key: string]: any;
}

export interface IDutyItem {
  category: string;
  id: number | string;
  name: string;
  status: EStatus;
  typeLabel: string;
}

export interface IDutyListItem {
  category: string;
  id: number | string;
  isCheck: boolean;
  labels: string[];
  name: string;
  show: boolean;
  status: EStatus;
  typeLabel: string;
}

export interface PersonalNotice {
  duty_rules: DutyRule[];
  enabled: boolean;
  hours_ago: number;
}

export interface PlanNotice {
  chat_ids: string[];
  date: number;
  days: number;
  enabled: boolean;
  time: string;
  type: 'daily' | 'monthly' | 'weekly'; // 根据实际可能的值调整
}
