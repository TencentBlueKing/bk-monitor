/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
/** Contexts consumed by preserved business handlers; independent of Vuex. */
export interface StateActionContext<State, RootState = State> {
  state: State;
  rootState: RootState;
  getters: Record<string, unknown>;
  rootGetters: Record<string, unknown>;
  commit(type: string, payload?: unknown, options?: { root?: boolean }): void;
  dispatch(type: string, payload?: unknown, options?: { root?: boolean; [key: string]: unknown }): Promise<unknown> | undefined;
}
export type StateGetterDefinitions<State, RootState = State> = Record<string,
  (state: State, getters: Record<string, unknown>, rootState: RootState, rootGetters: Record<string, unknown>) => unknown>;
