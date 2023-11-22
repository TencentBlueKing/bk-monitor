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
import { random } from 'lodash';
import moment from 'moment';

import { FixedDataModel } from './components/fixed-rotation-tab';
import { ItemDataModel } from './components/replace-rotation-tab';
import { ReplaceItemDataModel } from './components/replace-rotation-table-item';
import { RotationSelectTextMap, RotationSelectTypeEnum } from './typings/common';

/**
 * 以15分钟为间隔生成一天的时间段
 * @returns 时间段
 */
export function generateTimeSlots(): string[] {
  const timeSlots = [];
  const currentTime = moment().startOf('day');
  const endTime = moment().endOf('day');

  // 循环生成时间段，直到到达第二天的 00:00:00
  while (currentTime.isSameOrBefore(endTime)) {
    const formattedTime = currentTime.format('HH:mm');
    timeSlots.push(formattedTime);
    // 增加15分钟
    currentTime.add(15, 'minutes');
  }
  return timeSlots;
}

export const colorList = [
  '#4152a3',
  '#699df4',
  '#74c2a8',
  '#b5cc8e',
  '#ebd57f',
  '#f0ad69',
  '#d66f6b',
  '#e0abc9',
  '#a596eb'
];

export const randomColor = (index: number) => {
  if (index <= colorList.length - 1) {
    return colorList[index];
  }
  const r = Math.floor(Math.random() * 255);
  const g = Math.floor(Math.random() * 255);
  const b = Math.floor(Math.random() * 255);
  return `rgba(${r},${g},${b},0.8)`;
};

export function timeRangeTransform(val: string) {
  const [start, end] = val.split('--');
  return moment(start, 'hh:mm').isBefore(moment(end, 'hh:mm')) ? val : `${start} - ${window.i18n.t('次日')}${end}`;
}

/**
 * 交替轮值-接口数据和实际使用数据转化
 * @param originData 需要转化的数据
 * @param type params 实际数据转接口数据 data: 接口数据转实际数据
 * @returns 转化后的数据
 */
export function replaceRotationTransform(originData, type) {
  if (type === 'data') {
    let id;
    let userGroupType;
    const res = originData.map(data => {
      id = data.id;
      userGroupType = data.group_type;
      const date = data.duty_time.reduce(
        (pre: ReplaceItemDataModel['date'], cur, ind) => {
          if (ind === 0) {
            pre.isCustom = cur.is_custom || false;
            pre.type = cur.work_type;
            pre.workTimeType = cur.work_time_type || 'time_range';
            pre.customTab = data.duty_time.length > 1 ? 'classes' : 'duration';
            pre.customWorkDays = cur.work_days;
            pre.periodSettings = cur.period_settings || {
              unit: 'day',
              duration: 1
            };
          }
          const time = cur.work_time.map(item => item.split('--'));
          switch (cur.work_type) {
            case RotationSelectTypeEnum.Daily:
            case RotationSelectTypeEnum.WorkDay:
            case RotationSelectTypeEnum.Weekend: {
              pre.value.push({ key: random(8, true), workTime: time, workDays: cur.work_days });
              break;
            }
            case RotationSelectTypeEnum.Weekly:
            case RotationSelectTypeEnum.Monthly: {
              if (pre.workTimeType === 'time_range') {
                pre.value.push({
                  key: random(8, true),
                  workDays: cur.work_days,
                  workTime: time
                });
              } else {
                pre.value.push({
                  key: random(8, true),
                  workTime: cur.work_time.map(item => item.split('--').map(item => item.split(' ')))[0] || []
                });
              }
              break;
            }
            case RotationSelectTypeEnum.Custom: {
              pre.value.push({
                key: random(8, true),
                workTime: time
              });
            }
          }
          return pre;
        },
        {
          type: RotationSelectTypeEnum.WorkDay,
          workTimeType: 'time_range',
          isCustom: false,
          customTab: 'duration',
          value: []
        }
      );
      const obj: ReplaceItemDataModel = {
        id: data.id,
        date,
        users: {
          type: data.group_type,
          groupNumber: data.group_number,
          value: data.duty_users.map(item => ({
            key: random(8, true),
            value: item
          }))
        }
      };
      return obj;
    });
    return {
      id,
      userGroupType,
      data: res
    };
  }

  return originData.data.map((item: ItemDataModel) => {
    const data = item.date;
    const rotationType: RotationSelectTypeEnum = data.isCustom ? RotationSelectTypeEnum.Custom : data.type;
    let dutyTime = [];
    switch (rotationType) {
      case RotationSelectTypeEnum.Daily:
      case RotationSelectTypeEnum.Weekend:
      case RotationSelectTypeEnum.WorkDay: {
        dutyTime = data.value
          .map(item => ({
            work_type: data.type,
            work_time: item.workTime.map(val => val.join('--')),
            work_days: item.workDays,
            work_time_type: 'time_range'
          }))
          .filter(item => item.work_time.length);
        break;
      }
      case RotationSelectTypeEnum.Weekly:
      case RotationSelectTypeEnum.Monthly: {
        if (data.workTimeType === 'time_range') {
          dutyTime = data.value
            .map(item => ({
              work_type: data.type,
              work_time_type: data.workTimeType,
              work_days: item.workDays,
              work_time: item.workTime.map(val => val.join('--'))
            }))
            .filter(item => item.work_days.length);
        } else {
          dutyTime = data.value
            .map(item => ({
              work_type: data.type,
              work_time_type: data.workTimeType,
              work_days: item.workDays,
              work_time: [item.workTime.length && item.workTime.map(item => item.join(' ')).join('--')]
            }))
            .filter(item => item.work_time.length);
        }
        break;
      }
      case RotationSelectTypeEnum.Custom: {
        dutyTime = data.value.map(item => {
          const { unit, duration } = data.periodSettings;
          return {
            is_custom: true,
            work_type: data.type,
            work_days: data.customWorkDays,
            work_time: item.workTime.map(val => val.join('--')),
            work_time_type: 'time_range',
            period_settings: {
              window_unit: unit,
              duration
            }
          };
        });
        break;
      }
    }

    return {
      id: item.id,
      duty_time: dutyTime,
      duty_users: item.users.value.filter(item => item.value.length).map(item => item.value),
      group_type: item.users.type,
      group_number: item.users.groupNumber
    };
  });
}

/**
 * 固定值班-接口数据和实际使用数据转化
 * @param data 需要转化的数据
 * @param type params 实际数据转接口数据 data: 接口数据转实际数据
 * @returns 转化后的数据
 */
export function fixedRotationTransform<T extends 'params' | 'data'>(
  data: T extends 'data' ? any : FixedDataModel[],
  type: T
): T extends 'data' ? FixedDataModel[] : any {
  if (type === 'data')
    return data.map(item => {
      const obj: FixedDataModel = {
        id: item.id,
        key: random(8, true),
        type: item.duty_time?.[0]?.work_type || RotationSelectTypeEnum.Weekly,
        workDays: item.duty_time?.[0]?.work_days || [],
        workDateRange: [],
        workTime: (item.duty_time?.[0]?.work_time || []).map(item => item.split('--')),
        users: item.duty_users[0] || []
      };
      const dateRange = item.duty_time?.[0]?.work_date_range || [];
      if (dateRange.length) {
        obj.workDateRange = dateRange[0].split('--');
      }
      return obj;
    });

  return data.map((item: FixedDataModel) => {
    let dutyTimeItem;
    switch (item.type) {
      case RotationSelectTypeEnum.Weekly:
      case RotationSelectTypeEnum.Monthly: {
        dutyTimeItem = {
          work_type: item.type,
          work_days: item.workDays,
          work_time: item.workTime.map(item => item.join('--'))
        };
        break;
      }
      case RotationSelectTypeEnum.DateRange: {
        const dateRange = item.workDateRange.map(date => moment(date).format('YYYY-MM-DD')).join('--');
        dutyTimeItem = {
          work_type: item.type,
          work_date_range: dateRange ? [dateRange] : [],
          work_time: item.workTime.map(item => item.join('--')),
          work_time_type: 'time_range'
        };
        break;
      }
    }
    const obj = {
      id: item.id,
      duty_time: [dutyTimeItem],
      duty_users: item.users.length ? [item.users] : []
    };
    return obj;
  });
}

/**
 * 根据值，展示值所对应的星期名
 * @param data 值
 * @returns 星期名
 */
export function transformWeeklyName(data: number[]) {
  const week = [
    '',
    window.i18n.t('一'),
    window.i18n.t('二'),
    window.i18n.t('三'),
    window.i18n.t('四'),
    window.i18n.t('五'),
    window.i18n.t('六'),
    window.i18n.t('日')
  ];
  return data.length ? `${window.i18n.t('每周')}${data.map(item => week[item]).join('、')}` : '';
}

export interface RuleDetailModel {
  ruleTime: {
    day: string;
    timer: string[];
    periodSettings: string;
  }[];
  ruleUser: { type: 'group' | 'user'; display_name: string; logo: string }[][];
}
export function transformRulesDetail(data: any[]): RuleDetailModel[] {
  return data.map(rule => {
    const ruleTime = rule.duty_time.map(time => {
      let day = RotationSelectTextMap[time.work_type];
      switch (time.work_type) {
        case RotationSelectTypeEnum.Weekly:
          day = transformWeeklyName(time.work_days);
          break;
        case RotationSelectTypeEnum.Monthly:
          day = time.work_days.length ? `${window.i18n.t('每月')}${time.work_days.join('、')}` : '';
          break;
      }

      let periodSettings = '';
      if (time.is_custom && rule.duty_time.length > 1) {
        const { duration, window_unit } = time.period_settings;
        periodSettings = window.i18n.t('单班 {num} {type}', {
          num: duration,
          type: window.i18n.t(window_unit === 'day' ? '天' : '小时')
        });
      }

      return {
        day,
        timer: time.work_time,
        periodSettings
      };
    });
    return {
      ruleTime,
      ruleUser: rule.duty_users
    };
  });
}
