/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { defineComponent, h } from 'vue';
import { ConfigProvider } from 'tdesign-vue-next';
import english from 'tdesign-vue-next/es/locale/en_US';
import chinese from 'tdesign-vue-next/es/locale/zh_CN';
import i18n from './i18n';
import { createApplicationControlConfig } from '../ui/tdesign-config';
type MutableLocale<T> = T extends object ? { -readonly [K in keyof T]: MutableLocale<T[K]> } : T;
// TDesign exports readonly locale constants but expects mutable provider arrays.
// Give each provider configuration its own data instead of mutating those exports.
const locales = {
  en: structuredClone(english) as MutableLocale<typeof english>,
  'zh-cn': structuredClone(chinese) as MutableLocale<typeof chinese>,
};
// Stable identity prevents parent rerenders from resetting open native controls.
const applicationConfigs = {
  en: createApplicationControlConfig(locales.en),
  'zh-cn': createApplicationControlConfig(locales['zh-cn']),
};
/** Keep native TDesign controls in the same locale as compiled application messages. */
export default defineComponent({
  name: 'ApplicationLocaleProvider',
  compatConfig: { MODE: 3 },
  setup(_, { slots }) {
    return () => h(ConfigProvider, { globalConfig: applicationConfigs[i18n.getLocale()] }, slots);
  },
});
