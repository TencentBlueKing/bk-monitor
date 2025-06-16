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
export enum EShieldType {
  Dimension = 'alarm-shield-dimension',
  Event = 'alarm-shield-event',
  Scope = 'alarm-shield-scope',
  Strategy = 'alarm-shield-strategy',
}

export const categoryMap = {
  [EShieldType.Scope]: 'scope',
  [EShieldType.Strategy]: 'strategy',
  [EShieldType.Dimension]: 'dimension',
  [EShieldType.Event]: 'alert',
};

export enum EColumn {
  beginTime = 'begin_time',
  currentCycleRamainingTime = 'currentCycleRamainingTime',
  cycleDuration = 'cycleDuration',
  description = 'description',
  endTime = 'endTime',
  failureTime = 'failure_time',
  id = 'id',
  operate = 'operate',
  shieldContent = 'shieldContent',
  shieldCycle = 'shieldCycle',
  // shieldType = 'shieldType',
  status = 'status',
  // updateUser = 'update_user',
}

export interface IColumn {
  id: EColumn;
  name: string;
  minWidth?: number;
  width?: number;
  disabled?: boolean;
  sortable?: boolean;
  filterMultiple?: boolean;
  filter?: { label: string; value: string; checked?: boolean }[];
}

interface DimensionConfig {
  id: number[];
}

export interface AlarmShieldTableItem {
  id: number;
  bk_biz_id: number;
  category: string;
  category_name: string;
  status: number;
  status_name: string;
  dimension_config: DimensionConfig;
  content: string;
  begin_time: string;
  failure_time: string;
  cycle_duration: string;
  description: string;
  source: string;
  update_user: string;
  label: string;
}
