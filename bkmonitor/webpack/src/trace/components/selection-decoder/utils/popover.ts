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

import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import { createDOMRect, resolveAnchorRect, resolveSelectionRect } from './geometry';
import {
  type ResolvedTippyProps,
  type SelectionDecoderPlacement,
  type SelectionDecoderTarget,
  DEFAULT_PLACEMENT,
} from './typing';

const VERTICAL_PLACEMENT_OFFSET = 20;

let popoverInstance: Instance | null = null;
let popoverContent: HTMLElement | null = null;
let lastTippyProps: null | ResolvedTippyProps = null;
let lastPlacement: SelectionDecoderPlacement = DEFAULT_PLACEMENT;

const getPlacementOffset = (placement: SelectionDecoderPlacement): [number, number] => {
  if (placement === 'top' || placement === 'bottom') {
    return [0, VERTICAL_PLACEMENT_OFFSET];
  }
  return [0, 0];
};

const resolveReferenceFromTarget = (target?: SelectionDecoderTarget): null | SingleTarget => {
  if (target instanceof MouseEvent) {
    return ((target.currentTarget as Element) || document.body) as SingleTarget;
  }
  if (target instanceof Element) {
    return target as SingleTarget;
  }
  return null;
};

const resolveTippyProps = (target?: SelectionDecoderTarget): null | ResolvedTippyProps => {
  const selectionRect = resolveSelectionRect();
  const anchorRect = resolveAnchorRect(target);
  const reference =
    resolveReferenceFromTarget(target) ||
    (selectionRect?.ancestor as SingleTarget | undefined) ||
    (typeof document !== 'undefined' ? (document.body as SingleTarget) : null);

  if (!reference) {
    return null;
  }

  if (anchorRect) {
    return {
      reference,
      getReferenceClientRect: () => anchorRect,
    };
  }

  if (target instanceof MouseEvent) {
    const { clientX, clientY } = target;
    return {
      reference,
      getReferenceClientRect: () => createDOMRect(clientX, clientY, clientX, clientY),
    };
  }

  if (target instanceof Element) {
    return { reference };
  }

  return null;
};

/**
 * 无划选 / 锚点时，将弹窗挂到视口中央
 */
const resolveCenteredTippyProps = (): null | ResolvedTippyProps => {
  if (typeof document === 'undefined') {
    return null;
  }

  return {
    reference: document.body as SingleTarget,
    getReferenceClientRect: () => {
      const cx = window.innerWidth / 2;
      const cy = window.innerHeight / 2;
      return createDOMRect(cx, cy, cx, cy);
    },
  };
};

const destroyPopover = () => {
  const instance = popoverInstance;
  popoverInstance = null;
  if (instance) {
    instance.hide();
    instance.destroy();
  }
  popoverContent?.remove();
  popoverContent = null;
};

export const showPopover = (
  content: HTMLElement,
  options?: {
    hideOnClick?: boolean;
    interactive?: boolean;
    theme?: string;
  }
) => {
  if (!lastTippyProps) {
    return;
  }

  destroyPopover();
  popoverContent = content;
  popoverInstance = tippy(lastTippyProps.reference, {
    content,
    trigger: 'manual',
    placement: lastPlacement,
    offset: getPlacementOffset(lastPlacement),
    theme: options?.theme ?? 'light selection-decoder-popover',
    interactive: options?.interactive ?? true,
    hideOnClick: options?.hideOnClick ?? true,
    appendTo: () => document.body,
    zIndex: 9999,
    ...(lastTippyProps.getReferenceClientRect ? { getReferenceClientRect: lastTippyProps.getReferenceClientRect } : {}),
    onHidden(instance) {
      if (popoverInstance !== instance) {
        return;
      }
      hideSelectionDecoder();
    },
  });
  popoverInstance.show();
};

export const prepareDecoderPopover = (
  text: string,
  target?: SelectionDecoderTarget,
  placement: SelectionDecoderPlacement = DEFAULT_PLACEMENT,
  options?: {
    fallbackCenter?: boolean;
  }
): boolean => {
  if (typeof text !== 'string' || !text) {
    return false;
  }

  const tippyProps = resolveTippyProps(target) || (options?.fallbackCenter ? resolveCenteredTippyProps() : null);
  if (!tippyProps) {
    return false;
  }

  lastTippyProps = tippyProps;
  lastPlacement = placement;
  return true;
};

/**
 * 关闭并销毁当前解码器 tippy 弹窗
 */
export const hideSelectionDecoder = () => {
  lastTippyProps = null;
  lastPlacement = DEFAULT_PLACEMENT;
  destroyPopover();
};
