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

const TRIGGER_SELECTOR = '.date-content';
const CONTENT_SELECTOR = '.__date-tooltips__, .time-range-tips-content';
const POPOVER_MARK = '__bk-date-picker-popover__';

type TippyLike = {
  hide?: () => void;
};

type TippyHost = Element & {
  _tippy?: TippyLike;
  $tippy?: TippyLike;
};

/**
 * Hide the resolved-time hover tippy without touching its content node.
 * Setting display:none on `.__date-tooltips__` leaves an empty black shell
 * that cannot show content or close on later hovers.
 */
export function hideResolvedTimeTooltip(scope?: ParentNode) {
  const doc = typeof document === 'undefined' ? undefined : document;
  const local = scope ?? doc;
  if (!local?.querySelectorAll) {
    return;
  }

  const instances = new Set<TippyLike>();
  collectTriggerInstances(local, instances);
  collectPopperInstances(doc ?? local, instances);
  instances.forEach((instance) => {
    if (typeof instance.hide === 'function') {
      instance.hide();
    }
  });

  syncDatePickerHoverState(local);
}

function collectTriggerInstances(scope: ParentNode, instances: Set<TippyLike>) {
  scope.querySelectorAll(TRIGGER_SELECTOR).forEach((el) => {
    const instance = getTippy(el as TippyHost);
    if (instance) {
      instances.add(instance);
    }
  });
}

function collectPopperInstances(scope: ParentNode, instances: Set<TippyLike>) {
  if (!scope?.querySelectorAll) {
    return;
  }
  scope.querySelectorAll('[data-tippy-root]').forEach((popper) => {
    if (!popper.querySelector(CONTENT_SELECTOR)) {
      return;
    }
    if (String((popper as Element).className || '').includes(POPOVER_MARK)) {
      return;
    }
    const instance = getTippy(popper as TippyHost);
    if (instance) {
      instances.add(instance);
    }
  });
}

function syncDatePickerHoverState(scope: ParentNode) {
  const EventCtor = typeof MouseEvent !== 'undefined' ? MouseEvent : typeof Event !== 'undefined' ? Event : null;
  if (!EventCtor) {
    return;
  }
  scope.querySelectorAll(TRIGGER_SELECTOR).forEach((el) => {
    el.dispatchEvent(new EventCtor('mouseleave', { bubbles: true }));
  });
}

function getTippy(host: TippyHost) {
  return host._tippy || host.$tippy;
}
