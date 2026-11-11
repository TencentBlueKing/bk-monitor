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
import { isRef, ref, type Ref } from 'vue';

import { overlayRegistry } from './overlay/overlay-registry';
import { Z_INDEX_LAYERS } from './overlay/z-index-manager.js';
import { debounce } from 'lodash-es';
import tippy, { type Props, type Placement, type Instance, MultipleTargets } from 'tippy.js';

import './pop-instance-util.scss';

type PopoverContent =
  | (() => HTMLElement | string | null | undefined)
  | HTMLElement
  | Ref<HTMLElement | null | undefined>
  | Ref<{ $el?: HTMLElement } | string | null | undefined>
  | string
  | null
  | undefined;
type PopInstanceUtilType = {
  refContent: PopoverContent;
  onShowFn: (instance: Instance | null) => boolean | void;
  onHiddenFn: (instance: Instance | null) => boolean | void;
  arrow: boolean;
  newInstance: boolean;
  tippyOptions: Partial<Props>;
  watchElement: Ref<HTMLElement | null | undefined>;
};

export const markBklogTippy = (instances: Instance | Instance[]) => {
  const instanceList = Array.isArray(instances) ? instances : [instances];
  instanceList.forEach((instance) => {
    instance.popper.classList.add('bklog-tippy');
  });
};

export default class PopInstanceUtil {
  private tippyInstance: Instance<Props> | null;
  private refContent: PopoverContent = ref(null);
  private onShowFn;
  private onHiddenFn;
  private arrow = true;
  private newInstance = true;
  private tippyOptions: Partial<Props> = {};
  private resizeObserver: ResizeObserver | null = null;

  private delayShowInstance;
  private watchElement: Ref<HTMLElement | null | undefined> = ref(null);
  private isShowing = false;
  private hiddenTimer: string | number | NodeJS.Timeout | null | undefined;
  private destroyingInstance: Instance<Props> | null = null;

  constructor({
    refContent,
    onShowFn,
    onHiddenFn,
    arrow = true,
    newInstance = true,
    tippyOptions = {},
    watchElement = ref(null), // 添加需要监视的元素，能在元素高度变化时，自动更新 pop
  }: Partial<PopInstanceUtilType>) {
    this.tippyInstance = null;
    this.refContent = refContent;
    this.onShowFn = onShowFn;
    this.onHiddenFn = onHiddenFn;
    this.arrow = arrow;
    this.newInstance = newInstance;
    this.tippyOptions = tippyOptions;
    this.watchElement = watchElement;
    this.isShowing = false;

    /**
     * 处理多次点击触发多次请求的事件
     */
    this.delayShowInstance = debounce(this.immediateShowInstance);
  }

  setIsShowing(isShowing: boolean) {
    this.isShowing = isShowing;
  }

  immediateShowInstance(target: EventTarget | MultipleTargets | null | undefined) {
    if (this.isShown()) {
      this.repositionTippyInstance();
      return;
    }

    this.initInistance(target);
    this.getTippyInstance()?.show();
  }

  // 初始化监听器
  onMounted() {
    // 在 onMounted 中判断 watchElement 是否存在
    if (this.watchElement?.value) {
      this.resizeObserver = new ResizeObserver(() => {
        this.repositionTippyInstance();
      });
      this.resizeObserver.observe(this.watchElement.value);
    }
  }

  onBeforeUnmount() {
    this.resizeObserver?.disconnect();
  }

  setContent(refContent: PopoverContent) {
    this.refContent = refContent;
  }

  setProps(props: Partial<Props>) {
    Object.assign(this.tippyOptions, props ?? {});
    this.tippyInstance?.setProps(props);
  }

  getTippyInstance() {
    return this.tippyInstance;
  }

  isInstanceShowing() {
    return this.isShowing;
  }

  isShown() {
    return this.getTippyInstance()?.state?.isShown ?? false;
  }

  /**
   * 判断 tippy 实例是否正在 uninstallInstance 中被销毁。
   * 重建实例时旧实例 unmount 会同步触发 onHidden，调用方可据此忽略旧实例的事件。
   */
  isDestroyingInstance(instance?: Instance<Props> | null) {
    return Boolean(instance) && instance === this.destroyingInstance;
  }

  uninstallInstance = () => {
    this.delayShowInstance?.cancel?.();
    this.cancelHide();
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    if (this.tippyInstance) {
      this.destroyingInstance = this.tippyInstance;
      try {
        this.tippyInstance?.hide();
        this.tippyInstance?.unmount();
        this.tippyInstance?.destroy();
        this.tippyInstance = null;
      } finally {
        this.destroyingInstance = null;
      }
    }
  };

  getContent() {
    if (isRef(this.refContent)) {
      return this.refContent.value;
    }

    if (typeof this.refContent === 'function') {
      return this.refContent();
    }

    return this.refContent;
  }

  getDefaultOption() {
    const content = this.getContent();
    return {
      arrow: this.arrow,
      content: (content as any)?.$el ?? content,
      trigger: 'manual',
      theme: 'log-light',
      placement: 'bottom-start' as Placement,
      interactive: true,
      maxWidth: 800,
      zIndex: Z_INDEX_LAYERS.DROPDOWN,
      onShow: () => {
        if (this.tippyOptions?.zIndex == null) {
          this.tippyInstance?.setProps({ zIndex: overlayRegistry.nextZIndex() });
        }
        this.onMounted();
        return this.onShowFn?.(this.tippyInstance) ?? true;
      },
      onShown: () => {
        this.setIsShowing(true);
      },
      onHide: () => {
        this.setIsShowing(false);
        if (!(this.onHiddenFn?.(this.tippyInstance) ?? true)) {
          return false;
        }

        this.onBeforeUnmount();
      },
      onHidden: () => {
        this.setIsShowing(false);
      },
    };
  }

  getMergeTippyOptions(): Partial<Props> {
    const options: Record<string, unknown> = { ...this.getDefaultOption() };
    const custom = this.tippyOptions as Record<string, unknown>;
    for (const key of Object.keys(custom)) {
      const next = custom[key];
      if (typeof next === 'function') {
        const previous = options[key];
        // Preserve lifecycle chaining, and pass positioning callbacks through unchanged.
        options[key] =
          typeof previous === 'function'
            ? (...args: unknown[]) => {
                Reflect.apply(next, this.tippyOptions, args);
                return Reflect.apply(previous, undefined, args);
              }
            : next;
      } else if (next !== undefined && next !== null) {
        options[key] = next;
      }
    }
    return options as Partial<Props>;
  }

  initInistance(target: HTMLElement | MultipleTargets | null) {
    if (this.newInstance) {
      this.uninstallInstance();
    }

    const content = this.getContent();
    if (this.tippyInstance === null && content) {
      this.tippyInstance = tippy(target, this.getMergeTippyOptions()) as any;
      markBklogTippy(this.tippyInstance);
    }
  }

  show(target: EventTarget | null | undefined, cancelHidding = false, immediate = false) {
    if (this.isShowing) {
      return;
    }

    cancelHidding && this.cancelHide();
    if (!immediate) {
      this.delayShowInstance(target);
      return;
    }

    this.immediateShowInstance(target);
  }

  repositionTippyInstance(force?: boolean | undefined) {
    if (this.getTippyInstance()?.state.isShown || force) {
      this.getTippyInstance()?.popperInstance?.update();
    }

    return this.getTippyInstance()?.state.isShown;
  }

  hide(delay?: number | undefined) {
    this.delayShowInstance.cancel();
    if (delay) {
      // 清理掉之前的隐藏定时器，保证只有一个定时器
      this.cancelHide();
      this.hiddenTimer = setTimeout(() => {
        this.getTippyInstance()?.hide();
      }, delay);

      return;
    }

    this.getTippyInstance()?.hide();
  }

  cancelHide() {
    this.hiddenTimer && clearTimeout(this.hiddenTimer);
    this.hiddenTimer = null;
  }
}
