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
import { createI18n, type Locale, type Path } from 'vue-i18n';

import { LANGUAGE_COOKIE_KEY } from 'monitor-common/utils';
import { docCookies } from 'monitor-common/utils/utils';
import { mergeI18nJson } from 'monitor-pc/i18n/common';

import './dayjs';

let currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY);
if (currentLang === 'en') {
  currentLang = 'enUS';
} else {
  currentLang = 'zhCN';
}
// 判断当前语言是否为英文
export const isEn = currentLang === 'enUS';
const i18n = createI18n({
  locale: currentLang,
  fallbackLocale: 'zh-cn',
  silentTranslationWarn: false,
  silentFallbackWarn: false,
  legacy: true,
  missing: (locale: Locale, key: Path) => {
    if (process.env.NODE_ENV === 'development') {
      console.warn(`缺少翻译key: ${key} in ${locale}`);
    }
    return key;
  },
  messages: {
    ...mergeI18nJson(),
  },
});
window.i18n = i18n.global;
export default i18n;
