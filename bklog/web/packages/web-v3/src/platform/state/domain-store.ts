/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { computed, ref, type Ref, type ComputedRef } from 'vue';
import { defineStore } from 'pinia';

/** Business handlers retain their source parameter and result types. */
type Handler = (...args: never[]) => unknown;
type Handlers = Record<string, Handler>;
type ParametersAfterContext<F extends Handler> = Parameters<F> extends [unknown, ...infer Rest] ? Rest : [];
type BoundHandlers<Definitions extends Handlers> = {
  [Name in keyof Definitions]: (...args: ParametersAfterContext<Definitions[Name]>) => ReturnType<Definitions[Name]>;
};
type ComputedGetters<Definitions extends Handlers> = {
  [Name in keyof Definitions]: ComputedRef<ReturnType<Definitions[Name]>>;
};
export interface DomainActionContext {
  state: object;
  getters: object;
  rootState: object;
  rootGetters: object;
  commit(type: string | { type: string }, payload?: unknown, options?: { root?: boolean }): unknown;
  dispatch(type: string | { type: string }, payload?: unknown, options?: { root?: boolean }): unknown;
}

/**
 * Pinia owns state, computed getters and every named action. The adapter only
 * supplies the explicit context expected by the preserved business handlers.
 * It does not use Vuex internals or maintain another state container.
 */
export function defineDomainStore<State extends object, Getters extends Handlers, Mutations extends Handlers, Actions extends Handlers>(options: {
  id: string;
  createState(): State;
  getters: Getters;
  mutations: Mutations;
  actions: Actions;
  context(state: State): DomainActionContext;
}) {
  return defineStore(options.id, () => {
    const state = ref(options.createState()) as Ref<State>;
    const selectors: Record<string, ComputedRef<unknown>> = {};
    const methods: Record<string, (...args: unknown[]) => unknown> = {};
    for (const [name, getter] of Object.entries(options.getters)) {
      selectors[name] = computed(() => {
        const context = options.context(state.value);
        return getter(...[context.state, context.getters, context.rootState, context.rootGetters] as never[]);
      });
    }
    for (const [name, mutation] of Object.entries(options.mutations)) {
      methods[name] = (...args) => mutation(...[options.context(state.value).state, ...args] as never[]);
    }
    for (const [name, action] of Object.entries(options.actions)) {
      if (name in methods) throw new Error(`Ambiguous Pinia action ${options.id}.${name}`);
      methods[name] = (...args) => action(...[options.context(state.value), ...args] as never[]);
    }
    return { state, ...selectors, ...methods } as { state: Ref<State> } & ComputedGetters<Getters> & BoundHandlers<Mutations> & BoundHandlers<Actions>;
  });
}
