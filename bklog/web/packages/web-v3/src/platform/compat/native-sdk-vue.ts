/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
export * from '@vue/compat';
import { defineComponent as defineNativeComponent } from '@vue/compat';

export function configureNativeSdkComponent<T extends object>(component: T): T {
  const config = Reflect.get(component, 'compatConfig');
  Reflect.set(component, 'compatConfig', {
    ...(config && typeof config === 'object' ? config : {}), MODE: 3,
    COMPONENT_V_MODEL: false, RENDER_FUNCTION: false, INSTANCE_ATTRS_CLASS_STYLE: false,
    ATTR_FALSE_VALUE: false, ATTR_ENUMERATED_COERCION: false,
  });
  return component;
}

/**
 * Official Vue3 SDKs contain private components whose options cannot be reached
 * through public exports. Configure them when the SDK defines them; keep all
 * components on the application's single Vue runtime. The build resolver limits
 * this facade to approved Vue3 SDK entries.
 */
export const defineComponent: typeof defineNativeComponent = ((...args: unknown[]) => {
  const component = Reflect.apply(defineNativeComponent, undefined, args) as object;
  return configureNativeSdkComponent(component);
}) as typeof defineNativeComponent;
