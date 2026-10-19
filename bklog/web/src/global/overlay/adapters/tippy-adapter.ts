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

import PopInstanceUtil from '../../pop-instance-util';
import { overlayRegistry, resolvePopperPlacementRect } from '../overlay-registry';
import type { OverlayRegisterOptions } from '../overlay-types';

export interface OverlayTippyOptions extends OverlayRegisterOptions {
  id: string;
  tippy?: ConstructorParameters<typeof PopInstanceUtil>[0];
}

/**
 * 把现有 PopInstanceUtil 接到 Registry，不替换 tippy。
 * P1 热点调用点应走这里，而不是业务里直接 new PopInstanceUtil。
 */
export const createOverlayTippy = (options: OverlayTippyOptions) => {
  const instance = new PopInstanceUtil(options.tippy ?? {});

  overlayRegistry.register(options.id, {
    ...options,
    type: options.type || 'popover',
    hide: () => instance.hide(),
  });

  return {
    instance,
    show(target?: HTMLElement, cancelHidding = false, immediate = false) {
      overlayRegistry.open(options.id, { anchor: target ?? null });
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

export default createOverlayTippy;
