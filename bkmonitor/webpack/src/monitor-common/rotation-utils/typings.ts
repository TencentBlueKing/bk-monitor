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
import type { RotationSelectTypeEnum } from './common';
export type CustomTabType = 'classes' | 'duration';
export type WorkTimeType = 'datetime_range' | 'time_range';
export interface FixedDataModel {
  id?: number;
  key: number | string;
  type:
    | RotationSelectTypeEnum.Daily
    | RotationSelectTypeEnum.DateRange
    | RotationSelectTypeEnum.Monthly
    | RotationSelectTypeEnum.Weekly;
  workDays: (number | string)[];
  workDateRange: [];
  workTime: string[][];
  orderIndex: number;
  users: { type: 'group' | 'user'; id: string }[];
}

export interface ReplaceItemDataModel {
  id?: number;
  date: {
    type: RotationSelectTypeEnum;
    /** 每周、每月：时间范围/起止时间 */
    workTimeType: WorkTimeType;
    /** 是否是自定义轮值类型 */
    isCustom: boolean;
    /** 自定义：指定时长/指定班次 */
    customTab: CustomTabType;
    /** 自定义轮值有效日期 */
    customWorkDays: number[];
    /** 单班时长 */
    periodSettings: { unit: 'day' | 'hour'; duration: number };
    value: ReplaceRotationDateModel[];
  };
  users: ReplaceRotationUsersModel;
}

export interface ReplaceDataModel extends ReplaceItemDataModel {
  key: number;
}

export interface ReplaceRotationDateModel {
  key: number | string;
  workDays?: number[];
  workTime: string[][];
}

export interface ReplaceRotationUsersModel {
  groupNumber?: number;
  groupType: 'auto' | 'specified';
  value: { key: number; value: { type: 'group' | 'user'; id: string }[]; orderIndex: number }[];
}
