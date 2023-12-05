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

import { timeRangeMerger } from '../../../../trace/pages/rotation/components/calendar-preview';
import { randomColor } from '../duty-arranges/color';

import { IDutyItem } from './typing';

interface IOverlapTimesItem {
  verticalRange: number[];
  range: {
    timeStr: string;
    tempRange: number[];
    range: number[];
  };
}

interface IDutyDataRangeItem {
  users: { id: string; name: string }[]; // 用户组
  color: string; // 颜色
  range: number[]; // 宽度 此宽度最大为一周的宽度 最小为0 最大为1 例如 [0.1, 0.5]
  timeRange: string[];
  isStartBorder?: boolean; // 起点是否覆盖了边框
  row?: number;
  other: {
    time: string;
    users: string;
  }; // 其他信息
}

export interface IDutyData {
  dates: {
    year: number;
    month: number;
    day: number;
  }[];
  data: {
    id: string;
    name: string;
    maxRow?: number;
    data: IDutyDataRangeItem[];
  }[];
  freeTimes: {
    range: number[];
    timeStr: string;
  }[]; // 空闲时间
  overlapTimes: IOverlapTimesItem[]; // 重叠时间
}

export function getCalendarOfNum(num = 7, preDay?: number) {
  let today = new Date();
  if (preDay) {
    today = new Date(preDay + 24 * 60 * 60 * 1000);
  }
  const days = [];
  for (let i = 0; i < num; i++) {
    const day = new Date(today.getTime() + i * 24 * 60 * 60 * 1000);
    days.push(day);
  }
  return days.map((item: Date) => ({
    year: item.getFullYear(),
    month: item.getMonth() + 1,
    day: item.getDate()
  }));
}
/* 时间点刚好至每天的间隔则-1 */
/* 将字符串格式的时间段转为为百分比 */
export function getTimeRangeToPercent(timeRange: string[], totalRange: string[]) {
  const startObj = new Date(timeRange[0]);
  const isStartBorder = startObj.getHours() === 0 && startObj.getMinutes() === 0;
  const start = startObj.getTime() / 1000;
  const end = new Date(timeRange[1]).getTime() / 1000;
  const totalStart = new Date(totalRange[0]).getTime() / 1000;
  const totalEnd = new Date(totalRange[1]).getTime() / 1000;
  const totleLen = totalEnd - totalStart;
  const startPoint = (() => {
    if (start - totalStart <= 0) {
      return 0;
    }
    if (start > totalEnd) {
      return totleLen;
    }
    return start - totalStart;
  })();
  const endPoint = (() => {
    if (end - totalStart <= 0) {
      return 0;
    }
    if (end > totalEnd) {
      return totleLen;
    }
    return end - totalStart;
  })();
  return {
    isStartBorder: isStartBorder || startPoint === 0,
    range: [startPoint / totleLen, endPoint / totleLen]
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
    minutesStr: date.getMinutes() < 10 ? `${0}${date.getMinutes()}` : date.getMinutes()
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
  const endObj = timeStampToTimeStr(end);
  const startTimeStr = `${startObj.year}-${startObj.month}-${startObj.day} ${startObj.hoursStr}:${startObj.minutesStr}`;
  const endTimeStr = `${endObj.year}-${endObj.month}-${endObj.day} ${endObj.hoursStr}:${endObj.minutesStr}`;
  const timeStr =
    startTimeStr.split(' ')[0] === endTimeStr.split(' ')[0]
      ? `${startTimeStr.split(' ')[0]} ${startTimeStr.split(' ')[1]}-${endTimeStr.split(' ')[1]}`
      : `${startTimeStr}-${endTimeStr}`;
  return {
    range,
    timeStr
  };
}

/**
 * @description 获取所有空闲时间段
 * @param timeRanges
 * @param totalRange
 * @returns
 */
function getFreeTimeRanges(timeRanges: string[][], totalRange: string[]) {
  const freeTimes = [];
  const totalRangeTime = totalRange.map(item => new Date(item).getTime());
  const allRangeTime: number[][] = JSON.parse(
    JSON.stringify(
      timeRanges
        .filter(item => new Date(item[1]).getTime() > totalRangeTime[0])
        .map(item => {
          let start = new Date(item[0]).getTime();
          const end = new Date(item[1]).getTime();
          if (start < totalRangeTime[0]) {
            // eslint-disable-next-line prefer-destructuring
            start = totalRangeTime[0];
          }
          return [start, end];
        })
    )
  );
  allRangeTime.sort((a, b) => (a[0] === b[0] ? a[1] - b[1] : a[0] - b[0]));

  allRangeTime.reduce((acc: number[], cur: number[], index: number) => {
    const next = allRangeTime[index + 1];
    if (acc) {
      if (cur[0] > totalRangeTime[0]) {
        if (acc[0] > totalRangeTime[1]) {
          return cur;
        }
        if (cur[1] < acc[1] && acc[1] < totalRangeTime[1] && !next) {
          freeTimes.push([acc[1], totalRangeTime[1]]);
          return cur;
        }
        if (cur[1] < acc[1]) {
          return acc;
        }
        if (cur[0] > acc[1]) {
          if (acc[1] < totalRangeTime[0]) {
            freeTimes.push([totalRangeTime[0], cur[0]]);
          } else {
            if (cur[0] > totalRangeTime[1]) {
              freeTimes.push([acc[1], totalRangeTime[1]]);
            } else {
              freeTimes.push([acc[1], cur[0]]);
            }
          }
        }
        if (!next) {
          /* 如果当前为最后一个 */
          if (cur[1] < totalRangeTime[1]) {
            freeTimes.push([cur[1], totalRangeTime[1]]);
          }
        }
      } else if (!next) {
        if (cur[1] > totalRangeTime[0]) {
          freeTimes.push(cur[1], totalRangeTime[1]);
        } else {
          freeTimes.push([totalRangeTime[0], totalRangeTime[1]]);
        }
      }
    } else {
      if (cur[0] > totalRangeTime[0]) {
        if (cur[0] > totalRangeTime[1]) {
          freeTimes.push([totalRangeTime[0], totalRangeTime[1]]);
        } else {
          freeTimes.push([totalRangeTime[0], cur[0]]);
          if (allRangeTime.length === 1 && cur[1] < totalRangeTime[1]) {
            freeTimes.push([cur[0], totalRangeTime[1]]);
          }
        }
      }
    }
    return cur;
  }, false as any);
  if (!allRangeTime.length && !freeTimes.length) {
    freeTimes.push(totalRangeTime);
  }
  return freeTimes
    .filter(t => t[0] < totalRangeTime[1] && t[1] - t[0] !== 60000)
    .map(t => getDateStrAndRange(t, totalRangeTime));
}

/**
 * 获取多条时间段的重合区域
 * @param timeRnages
 * @returns
 */
export function getOverlap(timeRnages: number[][]) {
  let overlapStart = -Infinity;
  let overlapEnd = Infinity;

  timeRnages.forEach(item => {
    overlapStart = Math.max(overlapStart, item[0]);
    overlapEnd = Math.min(overlapEnd, item[1]);
  });
  if (overlapStart <= overlapEnd) {
    return [overlapStart, overlapEnd];
  }
  return [0, 0]; // 无重叠
}
/**
 * @description 合并精简重叠区域
 * @param timerRanges
 */
function mergeOverlaps(overlaps: number[][]) {
  overlaps.sort((a, b) => a[0] - b[0]);
  const result = [overlaps[0]];
  let currentOverlap = result[0];
  for (let i = 1; i < overlaps.length; i++) {
    const overlap = overlaps[i];

    if (overlap[0] <= currentOverlap[1]) {
      currentOverlap[1] = Math.max(currentOverlap[1], overlap[1]);
    } else {
      result.push(overlap);
      currentOverlap = overlap;
    }
  }
  return result.filter(r => !!r);
}
/**
 * @description 获取多条时间段的重合区域 需要进行两两重合并且将重合区域进行合并精简
 * @param timeRnages
 */
function getOverlapTowByTow(timeRanges: number[][][]) {
  const overlaps = [];
  timeRanges[0].forEach(timeRange1 => {
    timeRanges[1].forEach(timeRange2 => {
      const start = Math.max(timeRange1[0], timeRange2[0]);
      const end = Math.min(timeRange1[1], timeRange2[1]);
      if (start <= end) {
        overlaps.push([start, end]);
      }
    });
  });
  return mergeOverlaps(overlaps);
}
/**
 * @description 计算重叠区域
 * @param timeRanges
 * @param totalRange
 * @returns
 */
function getOverlapTimeRanges(timeRanges: string[][][], totalRange: string[]) {
  const overlapTimes: IOverlapTimesItem[] = [];
  const totalRangeTime = totalRange.map(item => new Date(item).getTime());
  for (let i = 0; i < timeRanges.length; i++) {
    for (let j = i + 1; j < timeRanges.length; j++) {
      // 两两对比
      const curTimeRanges = JSON.parse(
        JSON.stringify(timeRanges[i].map(item => [new Date(item[0]).getTime(), new Date(item[1]).getTime()]))
      ) as number[][];
      const nextTimeRanges = JSON.parse(
        JSON.stringify(timeRanges[j].map(item => [new Date(item[0]).getTime(), new Date(item[1]).getTime()]))
      ) as number[][];
      const ranges = getOverlapTowByTow([curTimeRanges, nextTimeRanges]);
      ranges.forEach(range => {
        let tempRange = range;
        if (tempRange[1] > totalRangeTime[0] && tempRange[0] < totalRangeTime[1]) {
          if (tempRange[0] < totalRangeTime[0]) {
            tempRange = [totalRangeTime[0], range[1]];
          } else if (tempRange[1] > totalRangeTime[1]) {
            tempRange = [tempRange[0], totalRangeTime[1]];
          }
          if (tempRange[0] !== tempRange[1]) {
            overlapTimes.push({
              verticalRange: [i, j],
              range: {
                ...getDateStrAndRange(tempRange, totalRangeTime),
                tempRange
              }
            });
          }
        }
      });
    }
  }
  // 将重复的区间进行精简
  const resultOverlapTimes: IOverlapTimesItem[] = [];
  const groupsObj = {};
  overlapTimes.sort((a, b) => a.range.tempRange[0] - b.range.tempRange[0]);
  overlapTimes.forEach(item => {
    const key = JSON.stringify(item.range.tempRange);
    if (!groupsObj[key]) {
      groupsObj[key] = [];
    }
    groupsObj[key].push(item);
  });
  Object.keys(groupsObj).forEach(key => {
    const group: IOverlapTimesItem[] = groupsObj[key];
    if (group.length > 1) {
      group.sort((a, b) => a.verticalRange[0] - b.verticalRange[0]);
      group.sort((a, b) => a.verticalRange[1] - a.verticalRange[0] - (b.verticalRange[1] - b.verticalRange[0]));
      const temp: IOverlapTimesItem[] = [];
      group.forEach(g => {
        const isNeed = () =>
          !resultOverlapTimes.filter(
            r =>
              g.verticalRange[0] >= r.verticalRange[0] &&
              g.verticalRange[1] <= r.verticalRange[1] &&
              g.range.tempRange[0] >= r.range.tempRange[0] &&
              g.range.tempRange[1] <= r.range.tempRange[1]
          ).length;
        if (temp.length) {
          const pre = temp[temp.length - 1];
          if (g.verticalRange[0] >= pre.verticalRange[1]) {
            if (isNeed()) {
              temp.push(g);
            }
          }
        } else {
          if (isNeed()) {
            temp.push(g);
          }
        }
      });
      resultOverlapTimes.push(...temp);
    } else {
      resultOverlapTimes.push(group[0]);
    }
  });
  /* 合并 */
  // resultOverlapTimes.sort((a, b) => {
  //   return a.range.tempRange[0] - b.range.tempRange[0];
  // });
  // interface ItotalTemp {
  //   tempRange: number[];
  //   verticalRange: number[];
  // }
  // const tempResult: ItotalTemp[] = [];
  // let totalTemp: ItotalTemp = null;
  // resultOverlapTimes.length &&
  //   resultOverlapTimes.reduce((pre, cur, curIndex) => {
  //     if (!totalTemp) {
  //       totalTemp = {
  //         tempRange: pre.range.tempRange,
  //         verticalRange: pre.verticalRange
  //       };
  //     }
  //     if (cur.range.tempRange[0] <= totalTemp.tempRange[1]) {
  //       totalTemp.tempRange[1] =
  //         totalTemp.tempRange[1] > cur.range.tempRange[1] ? totalTemp.tempRange[1] : cur.range.tempRange[1];
  //       totalTemp.verticalRange[0] =
  //         totalTemp.verticalRange[0] < cur.verticalRange[0] ? totalTemp.verticalRange[0] : cur.verticalRange[0];
  //       totalTemp.verticalRange[1] =
  //         totalTemp.verticalRange[1] > cur.verticalRange[1] ? totalTemp.verticalRange[1] : cur.verticalRange[1];
  //     } else {
  //       tempResult.push(totalTemp);
  //       totalTemp = null;
  //     }
  //     /* 最后一个 */
  //     if (curIndex === resultOverlapTimes.length - 1) {
  //       if (totalTemp) {
  //         tempResult.push(totalTemp);
  //         totalTemp = null;
  //       } else {
  //         totalTemp = {
  //           tempRange: cur.range.tempRange,
  //           verticalRange: cur.verticalRange
  //         };
  //         tempResult.push(totalTemp);
  //       }
  //     }
  //     return cur;
  //   });
  // const result = tempResult.map(item => ({
  //   verticalRange: item.verticalRange,
  //   range: {
  //     ...getDateStrAndRange(item.tempRange, totalRangeTime),
  //     tempRange: item.tempRange
  //   }
  // }));
  return resultOverlapTimes;
}

function setRowYOfOverlap(data: IDutyDataRangeItem[]) {
  const result: (IDutyDataRangeItem & { timeRangeNum: number[] })[] = [];
  const tempData: (IDutyDataRangeItem & { timeRangeNum: number[] })[] = data.map(item => ({
    ...item,
    timeRangeNum: item.timeRange.map(t => new Date(t).getTime())
  }));
  tempData.sort((a, b) => a.timeRangeNum[0] - b.timeRangeNum[0]);
  let maxRow = 0;
  tempData.forEach(item => {
    if (result.length) {
      for (let i = 0; i <= maxRow; i++) {
        const preItem = (JSON.parse(JSON.stringify(result)) as (IDutyDataRangeItem & { timeRangeNum: number[] })[])
          .sort((a, b) => b.timeRangeNum[1] - a.timeRangeNum[1])
          .filter(r => r.row === i)[0];
        /* 最后一夜重叠则新增maxrow */
        if (preItem.timeRangeNum[1] <= item.timeRangeNum[0]) {
          result.push({
            ...item,
            row: i
          });
          break;
        }
        if (i === maxRow) {
          maxRow += 1;
          result.push({
            ...item,
            row: maxRow
          });
          break;
        }
      }
    } else {
      result.push({
        ...item,
        row: 0
      });
    }
  });
  return {
    maxRow,
    result
  };
}

/**
 * @description 将用户组时间段可视化
 * @param dutyData
 * @returns
 */
export function dutyDataConversion(dutyData: IDutyData) {
  const dutyDataTemp = JSON.parse(JSON.stringify(dutyData)) as IDutyData;
  const { dates } = dutyData;
  const totalTimeRange = [
    `${dates[0].year}-${dates[0].month}-${dates[0].day} 00:00`,
    `${dates[6].year}-${dates[6].month}-${dates[6].day} 23:59`
  ];
  /* 所有用户组范围 */
  const allTimeRange = [];
  const allTimeRanges = [];
  /* 将字符串时间转转换为百分比 */
  dutyDataTemp.data = dutyDataTemp.data.map(item => {
    allTimeRanges.push(item.data.map(d => d.timeRange));
    const data = item.data.map(d => {
      const { timeRange } = d;
      const rangeObj = getTimeRangeToPercent(timeRange, totalTimeRange);
      const { other } = d;
      const start = timeRange[0].split(' ')[1];
      const end = timeRange[1].split(' ')[1];
      other.time = (() => {
        if (
          new Date(timeRange[1].split(' ')[0]).getTime() - new Date(timeRange[0].split(' ')[0]).getTime() >
          60000 * 24 * 60
        ) {
          return `${timeRange[0].split(' ')[0]} ${start}- ${timeRange[1].split(' ')[0]} ${end}`;
        }
        return `${timeRange[0].split(' ')[0]} ${start}-${end}`;
      })();
      allTimeRange.push(d.timeRange);
      return {
        ...d,
        isStartBorder: rangeObj.isStartBorder,
        range: rangeObj.range,
        other
      };
    });
    const obj = setRowYOfOverlap(data.filter(d => d.range[1] - d.range[0] !== 0));
    return {
      ...item,
      maxRow: obj.maxRow,
      data: obj.result
    };
  });
  /* 计算空闲时间 */
  dutyDataTemp.freeTimes = getFreeTimeRanges(allTimeRange, totalTimeRange);
  /* 计算重叠区域 */
  dutyDataTemp.overlapTimes = getOverlapTimeRanges(allTimeRanges, totalTimeRange);
  return dutyDataTemp;
}

interface IDutyPlans {
  users: {
    id: string;
    display_name: string;
    type: string;
  }[];
  user_index?: number;
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
 * @description 将接口的预览数据转为组件数据
 * @param params
 * @param ids
 */
export function setPreviewDataOfServer(params: IDutyPreviewParams[], dutyList: IDutyItem[]) {
  const data = dutyList.map(item => ({
    id: item.id,
    name: item.name,
    data: []
  }));
  uniqueByDutyUsers(params).forEach(item => {
    const id = item.rule_id;
    const dataItem = data.find(d => d.id === id);
    item.duty_plans.forEach((plans, pIndex) => {
      const users = plans.users.map(u => ({ id: u.id, name: u.display_name || u.id }));
      const userStr = users.map(u => `${u.id}(${u.name})`).join(', ');
      timeRangeMerger(plans.work_times).forEach(w => {
        dataItem.data.push({
          users,
          color: randomColor(plans.user_index === undefined ? pIndex : plans.user_index),
          timeRange: [w.start_time, w.end_time],
          other: {
            time: '',
            users: userStr
          }
        });
      });
    });
  });
  return data;
}

/**
 * @description 去重
 * @param data
 * @returns
 */
function uniqueByDutyUsers(data: IDutyPreviewParams[]) {
  const result = [];
  data.forEach(item => {
    const maps = new Map<string | number, Set<string>>();
    const dutyPlans = item.duty_plans.map(duty => {
      if (!maps.has(duty.user_index)) {
        maps.set(duty.user_index, new Set());
      }
      const workTimes = [];
      duty.work_times.forEach(time => {
        const timeStr = `${time.start_time}-${time.end_time}`;
        if (!maps.get(duty.user_index).has(timeStr)) {
          workTimes.push(time);
        }
        maps.get(duty.user_index).add(timeStr);
      });
      return {
        ...duty,
        work_times: workTimes
      };
    });
    result.push({
      ...item,
      duty_plans: dutyPlans
    });
  });
  return result;
}

interface IDutyPlansItem {
  users: { display_name: string }[];
  work_times: { end_time: string; start_time: string }[];
}
export function getDutyPlansDetails(data: IDutyPlansItem[], isHistory: boolean) {
  const result: { startTime: string; endTime: string; users: string }[] = [];
  const sets = new Set();
  data.forEach(item => {
    const usersStr = (item.users?.map(u => u.display_name) || []).join('、 ');
    item.work_times.forEach(time => {
      const timeStr = `${time.start_time}-${time.end_time}`;
      if (!sets.has(`${usersStr}--${timeStr}`)) {
        result.push({
          startTime: time.start_time || '--',
          endTime: time.end_time || '--',
          users: usersStr
        });
      }
      sets.add(`${usersStr}--${timeStr}`);
    });
  });
  if (isHistory) {
    return result
      .filter(d => new Date(d.startTime).getTime() < new Date().getTime())
      .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());
  }
  return result
    .filter(d => new Date(d.endTime).getTime() > new Date().getTime())
    .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime());
}
