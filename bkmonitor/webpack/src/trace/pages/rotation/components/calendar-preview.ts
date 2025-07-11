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
import { randomColor } from '../utils';

export interface ICalendarDataUser {
  color: string;
  timeRange: string[];
  users: { id: string; name: string }[];
}
interface ICalendarDataDataItem {
  // 日历表一行的数据
  users: { id: string; name: string }[]; // 用户组
  color: string; // 颜色
  range: number[]; // 宽度 此宽度最大为一周的宽度 最小为0 最大为1 例如 [0.1, 0.5]
  isStartBorder?: boolean;
  row?: number; // 第几行
  timeRange: string[]; // 时间间隔
  other: {
    time: string;
    users: string;
  }; // 其他信息
}
export interface ICalendarData {
  users: ICalendarDataUser[];
  data: {
    dates: {
      // 日历表一行的数据
      year: number;
      month: number;
      day: number;
      isOtherMonth: boolean;
      isCurDay: boolean;
    }[];
    maxRow?: number;
    data: ICalendarDataDataItem[];
  }[];
}
export function getCalendar() {
  const today = new Date(); // 获取当前日期

  const year = today.getFullYear(); // 获取当前年份
  const month = today.getMonth(); // 获取当前月份

  const firstDay = new Date(year, month, 1); // 当月第一天的日期对象
  const lastDay = new Date(year, month + 1, 0); // 当月最后一天的日期对象

  const startDate = new Date(firstDay); // 日历表开始日期，初始为当月第一天
  startDate.setDate(startDate.getDate() - startDate.getDay()); // 向前推算到周日

  const endDate = new Date(lastDay); // 日历表结束日期，初始为当月最后一天
  endDate.setDate(endDate.getDate() + (6 - endDate.getDay())); // 向后推算到周六

  // 判断是否需要添加次月初的日期
  if (endDate.getMonth() === month) {
    endDate.setMonth(month + 1, 0); // 设置为下个月的最后一天
  }

  const calendar = []; // 存放日历表的二维数组
  let week = []; // 存放一周的日期

  const currentDate = new Date(startDate); // 当前遍历的日期，初始为开始日期

  // 遍历日期范围，生成日历表
  while (currentDate <= endDate) {
    // 获取日期的年、月、日
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth();
    const currentDay = currentDate.getDate();

    // 添加日期到一周数组
    week.push({
      year: currentYear,
      month: currentMonth,
      day: currentDay,
      isOtherMonth: currentMonth !== month,
      isCurDay: currentDay === today.getDate() && currentMonth === month,
    });

    // 每周有7天，将一周的日期添加到日历表，并重置一周数组
    if (week.length === 7) {
      calendar.push(week);
      week = [];
    }

    // 增加一天
    currentDate.setDate(currentDate.getDate() + 1);
  }

  return calendar;
}

/**
 * @description 以当前周为起始周查询最近一个月的日期
 */
export function getCalendarNew() {
  const today = new Date(); // 获取当前日期
  const month = today.getMonth(); // 获取当前月份
  const min = 31; /* 最小展示天数31 */
  let startDate = new Date();
  let endDate = new Date(today.getTime() + min * 86400000);
  startDate = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() - startDate.getDay());
  endDate = new Date(endDate.getFullYear(), endDate.getMonth(), endDate.getDate() + (6 - endDate.getDay()));
  const calendar = []; // 存放日历表的二维数组
  let week = []; // 存放一周的日期

  const currentDate = new Date(startDate); // 当前遍历的日期，初始为开始日期

  // 遍历日期范围，生成日历表
  while (currentDate <= endDate) {
    // 获取日期的年、月、日
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth();
    const currentDay = currentDate.getDate();

    // 添加日期到一周数组
    week.push({
      year: currentYear,
      month: currentMonth,
      day: currentDay,
      isOtherMonth: currentMonth !== month,
      isCurDay: currentDay === today.getDate() && currentMonth === month,
    });

    // 每周有7天，将一周的日期添加到日历表，并重置一周数组
    if (week.length === 7) {
      calendar.push(week);
      week = [];
    }

    // 增加一天
    currentDate.setDate(currentDate.getDate() + 1);
  }
  return calendar;
}

/* 获取预览接口的生效时间及查询天数 */
export function getPreviewParams(effectiveTime: string) {
  const list = getCalendarNew();
  const startDate = list[0][0];
  let beginTime = `${startDate.year}-${startDate.month + 1}-${startDate.day} 00:00:00`;
  const effectiveDate = new Date(effectiveTime);
  if (effectiveDate.getTime() > new Date(beginTime).getTime()) {
    beginTime = effectiveTime;
  }
  const max = list.length * 7;
  const beginTimeDate = new Date(beginTime);
  let indexNum = 0;
  list.forEach((item, index) => {
    item.forEach((itemItem, itemIndex) => {
      if (
        beginTimeDate.getFullYear() === itemItem.year &&
        beginTimeDate.getMonth() === itemItem.month &&
        beginTimeDate.getDate() === itemItem.day
      ) {
        indexNum = index * 7 + itemIndex;
      }
    });
  });
  return {
    begin_time: beginTime,
    days: max - indexNum,
  };
}

/* 将时间戳转为字符串格式 */
function timeStampToTimeStr(num: number) {
  const date = new Date(num);
  return {
    year: date.getFullYear(),
    month: date.getMonth() + 1,
    day: date.getDate(),
    hours: date.getHours(),
    minutes: date.getMinutes(),
    seconds: date.getSeconds(),
    hoursStr: date.getHours() < 10 ? `${0}${date.getHours()}` : date.getHours(),
    minutesStr: date.getMinutes() < 10 ? `${0}${date.getMinutes()}` : date.getMinutes(),
  };
}
/* 根据时间戳段 获取百分比并输出字符串时间格式 */
export function getDateStrAndRange(timeRange: number[], totalRange: number[]) {
  const start = timeRange[0];
  const end = timeRange[1];
  const totalStart = totalRange[0];
  const totalEnd = totalRange[1];
  const range = [(start - totalStart) / (totalEnd - totalStart), (end - totalStart) / (totalEnd - totalStart)];
  const startObj = timeStampToTimeStr(start);
  const isStartBorder = startObj.hours === 0 && startObj.minutes === 0;
  const endObj = timeStampToTimeStr(end);
  const startTimeStr = `${startObj.year}-${startObj.month}-${startObj.day} ${startObj.hoursStr}:${startObj.minutesStr}`;
  const endTimeStr = `${endObj.year}-${endObj.month}-${endObj.day} ${endObj.hoursStr}:${endObj.minutesStr}`;
  const timeStr =
    startTimeStr.split(' ')[0] === endTimeStr.split(' ')[0]
      ? `${startTimeStr.split(' ')[0]} ${startTimeStr.split(' ')[1]}-${endTimeStr.split(' ')[1]}`
      : `${startTimeStr}-${endTimeStr}`;
  return {
    range,
    isStartBorder,
    timeStr,
  };
}
/**
 * @description 如有重叠区域需要展示多行
 * @param data
 * @returns
 */
function setRowYOfOverlap(data: ICalendarDataDataItem[]) {
  const result: (ICalendarDataDataItem & { timeRangeNum: number[] })[] = [];
  // data.sort((a, b) => new Date(a.timeRange[0]).getTime() - new Date(b.timeRange[0]).getTime());
  const tempData: (ICalendarDataDataItem & { timeRangeNum: number[] })[] = data.map(item => ({
    ...item,
    timeRangeNum: item.timeRange.map(t => new Date(t).getTime()),
  }));
  tempData.sort((a, b) => a.timeRangeNum[0] - b.timeRangeNum[0]);
  let maxRow = 0;
  tempData.forEach(item => {
    if (result.length) {
      for (let i = 0; i <= maxRow; i++) {
        const preItem = (JSON.parse(JSON.stringify(result)) as (ICalendarDataDataItem & { timeRangeNum: number[] })[])
          .sort((a, b) => b.timeRangeNum[1] - a.timeRangeNum[1])
          .filter(r => r.row === i)[0];
        /* 最后一夜重叠则新增maxrow */
        if (preItem.timeRangeNum[1] <= item.timeRangeNum[0]) {
          result.push({
            ...item,
            row: i,
          });
          break;
        }
        if (i === maxRow) {
          maxRow += 1;
          result.push({
            ...item,
            row: maxRow,
          });
          break;
        }
      }
    } else {
      result.push({
        ...item,
        row: 0,
      });
    }
  });
  return {
    maxRow,
    result,
  };
}
/**
 * @description 将用户组可视化
 * @param data
 */
export function calendarDataConversion(data: ICalendarData) {
  const calendarData: ICalendarData = JSON.parse(JSON.stringify(data));
  const { users } = calendarData;
  calendarData.data = calendarData.data.map(row => {
    const { dates } = row;
    const rowTotalTimeRange = [
      `${dates[0].year}-${dates[0].month + 1}-${dates[0].day} 00:00`,
      `${dates[6].year}-${dates[6].month + 1}-${dates[6].day} 23:59`,
    ];
    const temp = [];
    users.forEach(u => {
      const { timeRange } = u;
      const rowTotalTimeRangeNum = rowTotalTimeRange.map(item => new Date(item).getTime());
      const timeRangeNum = timeRange.map(item => new Date(item).getTime());
      if (timeRangeNum[0] < rowTotalTimeRangeNum[1] && timeRangeNum[1] > rowTotalTimeRangeNum[0]) {
        let tempRange = [];
        if (timeRangeNum[0] < rowTotalTimeRangeNum[0]) {
          tempRange = [rowTotalTimeRangeNum[0], timeRangeNum[1]];
        } else if (timeRangeNum[1] > rowTotalTimeRangeNum[1]) {
          tempRange = [timeRangeNum[0], rowTotalTimeRangeNum[1]];
        } else {
          tempRange = [timeRangeNum[0], timeRangeNum[1]];
        }
        const rangeStr = getDateStrAndRange(tempRange, rowTotalTimeRangeNum);
        temp.push({
          ...u,
          range: rangeStr.range,
          isStartBorder: rangeStr.isStartBorder,
          other: {
            time: rangeStr.timeStr,
            users: u.users,
          },
        });
      }
    });
    const rowData = setRowYOfOverlap(temp);
    return {
      ...row,
      maxRow: rowData.maxRow,
      data: rowData.result,
    };
  });
  return calendarData;
}

interface IDutyPlans {
  user_index?: number;
  order?: number;
  users: {
    id: string;
    display_name: string;
    type: string;
  }[];
  work_times: {
    start_time: string;
    end_time: string;
  }[];
}

export interface IDutyPreviewParams {
  rule_id: number | string;
  duty_plans: IDutyPlans[];
}

/**
 * @description 将时间段相交的区域进行合并处理
 * @param times
 */
export function timeRangeMerger(timePeriods: { start_time: string; end_time: string }[]) {
  if (!timePeriods?.length) {
    return [];
  }
  // 先对时间段按照开始时间进行排序
  timePeriods.sort((a, b) => {
    return new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
  });

  const mergedPeriods = [];
  let currentPeriod = timePeriods[0];

  for (let i = 1; i < timePeriods.length; i++) {
    const nextPeriod = timePeriods[i];

    const currentEndTime = new Date(currentPeriod.end_time);
    const nextStartTime = new Date(nextPeriod.start_time);

    if (nextStartTime.getTime() <= currentEndTime.getTime()) {
      // 时间段相交，更新当前时间段的结束时间
      currentPeriod.end_time = nextPeriod.end_time;
    } else {
      // 时间段不相交，将当前时间段加入到合并后的数组中，并更新当前时间段为下一个时间段
      mergedPeriods.push(currentPeriod);
      currentPeriod = nextPeriod;
    }
  }

  // 将最后一个时间段加入到合并后的数组中
  mergedPeriods.push(currentPeriod);
  /* 判断跨行的数据 */
  // const result = [];
  // mergedPeriods.forEach(item => {

  // });
  return mergedPeriods;
}

/**
 * @description 根据后台接口数据转换为预览数据
 * @param params
 */
export function setPreviewDataOfServer(
  params: IDutyPlans[],
  autoOrders?: { [key: number]: number },
  colorList?: string[]
) {
  const hasColorList = !!colorList;
  const data = [];
  const colorFn = (userIndex: number) => {
    if (hasColorList) {
      if (userIndex > colorList?.length - 1) {
        return randomColor(userIndex);
      }
      return colorList[userIndex];
    }
    return randomColor(userIndex);
  };
  userIndexResetOfpreviewData(params, autoOrders).forEach((item, index) => {
    const users = item.users.map(u => ({ id: u.id, name: u.display_name || u.id }));
    if (item.work_times.length) {
      timeRangeMerger(item.work_times).forEach(work => {
        data.push({
          users,
          color: colorFn(item.user_index === undefined ? index : item.user_index),
          timeRange: [work.start_time, work.end_time],
        });
      });
    }
  });
  return data;
}

/**
 * @description 重新配置user_index  以user_index + order 判断其唯一性
 * @param params
 */
export function userIndexResetOfpreviewData(params: IDutyPlans[], autoOrders?: { [key: number]: number }) {
  const userIndexCount = (all: { [key: string]: Set<number> }, curIndex, order) => {
    let count = 0;
    for (let i = 0; i < order; i++) {
      if (typeof autoOrders?.[i] !== 'undefined') {
        count += autoOrders?.[i] || 0;
      } else if (all?.[i]?.size) {
        count += Math.max(...Array.from(all[i])) + 1;
      }
    }
    return curIndex + count;
  };
  const temp: { [key: string]: Set<number> } = {};
  params.forEach(plan => {
    const o = plan?.order || 0;
    if (!temp?.[o]) {
      temp[o] = new Set();
    }
    temp[o].add(plan.user_index);
  });
  return params.map(plan => {
    return {
      ...plan,
      user_index: userIndexCount(temp, plan.user_index, plan?.order || 0),
    };
  });
}

export function getAutoOrderList(data) {
  const autoOrders: { [key: number]: number } = {};
  if (data?.category === 'handoff') {
    data?.duty_arranges?.forEach((item, index) => {
      if (item.group_type === 'auto') {
        autoOrders[index] = item.duty_users?.[0]?.length || 0;
      } else {
        autoOrders[index] = item.duty_users?.length || 0;
      }
    });
  }
  return autoOrders;
}

export function noOrderDutyData(data: IDutyPlans[]) {
  return data.map(item => ({
    ...item,
    order: 0,
  }));
}
