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

import { onBeforeUnmount, onMounted } from 'vue';
import type { ShallowRef } from 'vue';

/** pointerEvents 恢复延迟（ms） */
const POINTER_EVENTS_RESTORE_DELAY = 600;

/** 组件 ref（.$el 取 DOM） */
type ComponentRef = ShallowRef<null | { $el: HTMLElement }>;
/** 原生 DOM 的 ref */
type DomRef = ShallowRef<HTMLElement | null>;
interface ResolveElementOptions {
  /** 查找作用域的根元素（仅当 target 为 CSS 选择器字符串时生效），不传则在 document 全局查找 */
  root?: TargetElementType;
}

/** 目标元素类型：组件 ref / 原生 DOM 的 ref / DOM 元素 / CSS 选择器字符串 */
type TargetElementType = ComponentRef | DomRef | HTMLElement | string;

interface UseTableScrollOptimizeOptions {
  /** addEventListener 的配置项（如 { passive: true }），默认 { passive: true } */
  listenerOptions?: AddEventListenerOptions;
  /**
   * 查找滚动容器的作用域根元素（组件 ref / 原生 DOM 的 ref / CSS 选择器 / DOM 元素），
   * 不传则在 document 全局查找。用于避免多表格页面取到错误的 .t-table__content。
   */
  rootElement?: TargetElementType;
  /** 滚动容器：传字符串时在 rootElement 作用域内查找；也可直接传 DOM 元素 / ref */
  scrollContainerElement: TargetElementType;
  /** 需要优化 pointerEvents 的目标元素（可选，如无需优化可不传） */
  targetElement?: TargetElementType;
  /** 滚动时的额外回调（如隐藏 popover、触底加载），接收原始 scroll Event */
  onScroll?: (event: Event) => void;
}

/**
 * @description 解析目标元素为 HTMLElement
 * @param target - 目标元素（组件 ref / 原生 DOM 的 ref / CSS 选择器 / DOM 元素）
 * @param {ResolveElementOptions} [options] - 配置项
 * @param {TargetElementType} [options.root] - 查找作用域的根元素，仅当 target 为选择器字符串时生效
 * @returns 解析后的 HTMLElement 或 null
 */
const resolveElement = (target: TargetElementType, options: ResolveElementOptions = {}): HTMLElement | null => {
  if (!target) return null;
  if (target instanceof HTMLElement) return target;
  if (typeof target === 'string') {
    const root = resolveElement(options.root) ?? document;
    return root.querySelector<HTMLElement>(target);
  }
  const value = (target as ComponentRef | DomRef).value;
  if (value instanceof HTMLElement) return value;
  if (value && (value as { $el?: HTMLElement }).$el instanceof HTMLElement) {
    return (value as { $el: HTMLElement }).$el;
  }
  return null;
};

/**
 * @description 表格滚动优化 Composable，在外层容器滚动时禁用目标元素 pointerEvents 以提升滚动性能，
 *              并在滚动结束后恢复。同时支持滚动时触发额外回调（如隐藏 popover、触底加载）。
 * @param {UseTableScrollOptimizeOptions} options - 配置项
 * @param {TargetElementType} [options.targetElement] - 需要优化 pointerEvents 的目标元素，可省略
 * @param {TargetElementType} [options.rootElement] - 查找滚动容器的作用域根元素，可省略
 * @param {TargetElementType} options.scrollContainerElement - 滚动容器（字符串时在 rootElement 作用域内查找，也可直接传 DOM 元素 / ref）
 * @param {(event: Event) => void} [options.onScroll] - 滚动时的额外回调，接收原始 scroll Event
 * @param {AddEventListenerOptions} [options.listenerOptions] - addEventListener 的配置项，默认 { passive: true }
 */
export const useTableScrollOptimize = (options: UseTableScrollOptimizeOptions) => {
  const { targetElement, onScroll, scrollContainerElement, rootElement, listenerOptions = { passive: true } } = options;

  /** 滚动容器元素 */
  let scrollContainerEl: HTMLElement = null;
  /** 滚动结束后回调逻辑执行计时器 */
  let scrollPointerEventsTimer: null | ReturnType<typeof setTimeout> = null;

  /**
   * @description 配置目标元素是否能够触发事件
   * @param val - pointer-events 值
   */
  const updatePointerEvents = (val: 'auto' | 'none') => {
    const el = resolveElement(targetElement);
    if (!el) return;
    el.style.pointerEvents = val;
  };

  /**
   * @description 滚动触发事件
   * @param {Event} event - 原始 scroll 事件对象
   */
  const handleScroll = (event: Event) => {
    updatePointerEvents('none');
    onScroll?.(event);
    scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
    scrollPointerEventsTimer = setTimeout(() => {
      updatePointerEvents('auto');
    }, POINTER_EVENTS_RESTORE_DELAY);
  };

  /**
   * @description 添加滚动监听
   */
  const addScrollListener = () => {
    removeScrollListener();
    scrollContainerEl = resolveElement(scrollContainerElement, { root: rootElement });
    if (!scrollContainerEl) return;
    scrollContainerEl.addEventListener('scroll', handleScroll, listenerOptions);
  };

  /**
   * @description 移除滚动监听
   */
  const removeScrollListener = () => {
    if (!scrollContainerEl) return;
    scrollContainerEl.removeEventListener('scroll', handleScroll, listenerOptions);
    scrollContainerEl = null;
  };

  onMounted(() => {
    addScrollListener();
  });

  onBeforeUnmount(() => {
    scrollPointerEventsTimer && clearTimeout(scrollPointerEventsTimer);
    removeScrollListener();
  });
};
