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
import en from 'dayjs/locale/en';
import cn from 'dayjs/locale/zh-cn';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import duration from 'dayjs/plugin/duration';
import localizedFormat from 'dayjs/plugin/localizedFormat';
import relativeTime from 'dayjs/plugin/relativeTime';
import tz from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import jsCookie from 'js-cookie';

dayjs.extend(customParseFormat);
dayjs.extend(localizedFormat);
dayjs.extend(relativeTime);
dayjs.extend(tz);
dayjs.extend(utc);
dayjs.extend(duration);

const currentLang = jsCookie.get('blueking_language');
dayjs.locale({
  ...(currentLang === 'en' ? en : cn),
  weekStart: 1,
});
window.timezone = dayjs.tz.guess();
dayjs.tz.setDefault(window.timezone);
export const updateTimezone = (newTz?: string) => {
  window.timezone = newTz || dayjs.tz.guess();
  dayjs.tz.setDefault(window.timezone);
};
