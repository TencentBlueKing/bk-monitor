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

import { computed, ref, type App } from 'vue';
import { m } from '#paraglide/messages.js';
import { setLocale as setCompiledLocale } from '#paraglide/runtime.js';
import { locale as controlLocale, lang } from 'bk-magic-vue';
import jsCookie from 'js-cookie';
import Vue from '@/platform/compat/vue-runtime.mjs';
import keys from './legacy-message-keys.json';
import { createTranslator, type ApplicationLocale, type CompiledMessage } from './translator';
import './dayjs';

const initialLocale: ApplicationLocale = jsCookie.get('blueking_language') === 'en' ? 'en' : 'zh-cn';
const activeLocale = ref<ApplicationLocale>(initialLocale);
function setLocale(value: string) {
  const next: ApplicationLocale = value === 'en' ? 'en' : 'zh-cn';
  setCompiledLocale(next, { reload: false });
  activeLocale.value = next;
  controlLocale.use(next === 'en' ? lang.enUS : lang.zhCN);
}
setLocale(initialLocale);

// A Map also keeps bundlers from expanding every dynamic translation call
// across the entire generated message namespace during effect analysis.
const compiledMessages = new Map<string, CompiledMessage>(Object.entries(m).map(([id, message]) => [id, message as CompiledMessage]));
const t = createTranslator(key => {
  const id = Object.hasOwn(keys, key) ? Reflect.get(keys, key) : key;
  return compiledMessages.get(id);
}, () => activeLocale.value);
const i18n = {
  t,
  locale: computed({ get: () => activeLocale.value, set: setLocale }),
  availableLocales: ['zh-cn', 'en'] as const,
  getLocale: () => activeLocale.value,
  setLocale,
  install(app: App) {
    Reflect.set(app.config.globalProperties, '$t', t);
    Reflect.set(app.config.globalProperties, '$i18n', i18n);
  },
};
controlLocale.i18n((key, values) => t(key, values));
// Standalone legacy controls still use the compatibility constructor (e.g. API
// error toasts); install the same translator explicitly without a global Mixin.
Reflect.set(Vue.prototype, '$t', t);
Reflect.set(Vue.prototype, '$i18n', i18n);
window.$t = t;
export default i18n;
