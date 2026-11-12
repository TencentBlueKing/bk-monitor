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

import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../../src/app/state/domains/native-state-contracts.ts', import.meta.url), 'utf8');
const commands = new Set([...source.match(/ROOT_COMMAND_NAMES = (\[[\s\S]*?\]) as const/)[1].matchAll(/['"]([^'"]+)['"]/g)].map(match => match[1]));
const queries = new Set([...source.match(/ROOT_QUERY_NAMES = (\[[\s\S]*?\]) as const/)[1].matchAll(/['"]([^'"]+)['"]/g)].map(match => match[1]));
const cache = new WeakMap();
/** Test-only migration of existing fixture spies. Production code never imports this adapter. */
export function nativeStateFixture(context, namespace = '') {
  let modules = cache.get(context);
  if (!modules) {
    modules = new Map();
    cache.set(context, modules);
  }
  if (modules.has(namespace)) return modules.get(namespace);
  const data = namespace ? context.state?.[namespace] ?? {} : context.state ?? {};
  const proxy = new Proxy(data, {
    get(target, key) {
      if (key === '$state') return target;
      if (!namespace && ['retrieve', 'collect', 'globals'].includes(key)) return nativeStateFixture(context, key);
      const qualified = namespace ? namespace + '/' + String(key) : String(key);
      if (!namespace && key === 'resolvedVisibleFields') return context.getters?.visibleFields ?? target.visibleFields;
      if (qualified in (context.getters ?? {})) return context.getters[qualified];
      if (key in target) return Reflect.get(target, key);
      if ((!namespace && commands.has(key)) || (namespace && /^(update|reset|set)/.test(String(key))))
        return (...args) => {
          if (!context.commit) throw new Error('Missing native command fixture: ' + qualified);
          return context.commit(qualified, ...args);
        };
      if ((!namespace && queries.has(key)) || (namespace && ['requestSceneConfigs', 'getIndexSetList'].includes(key)))
        return (...args) => {
          if (!context.dispatch) throw new Error('Missing native query fixture: ' + qualified);
          return context.dispatch(qualified, ...args);
        };
    },
    set(target, key, value) {
      return Reflect.set(target, key, value);
    },
  });
  modules.set(namespace, proxy);
  return proxy;
}
export function nativeFixtureDependencies(dependencies) {
  if (typeof dependencies['@/app/state/domains/application-store']?.useApplicationStore === 'function')
    return dependencies;
  const entry = Object.entries(dependencies).find(([key]) => key.endsWith('/use-store'));
  if (!entry) return dependencies;
  const old = entry[1],
    factory = typeof old === 'function' ? old : old.default;
  if (!factory) return dependencies;
  return {
    ...dependencies,
    '@/app/state/domains/application-store': { useApplicationStore: () => nativeStateFixture(factory()) },
  };
}
