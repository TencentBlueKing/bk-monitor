/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { unref } from 'vue';
import type { LocationQueryRaw, Router, RouteLocationNormalizedLoaded } from 'vue-router';
export type SourceRouter = Omit<Router, 'currentRoute'> & { readonly currentRoute: RouteLocationNormalizedLoaded };
const adapters = new WeakMap<Router, SourceRouter>();

const legacyEncode = (value: string | number | boolean) =>
  encodeURIComponent(String(value))
    .replace(/[!'()*]/g, char => `%${char.charCodeAt(0).toString(16)}`)
    .replace(/%2C/g, ',');

/** Match Vue Router 3 query encoding while following Vue Router 4's no-leading-? contract. */
export function stringifyLegacyQuery(query: LocationQueryRaw): string {
  return Object.keys(query)
    .flatMap(key => {
      const value = query[key];
      if (value === undefined) return [];
      if (value === null) return [legacyEncode(key)];
      if (Array.isArray(value)) {
        return value.flatMap(item => {
          if (item === undefined) return [];
          if (item === null) return [legacyEncode(key)];
          return `${legacyEncode(key)}=${legacyEncode(item)}`;
        });
      }
      return `${legacyEncode(key)}=${legacyEncode(value)}`;
    })
    .join('&');
}

/** Preserve the source currentRoute object contract over Vue Router 4's Ref. */
export function asSourceRouter(router: Router): SourceRouter {
  let adapter = adapters.get(router);
  if (!adapter) {
    adapter = new Proxy(router, {
      get(target, key) {
        return key === 'currentRoute' ? unref(target.currentRoute) : Reflect.get(target, key, target);
      },
    }) as unknown as SourceRouter;
    adapters.set(router, adapter);
  }
  return adapter;
}
