/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import _dropWhile from 'lodash/dropWhile';
import _round from 'lodash/round';

import { toFloatPrecision } from './number';

const TODAY = 'Today';
const YESTERDAY = 'Yesterday';

export const STANDARD_DATE_FORMAT = 'YYYY-MM-DD';
export const STANDARD_TIME_FORMAT = 'HH:mm';
export const STANDARD_TIME_MS_FORMAT = 'HH:mm:ss.SSS';
export const STANDARD_DATETIME_FORMAT = 'MMMM D YYYY, HH:mm:ss.SSS';
export const ONE_MILLISECOND = 1000;
export const ONE_SECOND = 1000 * ONE_MILLISECOND;
export const ONE_MINUTE = 60 * ONE_SECOND;
export const ONE_HOUR = 60 * ONE_MINUTE;
export const ONE_DAY = 24 * ONE_HOUR;
export const DEFAULT_MS_PRECISION = Math.log10(ONE_MILLISECOND);

const UNIT_STEPS: { microseconds: number; ofPrevious: number; unit: string }[] = [
  { unit: 'd', microseconds: ONE_DAY, ofPrevious: 24 },
  { unit: 'h', microseconds: ONE_HOUR, ofPrevious: 60 },
  { unit: 'm', microseconds: ONE_MINUTE, ofPrevious: 60 },
  { unit: 's', microseconds: ONE_SECOND, ofPrevious: 1000 },
  { unit: 'ms', microseconds: ONE_MILLISECOND, ofPrevious: 1000 },
  { unit: 'μs', microseconds: 1, ofPrevious: 1000 },
];

const timeUnitToShortTermMapper = {
  milliseconds: 'ms',
  seconds: 's',
  minutes: 'm',
  hours: 'h',
  days: 'd',
};

/**
 * @param {number} timestamp
 * @param {number} initialTimestamp
 * @param {number} totalDuration
 * @return {number} 0-100 percentage
 */
export function getPercentageOfDuration(duration: number, totalDuration: number) {
  return (duration / totalDuration) * 100;
}

const quantizeDuration = (duration: number, floatPrecision: number, conversionFactor: number) =>
  toFloatPrecision(duration / conversionFactor, floatPrecision) * conversionFactor;

export function customFormatTime(duration: number, format = 'HH:mm') {
  return dayjs.tz(duration / ONE_MILLISECOND).format(format);
}
/**
 * @param {number} duration (in microseconds)
 * @return {string} formatted, unit-labelled string with time in milliseconds
 */
export function formatDate(duration: number) {
  return dayjs.tz(duration / ONE_MILLISECOND).format(STANDARD_DATE_FORMAT);
}

/**
 * @param {number} duration (in microseconds)
 * @return {string} formatted, unit-labelled string with time in milliseconds
 */
export function formatDatetime(duration: number) {
  return dayjs.tz(duration / ONE_MILLISECOND).format(STANDARD_DATETIME_FORMAT);
}

/**
 * Humanizes the duration for display.
 *
 * Example:
 * 5000ms => 5s
 * 1000μs => 1ms
 * 183840s => 2d 3h
 *
 * @param {number} duration (in microseconds)
 * @param {string} split 分隔符
 * @param {number} precision 精度
 * @return {string} formatted duration
 */
export function formatDuration(duration: number, split = '', precision = 2): string {
  // Drop all units that are too large except the last one
  const [primaryUnit, secondaryUnit] = _dropWhile(
    UNIT_STEPS,
    ({ microseconds }, index) => index < UNIT_STEPS.length - 1 && microseconds > duration
  );

  if (primaryUnit.ofPrevious === 1000) {
    // If the unit is decimal based, display as a decimal
    return `${_round(duration / primaryUnit.microseconds, precision)}${split}${primaryUnit.unit}`;
  }

  const primaryValue = Math.floor(duration / primaryUnit.microseconds);
  const remainingMicroseconds = duration % primaryUnit.microseconds;
  const secondaryValue = Math.round(remainingMicroseconds / secondaryUnit.microseconds);

  // If secondaryValue equals primaryUnit.ofPrevious, it means we should carry over
  if (secondaryValue >= primaryUnit.ofPrevious) {
    return `${primaryValue + 1}${split}${primaryUnit.unit}`;
  }

  const primaryUnitString = `${primaryValue}${split}${primaryUnit.unit}`;
  const secondaryUnitString = `${secondaryValue}${split}${secondaryUnit.unit}`;
  return secondaryValue === 0 ? primaryUnitString : `${primaryUnitString} ${secondaryUnitString}`;
}

export function formatDurationWithUnit(duration: number, split = '') {
  const units = _dropWhile(
    UNIT_STEPS,
    ({ microseconds }, index) => index < UNIT_STEPS.length - 1 && microseconds > duration
  );
  if (duration === 0) return '0μs';
  let remainingMicroseconds = duration;
  const durationUnits = units.reduce((pre, cur) => {
    if (remainingMicroseconds >= cur.microseconds) {
      const primaryValue = Math.floor(remainingMicroseconds / cur.microseconds);
      remainingMicroseconds = remainingMicroseconds % cur.microseconds;
      pre.push(`${primaryValue}${cur.unit}`);
    }
    return pre;
  }, []);
  return durationUnits.join(split);
}

/**
 * @param {number} duration (in microseconds)
 * @return {string} formatted, unit-labelled string with time in milliseconds
 */
export function formatMillisecondTime(duration: number) {
  const targetDuration = quantizeDuration(duration, DEFAULT_MS_PRECISION, ONE_MILLISECOND);
  return `${dayjs.duration(targetDuration / ONE_MILLISECOND).asMilliseconds()}ms`;
}

export function formatRelativeDate(value: any, fullMonthName = false) {
  const m = dayjs.isDayjs(value) ? value : dayjs.tz(value);
  const monthFormat = fullMonthName ? 'MMMM' : 'MMM';
  const dt = new Date();
  if (dt.getFullYear() !== m.year()) {
    return m.format(`${monthFormat} D, YYYY`);
  }
  const mMonth = m.month();
  const mDate = m.date();
  const date = dt.getDate();
  if (mMonth === dt.getMonth() && mDate === date) {
    return TODAY;
  }
  dt.setDate(date - 1);
  if (mMonth === dt.getMonth() && mDate === dt.getDate()) {
    return YESTERDAY;
  }
  return m.format(`${monthFormat} D`);
}

/**
 * @param {number} duration (in microseconds)
 * @return {string} formatted, unit-labelled string with time in seconds
 */
export function formatSecondTime(duration: number) {
  const targetDuration = quantizeDuration(duration, DEFAULT_MS_PRECISION, ONE_SECOND);
  return `${dayjs.duration(targetDuration / ONE_MILLISECOND).asSeconds()}s`;
}

/**
 * @param {number} duration (in microseconds)
 * @return {string} formatted, unit-labelled string with time in milliseconds
 */
export function formatTime(duration: number, isMs = false) {
  return dayjs.tz(duration / ONE_MILLISECOND).format(isMs ? STANDARD_TIME_MS_FORMAT : STANDARD_TIME_FORMAT);
}

export function formatTraceTableDate(duration: number | string) {
  return dayjs
    .tz(+duration.toString().slice(0, 13).padEnd(13, '0'))
    .format(duration.toString().length > 13 ? 'YYYY-MM-DD HH:mm:ss.SSS' : 'YYYY-MM-DD HH:mm:ss');
}

export const getSuitableTimeUnit = (microseconds: number): string => {
  if (microseconds < 1000) {
    return 'microseconds';
  }

  const duration = dayjs.duration(microseconds / 1000, 'ms');

  return Object.keys(timeUnitToShortTermMapper)
    .reverse()
    .find(timeUnit => {
      const durationInTimeUnit = duration.as(timeUnit as plugin.DurationUnitType);

      return durationInTimeUnit >= 1;
    })!;
};

export function convertTimeUnitToShortTerm(timeUnit: string) {
  if (timeUnit === 'microseconds') return 'μs';

  const shortTimeUnit = (timeUnitToShortTermMapper as any)[timeUnit];

  if (shortTimeUnit) return shortTimeUnit;

  return '';
}

export function convertToTimeUnit(microseconds: number, targetTimeUnit: string) {
  if (microseconds < 1000) {
    return microseconds;
  }

  return dayjs.duration(microseconds / 1000, 'ms').as(targetTimeUnit as plugin.DurationUnitType);
}

export function timeConversion(microseconds: number) {
  if (microseconds < 1000) {
    return `${microseconds}μs`;
  }

  const timeUnit = getSuitableTimeUnit(microseconds);

  return `${dayjs
    .duration(microseconds / 1000, 'ms')
    .as(timeUnit as plugin.DurationUnitType)}${convertTimeUnitToShortTerm(timeUnit)}`;
}
