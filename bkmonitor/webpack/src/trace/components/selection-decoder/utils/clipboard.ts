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

const t = (key: string) => window.i18n.t(key) as string;

const COPY_FALLBACK_STYLE =
  'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;margin:0;border:none;outline:none;box-shadow:none;background:transparent;opacity:0;font-size:12pt;';

const isAppleTouchDevice = () =>
  /ipad|ipod|iphone/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

const canUseClipboardApi = () =>
  typeof navigator !== 'undefined' && typeof navigator.clipboard?.writeText === 'function' && !!window.isSecureContext;

/**
 * execCommand 回退：覆盖旧版浏览器、非 HTTPS，以及 iOS 对隐藏 textarea 的限制
 */
const copyByExecCommand = (text: string): boolean => {
  if (typeof document.execCommand !== 'function') {
    return false;
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.setAttribute('aria-hidden', 'true');
  textarea.style.cssText = COPY_FALLBACK_STYLE;

  const selection = document.getSelection();
  const selectedRange = selection?.rangeCount ? selection.getRangeAt(0) : null;

  document.body.appendChild(textarea);

  if (isAppleTouchDevice()) {
    textarea.contentEditable = 'true';
    textarea.readOnly = false;
    const range = document.createRange();
    range.selectNodeContents(textarea);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
    textarea.setSelectionRange(0, text.length);
    textarea.focus();
  } else {
    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, text.length);
  }

  let success = false;
  try {
    success = document.execCommand('copy');
  } catch {
    success = false;
  }

  textarea.remove();

  if (selectedRange && selection) {
    selection.removeAllRanges();
    selection.addRange(selectedRange);
  }

  return success;
};

/**
 * 复制文本到剪切板，优先 Clipboard API，失败后回退 execCommand
 */
export const copyText = async (text: string): Promise<void> => {
  if (canUseClipboardApi()) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Clipboard API 可能因权限 / 失焦失败，继续走兼容回退
    }
  }

  if (copyByExecCommand(text)) {
    return;
  }

  throw new Error(t('复制失败，请手动复制'));
};
