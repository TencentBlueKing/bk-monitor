/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { shallowReactive, shallowRef, unref, type MaybeRef } from 'vue';
import {
  START_LOCATION,
  type Router,
  type RouteLocationNormalizedLoaded,
  type RouteLocationRaw,
  type LocationQueryRaw,
  type RouteParamsRaw,
} from 'vue-router';
export type MonitorHostRoute = Partial<Omit<RouteLocationNormalizedLoaded, 'query' | 'params'>> & {
  query: LocationQueryRaw;
  params: RouteParamsRaw;
};
export interface MonitorHostRouter {
  readonly currentRoute: MaybeRef<MonitorHostRoute>;
  replace(location: RouteLocationRaw): unknown;
  push(location: RouteLocationRaw): unknown;
  resolve(location: RouteLocationRaw): unknown;
}
/** Mirror the existing host router without changing its URL or query protocol.
 * Vue3 consumers receive the normal router Ref and a reactive route object. */
export function createMonitorHostRouter(host: MonitorHostRouter, initial?: MonitorHostRoute) {
  const route = shallowReactive({ ...START_LOCATION, ...(initial ?? unref(host.currentRoute)) });
  const currentRoute = shallowRef(route);
  function synchronize() {
    const latest = unref(host.currentRoute);
    if (latest) Object.assign(route, latest);
  }
  const router = new Proxy(host, {
    get(target, key) {
      if (key === 'currentRoute') return currentRoute;
      if (key === 'replace' || key === 'push')
        return (location: RouteLocationRaw) => {
          const result = target[key](location);
          synchronize(); // The Trace host performs navigation synchronously.
          return Promise.resolve(result).then(value => {
            synchronize();
            return value;
          });
        };
      const value = Reflect.get(target, key, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
  // Only the host boundary translates generations; application hooks keep the
  // native Vue Router contract and host-owned navigation methods.
  return { router: router as unknown as Router, route: route as RouteLocationNormalizedLoaded, synchronize };
}
