/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { createPinia, type Pinia } from 'pinia';
import { createStateRuntime } from '@/platform/state/state-runtime';
import actions from './actions';
import getters from './getters';
import mutations from './mutations';
import collect from './collect';
import globals from './globals';
import retrieve from './retrieve';
import { createStoreState } from './state';
import { applicationPinia } from './pinia';

export function createApplicationRuntime(pinia: Pinia = createPinia()) {
  return createStateRuntime({
    pinia,
    root: 'application',
    definitions: {
      application: { createState: createStoreState, getters, mutations, actions },
      retrieve: { ...retrieve, createState: () => structuredClone(retrieve.state) },
      collect: { ...collect, createState: () => structuredClone(collect.state) },
      globals: { ...globals, createState: () => structuredClone(globals.state) },
    },
  });
}
const applications = new WeakMap<Pinia, ReturnType<typeof createApplicationRuntime>>();
export function useApplicationStores(pinia: Pinia = applicationPinia) {
  let runtime = applications.get(pinia);
  if (!runtime) {
    runtime = createApplicationRuntime(pinia);
    applications.set(pinia, runtime);
  }
  return runtime;
}
export const useApplicationStore = (pinia?: Pinia) => useApplicationStores(pinia).domains.application;
export const useRetrieveStore = (pinia?: Pinia) => useApplicationStores(pinia).domains.retrieve;
export const useCollectionStore = (pinia?: Pinia) => useApplicationStores(pinia).domains.collect;
export const useGlobalsStore = (pinia?: Pinia) => useApplicationStores(pinia).domains.globals;
