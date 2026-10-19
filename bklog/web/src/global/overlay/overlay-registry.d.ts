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

import type {
  DialogVisibleHooks,
  DialogVisibleState,
  OverlayOpenOptions,
  OverlayRecord,
  OverlayRegisterOptions,
} from './overlay-types';

export const FALLBACK_ZINDEX_START: number;
export const OVERLAY_RULES: Readonly<Record<string, string>>;

export class OverlayRegistry {
  reset(): void;
  nextZIndex(): number;
  get(id: string): OverlayRecord | null;
  isOpen(id: string): boolean;
  getStack(): string[];
  collectAncestors(id: string): string[];
  register(id: string, options?: OverlayRegisterOptions): OverlayRecord;
  open(id: string, extra?: OverlayOpenOptions): OverlayRecord;
  hide(id: string): void;
  hideChildren(id: string): void;
  hideGroup(group: string, exceptId?: string): void;
  notifyAnchorLost(id: string): void;
  findParentIdByElement(el?: Element | null): string | null;
  isClickInsideRecord(event: { target?: EventTarget | null }, id: string): boolean;
  dispose(id: string): void;
}

export const overlayRegistry: OverlayRegistry;

export function isClickInsideClosest(event: { target?: EventTarget | null }, selectors?: string[]): boolean;
export function shouldHideOnOutsideClick(
  event: { target?: EventTarget | null },
  options?: { rootSelector?: string; ignoreSelector?: string },
): boolean;
export function isValidAnchorRect(rect?: { width?: number; height?: number } | null): boolean;
export function resolvePopperPlacementRect<T extends { width?: number; height?: number }>(rect?: T | null): T | null;
export function createDialogVisibleState(initial?: boolean, hooks?: DialogVisibleHooks): DialogVisibleState;
