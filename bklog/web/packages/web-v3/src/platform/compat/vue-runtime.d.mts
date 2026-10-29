/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
// @vue/compat accepts both generations at its registration boundary. The
// installed package omits vue.d.ts, so describe that boundary without changing vue's native types.
import Vue2 from '@legacy-vue';
import type { Component, Directive, Plugin, ComponentOptions } from 'vue';
export * from 'vue';
type CompatConstructor = typeof Vue2 & {
  component(name: string, component: Component): Component;
  directive(name: string, directive: Directive): void;
  use(plugin: Plugin, ...options: unknown[]): CompatConstructor;
  mixin(options: ComponentOptions): CompatConstructor;
};
declare const Vue: CompatConstructor;
export default Vue;
export const set: typeof Vue2.set;
export const del: typeof Vue2.delete;
