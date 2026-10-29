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

import tippy, { type Instance, type Props } from 'tippy.js';

import PopInstanceUtil, { markBklogTippy } from '../../pop-instance-util';
import { createRawTippyLifecycle, overlayRegistry, resolvePopperPlacementRect } from '../overlay-registry';
import type { OverlayRegisterOptions } from '../overlay-types';

export interface OverlayTippyOptions extends OverlayRegisterOptions {
  id: string;
  tippy?: ConstructorParameters<typeof PopInstanceUtil>[0];
}

/**
 * 把现有 PopInstanceUtil 接到 Registry，不替换 tippy。
 * P1 热点调用点应走这里，而不是业务里直接 new PopInstanceUtil。
 */
const resolveTippyParentId = (options: OverlayTippyOptions, anchor?: Element | null) => {
  return options.parentId || overlayRegistry.findParentIdByElement(anchor) || undefined;
};

const openOverlayTippy = (options: OverlayTippyOptions, anchor?: Element | null) => {
  overlayRegistry.open(options.id, {
    anchor: anchor ?? null,
    parentId: resolveTippyParentId(options, anchor),
  });
};

export const createOverlayTippy = (options: OverlayTippyOptions) => {
  const tippyOptions = {
    ...(options.tippy?.tippyOptions ?? {}),
    onShow: (...args: any[]) => {
      const userResult = options.tippy?.tippyOptions?.onShow?.(...args);
      const instance = args[0];
      const anchor = instance?.reference ?? instance ?? null;
      openOverlayTippy(options, anchor);
      return userResult;
    },
    onHidden: (...args: any[]) => {
      options.tippy?.tippyOptions?.onHidden?.(...args);
      overlayRegistry.hide(options.id);
    },
  };
  const instance = new PopInstanceUtil({
    ...(options.tippy ?? {}),
    tippyOptions,
  });

  overlayRegistry.register(options.id, {
    ...options,
    type: options.type || 'popover',
    hide: () => instance.hide(),
  });

  return {
    instance,
    show(target?: HTMLElement, cancelHidding = false, immediate = false) {
      openOverlayTippy(options, target);
      instance.show(target, cancelHidding, immediate);
    },
    hide(delay?: number) {
      if (delay) {
        instance.hide(delay);
        return;
      }
      overlayRegistry.hide(options.id);
    },
    notifyAnchorLost() {
      overlayRegistry.notifyAnchorLost(options.id);
    },
    uninstall() {
      overlayRegistry.dispose(options.id);
      instance.uninstallInstance();
    },
    resolvePlacementRect: resolvePopperPlacementRect,
  };
};

export interface RawTippyOverlayOptions extends OverlayRegisterOptions {
  id: string;
}

/**
 * 包住检索目录里仍直接 tippy() 的调用点。返回值与 tippy() 相同，业务仍可 show/hide/destroy。
 */
export const createRawTippyOverlay = (
  target: Parameters<typeof tippy>[0],
  tippyOptions: Partial<Props> = {},
  overlayOptions: RawTippyOverlayOptions,
) => {
  const lifecycle = createRawTippyLifecycle(overlayOptions.id, overlayOptions);
  const created = tippy(target, {
    appendTo: () => document.body,
    ...tippyOptions,
    zIndex: tippyOptions.zIndex ?? lifecycle.nextZIndex(),
    onShow(instance: Instance) {
      if (lifecycle.onShow(instance.reference) === false) {
        return false;
      }
      const userResult = tippyOptions.onShow?.(instance);
      if (userResult === false) {
        lifecycle.onHidden();
        return false;
      }
      return userResult;
    },
    onHidden(instance: Instance) {
      lifecycle.onHidden();
      tippyOptions.onHidden?.(instance);
    },
    onDestroy(instance: Instance) {
      lifecycle.onDestroy();
      tippyOptions.onDestroy?.(instance);
    },
  });

  markBklogTippy(created);
  lifecycle.setInstance(created);
  return created;
};

export default createOverlayTippy;
