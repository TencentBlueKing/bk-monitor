/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { useApplicationStores } from './application-runtime';

type Mapping = readonly string[] | Record<string, string | ((this: unknown, state: object, getters: object) => unknown)>;
function normalize(namespace: string | Mapping, map?: Mapping) {
  return typeof namespace === 'string' ? { namespace: namespace.replace(/\/$/, ''), map: map ?? [] } : { namespace: '', map: namespace };
}
function mappings(map: Mapping) {
  return Array.isArray(map) ? map.map(key => [key, key] as const) : Object.entries(map);
}
/** Options components read the same native Pinia states; no Vuex runtime is loaded. */
export function mapState(namespace: string | Mapping, map?: Mapping) {
  const selection = normalize(namespace, map);
  return Object.fromEntries(mappings(selection.map).map(([key, value]) => [key, function (this: unknown) {
    const runtime = useApplicationStores();
    const state: object = selection.namespace ? Reflect.get(runtime.domains, selection.namespace).state : runtime.state;
    const getters = runtime.getters;
    return typeof value === 'function' ? value.call(this, state, getters) : Reflect.get(state, value);
  }]));
}
export function mapGetters(namespace: string | Mapping, map?: Mapping) {
  const selection = normalize(namespace, map);
  return Object.fromEntries(mappings(selection.map).map(([key, value]) => [key, function () {
    const runtime = useApplicationStores();
    return Reflect.get(runtime.getters, selection.namespace ? `${selection.namespace}/${value}` : value);
  }]));
}
