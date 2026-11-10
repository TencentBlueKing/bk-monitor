/**
 * Grep 挂载 / 检索状态变化时的请求触发决策（纯函数，便于单测）。
 */

export type GrepMountAction = 'reload' | 'idle' | 'wait';

/**
 * 挂载时是否拉数：
 * - wait: 主检索进行中，等 SEARCHING_CHANGE(false)
 * - reload: 立即 reloadGrepDataAndTotal
 * - idle: 无字段，结束 loading，不请求
 */
export function resolveGrepMountAction(isSearching: boolean, field: string): GrepMountAction {
  if (isSearching) {
    return 'wait';
  }
  if (field) {
    return 'reload';
  }
  return 'idle';
}

/**
 * SEARCHING_CHANGE 与 INDEX_SET_ID_CHANGE 共用 handler，仅 boolean 才处理。
 */
export function shouldHandleSearchingChange(payload: unknown): payload is boolean {
  return typeof payload === 'boolean';
}

/**
 * SEARCHING_CHANGE(false) 时拉数，true 时等待。
 */
export function shouldReloadOnSearchingChange(isSearching: boolean): boolean {
  return !isSearching;
}
