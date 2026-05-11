/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { onUnmounted } from 'vue';

/**
 * useRequestAbort Hook 返回值接口
 * @template T - 响应数据类型
 * @description 提供自动中止重复请求的能力，返回执行函数、中止方法和 signal 供外部使用
 */
export interface UseRequestAbortReturn<T> {
  /**
   * 当前请求的 AbortSignal，可用于外部判断是否已终止
   * @description 每次调用 run 时会更新为新的 signal，请求完成后或被中止时为 null
   * @example if (signal?.aborted) { console.log('请求已终止') }
   */
  signal: AbortSignal | null;
  /**
   * 手动中止当前请求
   * @description 调用后会立即中止当前正在进行的请求，并将 signal 置为 null
   */
  abort: () => void;
  /**
   * 执行请求函数
   * @description 调用时会自动中止上一次未完成的请求，然后创建新的 AbortController 发起新请求
   * @param params - 请求参数，可选
   * @returns Promise<T> 请求的 Promise，如果请求被中止会抛出 AbortError，需由外部捕获处理
   */
  run: (params) => Promise<T>;
}

/**
 * 请求函数类型定义
 * @template T - 响应数据类型
 * @param params - 请求参数
 * @param options.signal - AbortSignal 用于取消请求，由 useRequestAbort 自动传入
 */
type RequestFn<T> = (params, options: { signal: AbortSignal }) => Promise<T>;

/**
 * 可中止请求 Hook
 * @description 包装请求函数，自动管理 AbortController，支持自动中止重复请求和组件卸载时清理
 * @template T - 响应数据类型
 * @param fn - 请求函数，接收 params 和 signal 参数
 * @returns {UseRequestAbortReturn<T>} 包含 run 函数、signal 和 abort 方法
 * @example
 * // 基础用法
 * const { run, signal, abort } = useRequestAbort(async (params, { signal }) => {
 *   return await fetch('/api/data', { signal }).then(res => res.json());
 * });
 *
 * // 执行请求（自动处理中止逻辑）
 * run({ id: 1 })
 *   .then(data => console.log(data))
 *   .catch(err => {
 *     if (err.name === 'AbortError') {
 *       console.log('请求被中止');
 *     } else {
 *       console.error('请求失败:', err);
 *     }
 *   });
 *
 * // 手动中止请求
 * abort();
 *
 * // 检查当前请求是否被中止
 * if (signal?.aborted) {
 *   console.log('请求已终止');
 * }
 */
export default function useRequestAbort<T = unknown>(fn: RequestFn<T>): UseRequestAbortReturn<T> {
  /** AbortController 实例引用，用于管理当前请求的中止 */
  let abortController: AbortController | null = null;
  /** 当前请求的 signal，外部可通过此值判断请求是否被中止 */
  let signal: AbortSignal | null = null;

  /**
   * 中止当前请求
   * @description 如果存在正在进行的请求，立即中止并将相关引用置空
   */
  const abort = () => {
    if (abortController) {
      abortController.abort();
      abortController = null;
      signal = null;
    }
  };

  /**
   * 包装后的请求函数
   * @description 自动中止上一次未完成的请求，并创建新的 AbortController 发起新请求
   * @param params - 请求参数
   * @returns Promise<T> 原始请求的 Promise，如果请求被中止会抛出 AbortError
   */
  const run = async (params): Promise<T> => {
    // 中止上一次未完成的请求，避免竞态条件
    abort();

    // 创建新的 AbortController 用于本次请求
    abortController = new AbortController();
    signal = abortController.signal;

    // 调用用户传入的请求函数，传入 signal 供其使用
    return fn(params, { signal });
  };

  // 组件卸载时自动中止请求，防止内存泄漏
  onUnmounted(() => {
    abort();
  });

  return { run, signal, abort };
}
