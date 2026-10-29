/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
export * from '@vue/compat';
import { defineComponent as defineNativeComponent } from '@vue/compat';

/**
 * Official Vue3 SDKs contain private components (e.g. PopReference) whose
 * options cannot be reached through public exports. Configure them when the
 * SDK defines them; keep all components on the application's single Vue runtime.
 * The build resolver limits this facade to date-picker/vue3 and bkui-vue.
 */
export const defineComponent: typeof defineNativeComponent = ((...args: unknown[]) => {
  const component = Reflect.apply(defineNativeComponent, undefined, args) as object;
  const config = Reflect.get(component, 'compatConfig');
  Reflect.set(component, 'compatConfig', { ...(config && typeof config === 'object' ? config : {}), MODE: 3 });
  return component;
}) as typeof defineNativeComponent;
