/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import en from 'dayjs/locale/en';
import cn from 'dayjs/locale/zh-cn';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore';
import localizedFormat from 'dayjs/plugin/localizedFormat';
import relativeTime from 'dayjs/plugin/relativeTime';
import tz from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { LANGUAGE_COOKIE_KEY, TIMEZONE_STORE_KEY } from 'monitor-common/utils/constant';
import { docCookies } from 'monitor-common/utils/utils';

dayjs.extend(customParseFormat);
dayjs.extend(localizedFormat);
dayjs.extend(relativeTime);
dayjs.extend(isSameOrBefore);
dayjs.extend(isBetween);
dayjs.extend(tz);
dayjs.extend(utc);
dayjs.extend(duration);

const currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY);
dayjs.locale({
  ...(currentLang === 'en' ? en : cn),
  weekStart: 1,
});
// window.timezone = dayjs.tz.guess();
// dayjs.tz.setDefault(window.timezone);
export const updateTimezone = (tz: string) => {
  if (!tz || tz === 'undefined' || !isValidTimeZone(tz)) return;
  window.timezone = tz || dayjs.tz.guess();
  sessionStorage.setItem(TIMEZONE_STORE_KEY, window.timezone);
  dayjs.tz.setDefault(window.timezone);
};
export const destroyTimezone = () => {
  window.timezone = dayjs.tz.guess();
  dayjs.tz.setDefault(window.timezone);
};
export const getDefaultTimezone = () => {
  const storeVal = sessionStorage.getItem(TIMEZONE_STORE_KEY);
  const timezone = storeVal && storeVal !== 'undefined' && isValidTimeZone(storeVal) ? storeVal : dayjs.tz.guess();
  window.timezone = timezone;
  dayjs.tz.setDefault(window.timezone);
  return timezone;
};

export const isValidTimeZone = (timeZone: string) => {
  try {
    new Intl.DateTimeFormat('en-US', { timeZone });
    return true;
  } catch {
    return false;
  }
};
