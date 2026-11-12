/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { createPinia, getActivePinia, type Pinia } from 'pinia';
import { hasInjectionContext } from 'vue';
/** One explicit Pinia instance shared by the log application and its exported host contract. */
export const applicationPinia = createPinia();

/** Components honor their injected owner; service callbacks use the explicit application owner. */
export function resolveApplicationPinia(pinia?: Pinia): Pinia {
  if (pinia) return pinia;
  return (hasInjectionContext() ? getActivePinia() : undefined) ?? applicationPinia;
}
