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

import type { SelectionDecoderTarget } from './typing';

const MIN_DRAG_SIZE = 4;

let lastPointerDown: null | { x: number; y: number } = null;

const handleDocumentPointerDown = (event: PointerEvent) => {
  if (event.button !== 0) {
    return;
  }
  lastPointerDown = { x: event.clientX, y: event.clientY };
};

if (typeof document !== 'undefined') {
  document.addEventListener('pointerdown', handleDocumentPointerDown, true);
}

export const createDOMRect = (left: number, top: number, right: number, bottom: number) =>
  new DOMRect(left, top, Math.max(right - left, 0), Math.max(bottom - top, 0));

const isMeaningfulRect = (rect: DOMRect) => rect.width >= MIN_DRAG_SIZE || rect.height >= MIN_DRAG_SIZE;

const unionClientRects = (rects: ArrayLike<DOMRect>): DOMRect | null => {
  let left = Number.POSITIVE_INFINITY;
  let top = Number.POSITIVE_INFINITY;
  let right = Number.NEGATIVE_INFINITY;
  let bottom = Number.NEGATIVE_INFINITY;
  let hasValidRect = false;

  for (let index = 0; index < rects.length; index++) {
    const rect = rects[index];
    if (rect.width <= 0 && rect.height <= 0) {
      continue;
    }
    hasValidRect = true;
    left = Math.min(left, rect.left);
    top = Math.min(top, rect.top);
    right = Math.max(right, rect.right);
    bottom = Math.max(bottom, rect.bottom);
  }

  return hasValidRect ? createDOMRect(left, top, right, bottom) : null;
};

const resolveDragRect = (target?: SelectionDecoderTarget): DOMRect | null => {
  if (!(target instanceof MouseEvent) || !lastPointerDown) {
    return null;
  }

  return createDOMRect(
    Math.min(lastPointerDown.x, target.clientX),
    Math.min(lastPointerDown.y, target.clientY),
    Math.max(lastPointerDown.x, target.clientX),
    Math.max(lastPointerDown.y, target.clientY)
  );
};

export const resolveSelectionRect = (): null | { ancestor: Element; getRect: () => DOMRect } => {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
    return null;
  }

  const range = selection.getRangeAt(0);
  const ancestor = range.commonAncestorContainer;
  const unionRect = unionClientRects(range.getClientRects()) || range.getBoundingClientRect();
  if (!isMeaningfulRect(unionRect)) {
    return null;
  }

  return {
    ancestor: ancestor instanceof Element ? ancestor : ancestor.parentElement || document.body,
    getRect: () => unionClientRects(range.getClientRects()) || range.getBoundingClientRect(),
  };
};

export const resolveAnchorRect = (target?: SelectionDecoderTarget): DOMRect | null => {
  const dragRect = resolveDragRect(target);
  if (dragRect && isMeaningfulRect(dragRect)) {
    return dragRect;
  }

  const selectionRect = resolveSelectionRect();
  if (selectionRect) {
    return selectionRect.getRect();
  }

  return dragRect;
};

/**
 * 是否为有位移的划选。点击已选文本时选区往往仍在，需要靠指针位移排除。
 */
export const isPointerDragSelect = (event: MouseEvent): boolean => {
  const dragRect = resolveDragRect(event);
  return !!dragRect && isMeaningfulRect(dragRect);
};

/**
 * 是否应弹出划词菜单：有位移的划选，或双击 / 三击产生选区。
 * 纯单击已选文本时选区往往仍在，不能仅凭选区判断。
 */
export const isSelectionDecoderTrigger = (event: MouseEvent): boolean => {
  return event.detail >= 2 || isPointerDragSelect(event);
};
