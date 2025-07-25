import dayjs from 'dayjs';

/* 头部对比时间预设 */
export enum EPreDateType {
  lastWeek = '1w',
  yesterday = '1d',
}

export enum ETypeSelect {
  compare = 'compare',
  group = 'group',
}

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
export interface IGroupByVariables {
  group_by_limit_enabled: boolean;
  limit: number;
  limit_sort_method: string;
  metric_cal_type: string;
}

export interface IGroupOption {
  checked?: boolean;
  id: string;
  name: string;
  top_limit_enable?: boolean;
}

export interface IListItem {
  id?: string;
  name?: string;
  text?: string;
  top_limit_enable?: boolean;
  value?: string;
}

const preDateTypeList = [
  {
    label: window.i18n.t('昨天'),
    value: EPreDateType.yesterday,
  },
  {
    label: window.i18n.t('上周'),
    value: EPreDateType.lastWeek,
  },
];

/**
 * @description 将 1d 10d 转换为 实际日期
 * @param t
 * @returns
 */
export function timeOffsetDateFormat(t: string) {
  if (preDateTypeList.map(item => item.value).includes(t as any)) {
    if (t === EPreDateType.yesterday) {
      return window.i18n.t('昨天');
    }
    if (t === EPreDateType.lastWeek) {
      return window.i18n.t('上周');
    }
  }
  const regex = /^(\d+)d$/; // 匹配类似 '1d', '10d' 的格式
  const match = t.match(regex);
  if (match) {
    const days = Number.parseInt(match[1], 10); // 提取天数
    const targetDate = dayjs().subtract(days, 'day'); // 当前日期减去天数
    return targetDate.format('YYYY-MM-DD'); // 格式化为 YYYY-MM-DD
  }
  return t;
}
