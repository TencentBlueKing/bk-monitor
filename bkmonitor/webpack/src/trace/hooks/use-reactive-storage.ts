/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for the蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
 * WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

/**
 * useReactiveStorage — 修复 @vueuse/core useStorage 的动态 key/defaults 同步缺陷
 *
 * 背景：
 *   useStorage 内部将 defaults 通过 toValue() 缓存为 rawInit 常量，
 *   当 key 动态变化时触发 update() → read()，read() 仍使用闭包中的旧 rawInit，
 *   导致 key 变更后 defaults 无法同步更新。
 *
 * 方案：
 *   当 key 或 defaults 变化时，销毁旧 useStorage 实例并创建新实例，
 *   通过 customRef 将新旧实例的 ref 透传为统一的响应式引用，
 *   对外接口与 useStorage 完全一致（返回 RemovableRef<T>），实现无感替换。
 *
 * 防递归策略：
 *   仅监听 key 变化触发重建。defaults 变化不触发重建，原因：
 *   1. defaults 通常为 Ref/shallowRef，其 .value 赋新对象后引用必然变化，
 *      而 useReactiveStorage 重建实例又会触发消费者写回 → 间接触发 defaults 再次变化 → 无限递归。
 *   2. defaults 变化的场景通常伴随 key 变化（如 alarmService 切换），
 *      key 变化已能覆盖绝大部分业务场景。
 *   3. key 不变但 defaults 变化的场景（如同一 service 下调整默认列），
 *      useStorage 内部 read() 使用 rawInit 仅在 storage 为空时生效，
 *      已有持久化数据时 defaults 变化不影响实际值，不重建也无副作用。
 */

import { customRef, effectScope, onScopeDispose, toValue, watch } from 'vue';

import { type RemovableRef, type StorageLike, type UseStorageOptions, useStorage } from '@vueuse/core';

import type { MaybeRefOrGetter } from '@vueuse/shared';

/** useReactiveStorage 扩展选项（当前与 UseStorageOptions 一致，预留扩展点） */
export type UseReactiveStorageOptions<T> = UseStorageOptions<T>;

export function useReactiveStorage<T>(
  key: MaybeRefOrGetter<string>,
  defaults: MaybeRefOrGetter<T>,
  storage?: StorageLike,
  options?: UseReactiveStorageOptions<T>
): RemovableRef<T> {
  /** 在 effectScope 内创建 useStorage 实例，并桥接其内部变化到 outerRef */
  function createInnerInstance(currentKey: string): { ref: RemovableRef<T>; scope: ReturnType<typeof effectScope> } {
    const scope = effectScope();
    const ref = scope.run(() => {
      // 结构化克隆 defaults：useStorage 内部 toValue(defaults) 获取的是对象引用，
      // 若不拷贝，outerRef.value 与外部 defaults 将共享同一对象，外部修改会意外联动内部状态
      // 传入 currentKey（字符串值）而非响应式 key：避免 useStorage 内部 watch key 导致
      // key 变更时 useStorage 先于外层 key watch 触发，产生中间态通知
      const storageRef = useStorage<T>(currentKey, () => structuredClone(toValue(defaults)), storage, options);
      // 桥接：innerRef 值变化（如 storage 事件、内部逻辑、外部 set）→ 同步通知 outerRef 消费者
      // 使用 flush: 'sync' 确保通知在当前 tick 内完成，避免 set() 后同步读取 computed 得到过期缓存值
      watch(storageRef, () => notifyChange?.(), { flush: 'sync' });
      return storageRef;
    }) as RemovableRef<T>;
    return { ref, scope };
  }

  let { ref: innerRef, scope: innerScope } = createInnerInstance(toValue(key));

  /** customRef 的 trigger 函数引用，保存在外层作用域供 watch 使用 */
  let notifyChange: (() => void) | null = null;

  const outerRef = customRef<T>((track, trigger) => {
    notifyChange = trigger;
    return {
      get() {
        track();
        return innerRef.value;
      },
      set(newValue) {
        // 预校验序列化：防止不可序列化的值（循环引用、BigInt 等）写入 innerRef 后，
        // useStorage 内部 watch 异步写回 storage 时序列化失败，导致 ref 已更新但 storage 未写入的不一致
        try {
          (options?.serializer?.write ?? JSON.stringify)(newValue);
        } catch {
          return;
        }
        innerRef.value = newValue;
      },
    };
  });

  /** 当 key 变化时，重建 useStorage 实例（不监听 defaults，避免无限递归） */
  watch(
    () => toValue(key),
    (newKey, oldKey) => {
      if (newKey === oldKey) return;

      // 先销毁旧实例的 effectScope，释放其内部所有副作用（watch、storage 事件监听等）
      // 注：stop() 到 innerRef 重新赋值之间是同步的，JS 单线程保证无竞态窗口
      innerScope.stop();
      // 重建实例：新 key + 新 defaults → useStorage 内部 toValue(defaults) 获取最新值
      const instance = createInnerInstance(newKey);
      innerScope = instance.scope;
      innerRef = instance.ref;
      notifyChange?.();
    }
  );

  // 当宿主 scope（组件 setup / effectScope）被销毁时，清理内部资源：
  // 1. 停止 innerScope → 释放 useStorage 实例内的 watch、storage 事件监听等
  // 2. 置空 notifyChange → 防止残留副作用在 scope 销毁后调用 customRef.trigger() 导致 "unmounted component" 警告
  onScopeDispose(() => {
    innerScope.stop();
    notifyChange = null;
  });

  return outerRef as RemovableRef<T>;
}
