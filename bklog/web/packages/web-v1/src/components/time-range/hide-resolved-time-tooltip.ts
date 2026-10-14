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

const RESOLVED_TIME_TOOLTIP_SELECTOR = '.__date-tooltips__, .time-range-tips-content';

type TippyLike = {
  hide?: () => void;
};

type TippyHost = Element & {
  _tippy?: TippyLike;
  style?: CSSStyleDeclaration;
};

/**
 * Close leftover @blueking/date-picker resolved-time tooltips.
 * The picker hides its panel on change but leaves the body-level tippy visible.
 */
export function hideResolvedTimeTooltip(root?: ParentNode) {
  const scope = root ?? (typeof document === 'undefined' ? undefined : document);
  if (!scope?.querySelectorAll) {
    return;
  }

  const seen = new Set<Element>();
  scope.querySelectorAll(RESOLVED_TIME_TOOLTIP_SELECTOR).forEach((content) => {
    const tippyRoot = ((content.closest?.('[data-tippy-root]') as TippyHost | null)
      || (content as TippyHost)) as TippyHost;
    if (seen.has(tippyRoot)) {
      return;
    }
    seen.add(tippyRoot);
    hideTippyHost(tippyRoot);
  });
}

function hideTippyHost(host: TippyHost) {
  if (typeof host._tippy?.hide === 'function') {
    host._tippy.hide();
    return;
  }
  if (host.style) {
    host.style.display = 'none';
  }
  if (typeof host.setAttribute === 'function') {
    host.setAttribute('aria-hidden', 'true');
  }
}
