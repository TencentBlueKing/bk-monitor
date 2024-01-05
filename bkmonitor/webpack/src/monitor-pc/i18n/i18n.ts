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
import Vue from 'vue';
import VueI18n from 'vue-i18n';
import { lang, locale } from 'bk-magic-vue';

import './dayjs';

import { LANGUAGE_COOKIE_KEY } from '../../monitor-common/utils/constant';
import { docCookies } from '../../monitor-common/utils/utils';

import { mergeI18nJson } from './commmon';
// 获取语言偏好设置
const currentLang = docCookies.getItem(LANGUAGE_COOKIE_KEY) || 'zhCN';

// 判断当前语言是否为英文
export const isEn = currentLang === 'en';
document.documentElement.setAttribute('lang', currentLang);

// 设置网页标题
document.title = isEn ? 'BKMonitor | Tencent BlueKing' : '监控平台 | 腾讯蓝鲸智云';

// 设置 VueI18n 使用的语言
const i18nLocale = isEn ? 'enUS' : 'zhCN';

// 安装 VueI18n 插件
Vue.use(VueI18n);

// 设置 locale 使用的语言
locale.use(lang[i18nLocale]);

// 初始化 VueI18n 实例
const i18n = new VueI18n({
  locale: i18nLocale, // 当前语言
  fallbackLocale: 'zhCN', // 默认语言
  silentTranslationWarn: false, // 是否警告翻译缺失
  messages: {
    // 翻译文件
    ...mergeI18nJson()
  }
});

// 将 VueI18n 实例挂载到全局变量 window.i18n 上
window.i18n = i18n;

// 导出 VueI18n 实例作为默认值
export default i18n;
