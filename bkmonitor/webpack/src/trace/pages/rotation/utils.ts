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
import { random } from 'lodash';

import { FixedDataModel } from './components/fixed-rotation-tab';
import { ReplaceDataModel } from './components/replace-rotation-tab';
import { ReplaceItemDataModel } from './components/replace-rotation-table-item';
import { RotationSelectTextMap, RotationSelectTypeEnum } from './typings/common';

/**
 * 以15分钟为间隔生成一天的时间段
 * @returns 时间段
 */
export function generateTimeSlots(): string[] {
  const timeSlots = [];
  let currentTime = dayjs().startOf('day');
  const endTime = dayjs().endOf('day');

  // 循环生成时间段，直到到达第二天的 00:00:00
  while (currentTime.isSameOrBefore(endTime)) {
    const formattedTime = currentTime.format('HH:mm');
    timeSlots.push(formattedTime);
    // 增加15分钟
    currentTime = currentTime.add(15, 'minutes');
  }
  return timeSlots;
}

export const colorList = [
  '#3A84FF',
  '#FF9C01',
  '#18B456',
  '#BC66E5',
  '#FF5656',
  '#699DF4',
  '#FFB848',
  '#51BE68',
  '#D493F3',
  '#FF6F6F',
  '#61B2C2',
  '#F5876C',
  '#EAD550',
  '#AEA5F2',
  '#85CCA8',
  '#FFA66B',
  '#6FBCEA',
  '#FFC685',
  '#6EDAC1',
  '#E787CB'
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

export function createColorList(num = 100) {
  const colors = [...colorList];
  for (let i = 0; i < num; i++) {
    const r = Math.floor(Math.random() * 255);
    const g = Math.floor(Math.random() * 255);
    const b = Math.floor(Math.random() * 255);
    colors.push(`rgba(${r},${g},${b},0.8)`);
  }
  return colors;
}

export function timeRangeTransform(val: string) {
  const [start, end] = val.split('--');
  return dayjs(start, 'hh:mm').isBefore(dayjs(end, 'hh:mm')) ? val : `${start} - ${window.i18n.t('次日')}${end}`;
}

/**
 * 校验固定值班单条轮值规则是否符合规范
 * @param data 轮值规则数据
 * @returns 是否符合规范
 */
export function validFixedRotationData(data: FixedDataModel) {
  if (data.users.length === 0) return { success: false, msg: window.i18n.t('轮值规则必须添加人员') };
  if (validTimeOverlap(data.workTime)) return { success: false, msg: window.i18n.t('时间段重复了') };
  return { success: true, msg: '' };
}

/**
 * 校验交替轮值单条轮值规则是否符合规范
 * @param data 轮值规则数据
 * @returns 是否符合规范
 */
export function validReplaceRotationData(data: ReplaceDataModel) {
  if (!data.users.value.some(item => item.value.length))
    return { success: false, msg: window.i18n.t('轮值规则必须添加人员') };
  const type = data.date.isCustom ? RotationSelectTypeEnum.Custom : data.date.type;
  switch (type) {
    case RotationSelectTypeEnum.Daily:
    case RotationSelectTypeEnum.WorkDay:
    case RotationSelectTypeEnum.Weekend: {
      if (data.date.value.every(item => !item.workTime.length)) {
        return { success: false, msg: window.i18n.t('轮值规则必须添加单班时间') };
      }
      break;
    }
    case RotationSelectTypeEnum.Weekly:
    case RotationSelectTypeEnum.Monthly: {
      if (data.date.workTimeType === 'time_range' && data.date.value.every(item => !item.workDays.length)) {
        return { success: false, msg: window.i18n.t('轮值规则必须添加单班时间') };
      }
      if (data.date.workTimeType === 'datetime_range' && data.date.value.every(item => !item.workTime.length)) {
        return { success: false, msg: window.i18n.t('轮值规则必须添加单班时间') };
      }
      break;
    }
  }
  if (data.date.value.some(date => validTimeOverlap(date.workTime)))
    return { success: false, msg: window.i18n.t('时间段重复了') };
  return { success: true, msg: '' };
}

/**
 * 交替轮值-接口数据和实际使用数据转化
 * @param originData 需要转化的数据
 * @param type params 实际数据转接口数据 data: 接口数据转实际数据
 * @returns 转化后的数据
 */
export function replaceRotationTransform(originData, type) {
  if (type === 'data') {
    return originData.map(data => {
      const date = data.duty_time.reduce(
        (pre: ReplaceItemDataModel['date'], cur, ind) => {
          if (ind === 0) {
            pre.isCustom = cur.is_custom || false;
            pre.type = cur.work_type;
            pre.workTimeType = cur.work_time_type || 'time_range';
            pre.customTab = cur.period_settings ? 'duration' : 'classes';
            pre.customWorkDays = cur.work_days;
            const { window_unit, duration } = cur.period_settings || {
              window_unit: 'day',
              duration: 1
            };
            pre.periodSettings = {
              unit: window_unit,
              duration
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
          customWorkDays: [],
          customTab: 'duration',
          value: []
        }
      );
      const obj: ReplaceItemDataModel = {
        id: data.id,
        date,
        users: {
          groupNumber: data.group_number,
          groupType: data.group_type,
          value: data.duty_users.map(item => ({
            key: random(8, true),
            value: item,
            orderIndex: 0
          }))
        }
      };
      return obj;
    });
  }

  const filterData = originData.filter(item => validReplaceRotationData(item).success);

  return filterData.map((item: ReplaceDataModel) => {
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
          const periodSetting =
            data.customTab === 'duration'
              ? {
                  period_settings: {
                    window_unit: unit,
                    duration
                  }
                }
              : {};
          return {
            is_custom: true,
            work_type: data.type,
            work_days: data.customWorkDays,
            work_time: item.workTime.map(val => val.join('--')),
            work_time_type: 'time_range',
            ...periodSetting
          };
        });
        break;
      }
    }

    return {
      id: item.id,
      duty_time: dutyTime,
      duty_users: item.users.value.filter(item => item.value.length).map(item => item.value),
      group_type: item.users.groupType,
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
export function fixedRotationTransform(data, type) {
  if (type === 'data')
    return data.map(item => {
      const obj: FixedDataModel = {
        id: item.id,
        key: random(8, true),
        type: item.duty_time?.[0]?.work_type || RotationSelectTypeEnum.Weekly,
        workDays: item.duty_time?.[0]?.work_days || [],
        workDateRange: [],
        workTime: (item.duty_time?.[0]?.work_time || []).map(item => item.split('--')),
        users: item.duty_users[0] || [],
        orderIndex: 0
      };
      const dateRange = item.duty_time?.[0]?.work_date_range || [];
      if (dateRange.length) {
        obj.workDateRange = dateRange[0].split('--');
      }
      return obj;
    });

  const filterData: FixedDataModel[] = data.filter(item => validFixedRotationData(item).success);

  return filterData.map(item => {
    let dutyTimeItem;
    switch (item.type) {
      case RotationSelectTypeEnum.Daily: {
        dutyTimeItem = {
          work_type: item.type,
          work_time: item.workTime.map(item => item.join('--'))
        };
        break;
      }
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
        const dateRange = item.workDateRange.map(date => dayjs(date).format('YYYY-MM-DD')).join('--');
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
  return data?.length ? `${window.i18n.t('每周')}${data.map(item => week[item]).join('、')}` : '';
}

export interface RuleDetailModel {
  ruleTime: {
    day: string;
    timer: string[];
    periodSettings: string;
  }[];
  ruleUser: { users: { type: 'group' | 'user'; display_name: string; logo: string }[]; orderIndex: number }[];
  isAuto: boolean;
  groupNumber: number;
}
export function transformRulesDetail(data: any[], type: 'handoff' | 'regular'): RuleDetailModel[] {
  let orderIndex = 0;
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
      if (time.is_custom && time.period_settings) {
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
      ruleUser: rule.duty_users.map(item => {
        const res = { users: item, orderIndex };
        // if (rule.group_type === 'specified') {
        //   orderIndex += 1;
        // } else if (item.length % rule.group_number === 0) {
        //   orderIndex += item.length / rule.group_number;
        // } else if (rule.group_number < item.length) {
        //   orderIndex += item.length;
        // } else {
        //   orderIndex += 1;
        // }
        if (rule.group_type === 'specified' || type === 'regular') {
          orderIndex += 1;
        } else {
          orderIndex += item.length;
        }
        return res;
      }),
      isAuto: rule.group_type === 'auto',
      groupNumber: rule.group_number
    };
  });
}

/**
 * 判断两个时间段是否存在重叠
 * @param start1 第一个时间段的起始时间
 * @param end1 第一个时间段的结束时间
 * @param start2 第二个时间段的起始时间
 * @param end2 第二个时间段的结束时间
 * @returns 是否存在重叠
 */
function hasOverlap(start1: number, end1: number, start2: number, end2: number) {
  return start1 < end2 && start2 < end1;
}

/**
 * 验证一组时间段是否存在重叠
 * @param list 时间段列表，每个时间段由起始时间和结束时间组成
 * @returns 是否存在重叠
 */
export function validTimeOverlap(list: string[][]) {
  const timestamps = list.map(([start, end]) => {
    const startTime = dayjs(start, 'hh:mm').valueOf();
    const isBefore = startTime < dayjs(end, 'hh:mm').valueOf();
    const endTime = dayjs(end, 'hh:mm')
      .add(isBefore ? 0 : 1, 'day')
      .valueOf();
    return { start: startTime, end: endTime };
  });

  for (let i = 0; i < timestamps.length; i++) {
    for (let j = i + 1; j < timestamps.length; j++) {
      if (hasOverlap(timestamps[i].start, timestamps[i].end, timestamps[j].start, timestamps[j].end)) {
        return true; // 发现重叠，立即返回true
      }
    }
  }

  return false; // 没有找到重叠
}
