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
export interface DateTimeBuiltinFormat {
  __momentBuiltinFormatBrand: any;
}
export type DateTimeInput = Array<number | string> | Date | DateTime | number | string; // null | undefined
export type FormatInput = DateTimeBuiltinFormat | string | undefined;
export type DurationInput = DateTimeDuration | number | string;
export type DurationUnit =
  | 'M'
  | 'Q'
  | 'd'
  | 'day'
  | 'days'
  | 'h'
  | 'hour'
  | 'hours'
  | 'm'
  | 'millisecond'
  | 'milliseconds'
  | 'minute'
  | 'minutes'
  | 'month'
  | 'months'
  | 'ms'
  | 'quarter'
  | 'quarters'
  | 's'
  | 'second'
  | 'seconds'
  | 'w'
  | 'week'
  | 'weeks'
  | 'y'
  | 'year'
  | 'years';

export interface DateTimeLocale {
  firstDayOfWeek: () => number;
}

export interface DateTimeDuration {
  asHours: () => number;
  hours: () => number;
  minutes: () => number;
  seconds: () => number;
  asSeconds: () => number;
}

export interface DateTime {
  add: (amount?: DateTimeInput, unit?: DurationUnit) => DateTime;
  set: (unit: DurationUnit, amount: DateTimeInput) => void;
  diff: (amount: DateTimeInput, unit?: DurationUnit, truncate?: boolean) => number;
  endOf: (unitOfTime: DurationUnit) => DateTime;
  format: (formatInput?: FormatInput) => string;
  fromNow: (withoutSuffix?: boolean) => string;
  from: (formaInput: DateTimeInput) => string;
  isSame: (input?: DateTimeInput, granularity?: DurationUnit) => boolean;
  isValid: () => boolean;
  local: () => DateTime;
  locale: (locale: string) => DateTime;
  startOf: (unitOfTime: DurationUnit) => DateTime;
  subtract: (amount?: DateTimeInput, unit?: DurationUnit) => DateTime;
  toDate: () => Date;
  toISOString: () => string;
  isoWeekday: (day?: number | string) => number | string;
  valueOf: () => number;
  unix: () => number;
  utc: () => DateTime;
  utcOffset: () => number;
  hour?: () => number;
  minute?: () => number;
}

export const setLocale = (_language: string) => {
  dayjs.locale();
};

export const toUtc = (input?, formatInput?): DateTime => dayjs.utc(input, formatInput) as unknown as DateTime;

export const toDuration = (input?, unit?): DateTimeDuration => dayjs.duration(input, unit) as DateTimeDuration;

export const dateTime = (input?, formatInput?): DateTime => dayjs(input, formatInput) as unknown as DateTime;

export const dateTimeAsMoment = (input?: DateTimeInput) => dateTime(input);

export const dateTimeForTimeZone = (timezone?, input?: DateTimeInput, formatInput?: FormatInput): DateTime => {
  if (timezone === 'utc') {
    return toUtc(input, formatInput);
  }

  return dateTime(input, formatInput);
};
