/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import type { App } from 'vue';
import { createPinia, type Pinia, type StoreGeneric } from 'pinia';
import { defineDomainStore, type DomainActionContext } from './domain-store';

type Handler = (...args: never[]) => unknown;
type Handlers = Record<string, Handler>;
export interface StateDomainDefinition {
  createState(): object;
  getters: Handlers;
  mutations: Handlers;
  actions: Handlers;
}
type BoundHandlers<Definitions extends Handlers> = {
  [Name in keyof Definitions]: Definitions[Name] extends (context: never, ...args: infer Args) => infer Result ? (...args: Args) => Result : never;
};
type NativeDomain<Definition extends StateDomainDefinition> = Pick<StoreGeneric, '$id' | '$onAction' | '$subscribe' | '$dispose'> & {
  $state: { state: ReturnType<Definition['createState']> };
  state: ReturnType<Definition['createState']>;
} & { [Name in keyof Definition['getters']]: ReturnType<Definition['getters'][Name]> }
  & BoundHandlers<Definition['mutations']> & BoundHandlers<Definition['actions']>;
export type NativeDomains<Definitions extends Record<string, StateDomainDefinition>> = {
  [Name in keyof Definitions]: NativeDomain<Definitions[Name]>;
};
type Intersect<Union> = (Union extends unknown ? (value: Union) => void : never) extends (value: infer Result) => void ? Result : never;
type CompositeState<Definitions extends Record<string, StateDomainDefinition>, Root extends keyof Definitions> = ReturnType<Definitions[Root]['createState']> & {
  [Name in Exclude<keyof Definitions, Root>]: ReturnType<Definitions[Name]['createState']>;
};
type ScopedHandlers<Definitions extends Record<string, StateDomainDefinition>, Root extends keyof Definitions, Kind extends 'actions' | 'getters'> = Definitions[Root][Kind] & Intersect<{
  [Name in Exclude<keyof Definitions, Root> & string]: { [Method in keyof Definitions[Name][Kind] & string as `${Name}/${Method}`]: Definitions[Name][Kind][Method] };
}[Exclude<keyof Definitions, Root> & string]>;
type GetterResults<Definitions extends Record<string, StateDomainDefinition>, Root extends keyof Definitions> = {
  [Name in keyof ScopedHandlers<Definitions, Root, 'getters'>]: ScopedHandlers<Definitions, Root, 'getters'>[Name] extends Handler ? ReturnType<ScopedHandlers<Definitions, Root, 'getters'>[Name]> : never;
};
type RuntimeDomain = { state: object; [name: string]: unknown };
type Invocation = string | { type: string; [key: string]: unknown };
interface ActionSubscriber { before?(action: { type: string; payload: unknown; config: unknown }, state: object): void; }

/** Pinia is the sole state owner. The legacy envelope is confined to this boundary. */
export function createStateRuntime<const Definitions extends Record<string, StateDomainDefinition>, const Root extends keyof Definitions & string>(options: {
  definitions: Definitions;
  root: Root;
  pinia?: Pinia;
  scope?: string;
}) {
  const pinia = options.pinia ?? createPinia();
  const stores: Record<string, RuntimeDomain> = {};
  const getters: Record<string, unknown> = {};
  const localGetters: Record<string, Record<string, unknown>> = {};
  const subscribers = new Set<ActionSubscriber>();
  let state: object;
  const normalize = (type: Invocation, payload?: unknown) => typeof type === 'object'
    ? { type: type.type, payload: type } : { type, payload };
  const resolve = (type: string) => {
    const slash = type.indexOf('/');
    return slash < 0 ? { domain: options.root, method: type } : { domain: type.slice(0, slash), method: type.slice(slash + 1) };
  };
  const invoke = (kind: 'actions' | 'mutations', type: string, payload?: unknown, config?: unknown): unknown => {
    const { domain, method } = resolve(type);
    const definition = options.definitions[domain];
    if (!definition || !Object.hasOwn(definition[kind], method)) {
      if (process.env.NODE_ENV !== 'production') console.error(`[state] unknown ${kind === 'actions' ? 'action' : 'mutation'} type: ${type}`);
      return undefined;
    }
    const handler = stores[domain][method];
    if (typeof handler !== 'function') throw new Error(`Pinia action is unavailable: ${type}`);
    return (handler as (payload: unknown, config?: unknown) => unknown)(payload, config);
  };
  const commit = (type: Invocation, payload?: unknown) => {
    const call = normalize(type, payload);
    invoke('mutations', call.type, call.payload);
  };
  type Actions = ScopedHandlers<Definitions, Root, 'actions'>;
  function dispatch<Name extends keyof Actions & string>(type: Name, payload?: unknown, config?: unknown): Promise<Actions[Name] extends Handler ? Awaited<ReturnType<Actions[Name]>> : unknown>;
  function dispatch(type: Invocation, payload?: unknown, config?: unknown): Promise<unknown> | undefined;
  function dispatch(type: Invocation, payload?: unknown, config: unknown = {}): Promise<unknown> | undefined {
    const call = normalize(type, payload);
    const { domain, method } = resolve(call.type);
    if (!options.definitions[domain] || !Object.hasOwn(options.definitions[domain].actions, method)) {
      invoke('actions', call.type, call.payload, config);
      return undefined;
    }
    const action = { ...call, config };
    for (const subscriber of [...subscribers]) subscriber.before?.(action, state);
    return Promise.resolve(invoke('actions', call.type, call.payload, config));
  };
  const qualified = (domain: string, type: string, root?: boolean) => root || domain === options.root ? type : `${domain}/${type}`;
  const localCall = (kind: 'actions' | 'mutations', domain: string, type: Invocation, payload?: unknown, config?: { root?: boolean }) => {
    const call = normalize(type, payload);
    const selection = typeof type === 'object' ? payload as { root?: boolean } | undefined : config;
    const target = qualified(domain, call.type, selection?.root);
    return kind === 'actions' ? dispatch(target, call.payload, config) : commit(target, call.payload);
  };
  for (const [name, definition] of Object.entries(options.definitions)) {
    localGetters[name] = name === options.root ? getters : {};
    const useDomain = defineDomainStore({
      ...definition,
      id: `${options.scope ?? 'bklog'}.${name}`,
      context(domainState): DomainActionContext {
        return {
          state: name === options.root ? state : domainState,
          getters: localGetters[name], rootState: state, rootGetters: getters,
          commit: (type, payload, config) => localCall('mutations', name, type, payload, config),
          dispatch: (type, payload, config) => localCall('actions', name, type, payload, config),
        };
      },
    });
    const store = useDomain(pinia);
    stores[name] = store as unknown as RuntimeDomain;
    for (const key of Object.keys(definition.getters)) {
      Object.defineProperty(localGetters[name], key, { enumerable: true, get: () => stores[name][key] });
      if (name !== options.root) Object.defineProperty(getters, `${name}/${key}`, { enumerable: true, get: () => stores[name][key] });
    }
  }
  // This view contains no copied state. It retains the published Monitor root/module
  // shape while reads and writes reach the corresponding native Pinia store.
  state = new Proxy({}, {
    get: (_, key) => typeof key === 'string' && key !== options.root && Object.hasOwn(stores, key)
      ? stores[key].state : Reflect.get(stores[options.root].state, key),
    set: (_, key, value) => {
      if (typeof key === 'string' && key !== options.root && Object.hasOwn(stores, key)) stores[key].state = value;
      else Reflect.set(stores[options.root].state, key, value);
      return true;
    },
    ownKeys: () => [...new Set([...Reflect.ownKeys(stores[options.root].state), ...Object.keys(stores).filter(name => name !== options.root)])],
    getOwnPropertyDescriptor: (_, key) => Object.hasOwn(stores[options.root].state, key) || typeof key === 'string' && key !== options.root && Object.hasOwn(stores, key)
      ? { enumerable: true, configurable: true } : undefined,
    deleteProperty: (_, key) => Reflect.deleteProperty(stores[options.root].state, key),
    has: (_, key) => key in stores[options.root].state || typeof key === 'string' && Object.hasOwn(stores, key),
  });
  const runtime = {
    pinia, domains: stores as unknown as NativeDomains<Definitions>, state: state as CompositeState<Definitions, Root>, getters: getters as GetterResults<Definitions, Root>, commit, dispatch,
    subscribeAction(subscriber: ActionSubscriber | NonNullable<ActionSubscriber['before']>) {
      const normalized = typeof subscriber === 'function' ? { before: subscriber } : subscriber;
      subscribers.add(normalized);
      return () => subscribers.delete(normalized);
    },
    install(app: App) {
      app.use(pinia);
      Reflect.set(app.config.globalProperties, '$store', runtime);
    },
  };
  return runtime;
}
