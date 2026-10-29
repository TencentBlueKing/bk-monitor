/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { unref } from 'vue';
import type { Router, RouteLocationNormalizedLoaded } from 'vue-router';
export type SourceRouter = Omit<Router, 'currentRoute'> & { readonly currentRoute: RouteLocationNormalizedLoaded };
const adapters = new WeakMap<Router, SourceRouter>();
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
