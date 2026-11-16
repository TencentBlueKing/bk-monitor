/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
export * from '../vue-runtime.mjs';
export { default } from '../vue-runtime.mjs';
import { defineComponent as defineNativeComponent } from '../vue-runtime.mjs';
import { preserveVue3ComponentModel } from '../vue3-component-model';

/** The same model/render compatibility flags previously applied by scanning
 * all TDesign exports. The scoped build adapter applies them at definition time
 * so lazy components also receive the flags without eagerly importing them. */
export const defineComponent: typeof defineNativeComponent = ((...args: unknown[]) => {
  const component = Reflect.apply(defineNativeComponent, undefined, args) as { compatConfig?: Record<string, unknown> };
  preserveVue3ComponentModel(component);
  component.compatConfig = { ...component.compatConfig, RENDER_FUNCTION: false };
  return component;
}) as typeof defineNativeComponent;
