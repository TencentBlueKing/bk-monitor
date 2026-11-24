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

/** 普通消息走 TDesign MessagePlugin；bkui 高级对象消息走 advanced-message 还原实现。 */
import { MessagePlugin } from 'tdesign-vue-next';

import {
  isAdvancedMessage,
  showAdvancedMessage,
  type AdvancedMessageOptions,
} from './advanced-message';

export { isAdvancedMessage, showAdvancedMessage };
export type { AdvancedMessage, AdvancedMessageAction, AdvancedMessageOptions } from './advanced-message';

type MessageContent =
  | string
  | Parameters<typeof MessagePlugin>[0]
  | AdvancedMessageOptions['message'];

type SimpleMessageContent = Parameters<typeof MessagePlugin>[0] extends infer T
  ? T extends { content?: infer C }
    ? C
    : string
  : string;

function isOptionsObject(value: unknown): value is AdvancedMessageOptions {
  return (
    !!value &&
    typeof value === 'object' &&
    ('message' in (value as Record<string, unknown>) || 'actions' in (value as Record<string, unknown>))
  );
}

const show = (theme: 'error' | 'success' | 'info' | 'warning', message: MessageContent, duration = 3000) => {
  if (isAdvancedMessage(message)) {
    return showAdvancedMessage({ message, theme, delay: duration });
  }
  if (isOptionsObject(message)) {
    const options = message as AdvancedMessageOptions;
    if (isAdvancedMessage(options.message)) {
      return showAdvancedMessage({ ...options, theme: options.theme ?? theme, delay: options.delay ?? duration });
    }
    return show(theme, options.message as MessageContent, options.delay ?? options.duration ?? duration);
  }
  return MessagePlugin[theme === 'info' ? 'info' : theme]({
    content: message as SimpleMessageContent,
    duration,
    zIndex: (
      window as unknown as { __bk_zIndex_manager?: { nextMessageZIndex?: () => number } }
    ).__bk_zIndex_manager?.nextMessageZIndex?.(),
  });
};

export const messageError = (message: MessageContent, delay = 3000, _ellipsisLine = 0) => show('error', message, delay);
export const messageSuccess = (message: MessageContent, delay = 3000, _ellipsisLine = 0) =>
  show('success', message, delay);
export const messageInfo = (message: MessageContent, delay = 3000, _ellipsisLine = 0) => show('info', message, delay);
export const messageWarn = (message: MessageContent, delay = 3000, _ellipsisLine = 0) =>
  show('warning', message, delay);

/** bk-magic-vue 兼容：`showMessage({ theme, message, delay })` / `showMessage(text, theme)`。 */
export const showMessage = (
  options: AdvancedMessageOptions | string,
  theme: 'error' | 'success' | 'info' | 'warning' = 'success',
) => {
  if (typeof options === 'string') return show(theme, options);
  const resolvedTheme = (options.theme as typeof theme) ?? theme;
  if (isAdvancedMessage(options.message)) {
    return showAdvancedMessage({ ...options, theme: resolvedTheme });
  }
  return show(resolvedTheme, options.message as MessageContent, options.delay ?? options.duration ?? 3000);
};

/** bk-magic-vue 兼容通知入口；高级对象同样走还原后的 Message。 */
export const showNotify = showMessage;
