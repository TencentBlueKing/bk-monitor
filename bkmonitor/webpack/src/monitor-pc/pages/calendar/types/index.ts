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

import dayjs from 'dayjs';

/** 日历服务列表的弹层层级 */
export const Z_INDEX = 2500;

export enum ERepeatKey {
  custom = 'custom',
  everyDay = 'every-day',
  everyMonth = 'every-month',
  everyWeek = 'every-week',
  everyWorkingDay = 'every-working-day',
  everyYear = 'every-year',
  noRepeat = 'no-repeat',
}

/** 自定义类型id */
export enum ERepeatTypeId {
  days = 'day', // 天
  months = 'month', // 月
  weeks = 'week', // 周
  years = 'year', // 年
}

/** 日历列表数据 */
export interface ICalendarListItem {
  checked: boolean;
  color: string;
  id: number | string;
  name: string;
}

/** 事项列表数据结构 */
export interface ICalendarTableItem {
  calendar_id: number; // 归属日历
  end_time: number; // 结束时间
  id: number;
  is_first?: boolean; // 是否为重复项的第一条数据
  name: string; // 事项名称
  parent_id: number; // 修改了当独项才会出现
  repeat: IRepeatParams; // 重复选项
  start_time: number; // 开始时间
  status: boolean; // 事项是否有效
  time_zone?: string; // 时区
}

/** 日历列表侧边栏数据结构 */
export interface ICalendarTypeListItem {
  list: ICalendarListItem[];
  title: string;
}

export interface IOptionsItem {
  disabled?: boolean;
  id: number | string;
  name: string;
}

/** 重复配置数据格式 */
export interface IRepeatConfig {
  every: number[]; // 区间
  exclude_date: number[]; // 排除事项日期
  freq: ERepeatTypeId;
  interval: number; // 间隔
  until: number; // 结束日期
}

export interface IRepeatParams {
  every: number[]; // 区间
  exclude_date: number[]; // 排除事项日期
  freq: ERepeatTypeId; // 重复类型
  interval: number; // 间隔
  until: number; // 结束时间
}

/** 重复选项的接口参数 */
export const repeatParamsMap: Record<ERepeatKey, IRepeatConfig | {}> = {
  [ERepeatKey.noRepeat]: {},
  [ERepeatKey.everyDay]: {
    freq: 'day',
    interval: 1, // 间隔
    until: null, // 结束日期
    every: [], // 区间
    exclude_date: [], // 排除事项日期
  },
  [ERepeatKey.everyWorkingDay]: {
    freq: 'week',
    interval: 1,
    until: null, // 永不结束
    every: [1, 2, 3, 4, 5],
    exclude_date: [], // 排除事项日期
  },
  [ERepeatKey.everyWeek]: {
    freq: 'week',
    interval: 1,
    until: null,
    every: [],
    exclude_date: [], // 排除事项日期
  },
  [ERepeatKey.everyMonth]: {
    freq: 'month',
    interval: 1,
    until: null,
    every: [],
    exclude_date: [], // 排除事项日期
  },
  [ERepeatKey.everyYear]: {
    freq: 'year',
    interval: 1,
    until: null,
    every: [],
    exclude_date: [], // 排除事项日期
  },
  [ERepeatKey.custom]: null, // 自定义
};

/**
 * 获取当前时区
 */
export const getTimezoneOffset = () => dayjs.tz.guess();
/** 工作日 */
export const WORKING_DATE_LIST = [1, 2, 3, 4, 5];

/** 修改/删除事项类型（所有事项均生效：0；仅生效当前项：1；当前项及未来事项均生效：2 */
export enum EDelAndEditType {
  all = 0,
  current = 1,
  currentAndFuture = 2,
}
