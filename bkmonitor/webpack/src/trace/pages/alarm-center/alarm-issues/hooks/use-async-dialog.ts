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

import { type Ref, shallowRef, watch } from 'vue';

/** useAsyncDialog 确认事件对象 */
export interface AsyncDialogConfirmEvent<T extends Record<string, unknown> = Record<string, unknown>> {
  /** 业务数据 */
  payload: T;
  /** 异步结果，可供调用方 await */
  promise: Promise<void>;
  /** 业务失败时调用 */
  reject: () => void;
  /** 业务成功时调用 */
  resolve: () => void;
}

/** useAsyncDialog 返回类型 */
export type UseAsyncDialogReturnType = ReturnType<typeof useAsyncDialog>;

/** useAsyncDialog 配置选项 */
interface UseAsyncDialogOptions {
  /** reject 时是否自动关闭弹窗，默认 false */
  closeOnReject?: boolean;
  /** 外部受控的显隐状态 */
  isShow: Ref<boolean>;
  /** 显隐状态变更回调，对应 emit('update:isShow', val) */
  onShowChange: (value: boolean) => void;
}

/**
 * @description 异步弹窗状态机 Hook（纯受控模式）。
 *   管理 loading 状态，通过 { resolve, reject, promise } 协议将控制权交给调用方。
 * @param {UseAsyncDialogOptions} options - 配置选项
 * @returns {{ loading, open, close, handleConfirm, handleCancel }}
 */
export const useAsyncDialog = (options: UseAsyncDialogOptions) => {
  const { closeOnReject = false, isShow, onShowChange } = options;

  /** 提交中 loading 状态 */
  const loading = shallowRef(false);

  /**
   * @description 打开弹窗
   * @returns {void}
   */
  const open = () => {
    onShowChange(true);
  };

  /**
   * @description 关闭弹窗（loading 中不可关闭）
   * @returns {void}
   */
  const close = () => {
    if (loading.value) return;
    onShowChange(false);
  };

  /**
   * @description 创建确认事件——resolve 关闭弹窗，reject 由 closeOnReject 决定是否关闭。
   *   副作用通过 promise.then/.catch 管理，resolve/reject 仅透传 settlement。
   * @param {Record<string, unknown>} payload - 业务数据
   * @returns {AsyncDialogConfirmEvent} 事件对象
   */
  const handleConfirm = <T extends Record<string, unknown> = Record<string, unknown>>(
    payload?: T
  ): AsyncDialogConfirmEvent<T> => {
    loading.value = true;

    const noop = () => {};
    let promiseResolve: () => void = noop;
    let promiseReject: () => void = noop;
    const promise = new Promise<void>((res, rej) => {
      promiseResolve = res;
      promiseReject = rej;
    });

    // 副作用链：分叉消费，不影响调用方 await event.promise
    promise
      .then(() => {
        loading.value = false;
        onShowChange(false);
      })
      .catch(() => {
        loading.value = false;
        if (closeOnReject) {
          onShowChange(false);
        }
      });

    return {
      payload: (payload ?? {}) as T,
      promise,
      resolve: promiseResolve,
      reject: promiseReject,
    };
  };

  /**
   * @description 取消操作（loading 中不可取消）
   * @returns {boolean} 是否成功取消
   */
  const handleCancel = (): boolean => {
    if (loading.value) return false;
    onShowChange(false);
    return true;
  };

  // 弹窗打开时重置 loading
  watch(isShow, val => {
    if (val) {
      loading.value = false;
    }
  });

  return {
    loading,
    open,
    close,
    handleConfirm,
    handleCancel,
  };
};
