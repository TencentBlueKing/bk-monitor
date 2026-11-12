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

import type { App } from 'vue';
import type { Pinia } from 'pinia';
import type { NativeApplicationStore } from './domains/application-store';
import type { useRetrieveStore } from './domains/retrieve-store';
import type { useCollectionStore } from './domains/collection-store';
import type { useGlobalsStore } from './domains/globals-store';
import type { ApplicationState } from './application-store.type';
import { ROOT_COMMAND_NAMES, ROOT_QUERY_NAMES, ROOT_SELECTOR_NAMES } from './domains/native-state-contracts';
type RootGetters = {
  [Name in keyof typeof ROOT_SELECTOR_NAMES]: NativeApplicationStore[(typeof ROOT_SELECTOR_NAMES)[Name]];
};
type ModuleGetters = {
  'retrieve/sceneConfigList': ReturnType<typeof useRetrieveStore>['sceneConfigList'];
  'collect/curCollect': ReturnType<typeof useCollectionStore>['curCollect'];
  'collect/exportCollectObj': ReturnType<typeof useCollectionStore>['exportCollectObj'];
  'globals/globalsData': ReturnType<typeof useGlobalsStore>['globalsData'];
  'globals/authContainerInfo': ReturnType<typeof useGlobalsStore>['authContainerInfo'];
};
type Invocation = string | { type: string; [key: string]: unknown };
type Before = (action: { type: string; payload: unknown; config: unknown }, state: ApplicationState) => void;
/** Monitor's published protocol only. All state and actions belong to native Pinia stores. */
export function createMonitorStoreCompatibility(
  pinia: Pinia,
  stores: {
    application: NativeApplicationStore;
    retrieve: ReturnType<typeof useRetrieveStore>;
    collect: ReturnType<typeof useCollectionStore>;
    globals: ReturnType<typeof useGlobalsStore>;
  },
) {
  const commands = {
    application: new Set<string>(ROOT_COMMAND_NAMES),
    retrieve: new Set([
      'updateActiveVersion',
      'updateTrendDataLoading',
      'updateTrendShellPending',
      'updateResultShellReady',
      'updateTotalCountLoaded',
      'updateTrendDataCount',
      'updateChartKey',
      'updateCachePickerValue',
      'updateCacheTimeRange',
      'updateFiledSettingConfigID',
      'updateIndexSetList',
      'updateIndexSetLoading',
      'updateCatchFieldCustomConfig',
      'updateCatchFilterAddition',
      'updateSceneConfigs',
      'resetRuntimeState',
    ]),
    collect: new Set([
      'setCurCollect',
      'updateCurCollect',
      'updateCurIndexSet',
      'updateScenarioMap',
      'updateExportCollectObj',
    ]),
    globals: new Set(['setGlobalsData', 'updateGlobalsData', 'updateAuthContainerInfo']),
  };
  const queries = {
    application: new Set<string>(ROOT_QUERY_NAMES),
    retrieve: new Set(['requestSceneConfigs', 'getIndexSetList']),
    collect: new Set<string>(),
    globals: new Set<string>(),
  };
  const modules = {
    retrieve: ['sceneConfigList'],
    collect: ['curCollect', 'exportCollectObj'],
    globals: ['globalsData', 'authContainerInfo'],
  };
  const getters: Record<string, unknown> = {};
  for (const [name, actual] of Object.entries(ROOT_SELECTOR_NAMES))
    Object.defineProperty(getters, name, { enumerable: true, get: () => stores.application[actual] });
  for (const [domain, names] of Object.entries(modules))
    for (const name of names)
      Object.defineProperty(getters, domain + '/' + name, {
        enumerable: true,
        get: () => Reflect.get(stores[domain as keyof typeof modules], name),
      });
  const state = new Proxy(stores.application.$state, {
    get: (target, key) =>
      typeof key === 'string' && Object.hasOwn(modules, key)
        ? stores[key as keyof typeof modules].$state
        : Reflect.get(target, key),
    set: (target, key, value) => {
      if (typeof key === 'string' && Object.hasOwn(modules, key)) stores[key as keyof typeof modules].$state = value;
      else Reflect.set(target, key, value);
      return true;
    },
    ownKeys: (target) => [...new Set([...Reflect.ownKeys(target), ...Object.keys(modules)])],
    getOwnPropertyDescriptor: (target, key) =>
      Reflect.getOwnPropertyDescriptor(target, key) ??
      (typeof key === 'string' && Object.hasOwn(modules, key) ? { configurable: true, enumerable: true } : undefined),
    has: (target, key) => Reflect.has(target, key) || (typeof key === 'string' && Object.hasOwn(modules, key)),
  }) as ApplicationState;
  const normalize = (type: Invocation, payload?: unknown) =>
    typeof type === 'object' ? { type: type.type, payload: type } : { type, payload };
  const resolve = (type: string) => {
    const slash = type.indexOf('/');
    return slash < 0
      ? { domain: 'application', method: type }
      : { domain: type.slice(0, slash), method: type.slice(slash + 1) };
  };
  const invoke = (kind: 'commands' | 'queries', type: string, payload?: unknown, config?: unknown) => {
    const { domain, method } = resolve(type),
      allowed = Reflect.get(kind === 'commands' ? commands : queries, domain) as Set<string> | undefined;
    if (!allowed?.has(method)) {
      if (process.env.NODE_ENV !== 'production')
        console.error('[state] unknown ' + (kind === 'queries' ? 'action' : 'mutation') + ' type: ' + type);
      return;
    }
    const store = Reflect.get(stores, domain),
      handler = Reflect.get(store, method);
    return Reflect.apply(handler, store, [payload, config]);
  };
  const domains = Object.fromEntries(
    Object.entries(stores).map(([name, store]) => [
      name,
      new Proxy(store, {
        get: (target, key) =>
          key === 'state'
            ? target.$state
            : name === 'application' && key === 'visibleFields'
            ? stores.application.resolvedVisibleFields
            : Reflect.get(target, key),
        set: (target, key, value) => {
          if (key === 'state') target.$state = value;
          else Reflect.set(target, key, value);
          return true;
        },
      }),
    ]),
  );
  const adapter = {
    pinia,
    domains,
    state,
    getters: getters as RootGetters & ModuleGetters,
    commit(type: Invocation, payload?: unknown) {
      const call = normalize(type, payload);
      invoke('commands', call.type, call.payload);
    },
    dispatch(type: Invocation, payload?: unknown, config: unknown = {}) {
      const call = normalize(type, payload),
        { domain, method } = resolve(call.type);
      if (!(Reflect.get(queries, domain) as Set<string> | undefined)?.has(method)) {
        invoke('queries', call.type, call.payload, config);
        return;
      }
      return Promise.resolve(invoke('queries', call.type, call.payload, config));
    },
    subscribeAction(subscriber: Before | { before?: Before }) {
      const before = typeof subscriber === 'function' ? subscriber : subscriber.before;
      const stops = Object.entries(stores).map(([domain, store]) =>
        store.$onAction(({ name, args }) => {
          if ((queries[domain as keyof typeof queries] as Set<string>).has(name))
            before?.(
              {
                type: domain === 'application' ? name : domain + '/' + name,
                payload: args[0],
                config: args.length > 1 ? args[1] : {},
              },
              state,
            );
        }),
      );
      return () => stops.forEach((stop) => stop());
    },
    install(app: App) {
      app.use(pinia);
      app.config.globalProperties.$store = adapter;
    },
  };
  return adapter;
}
