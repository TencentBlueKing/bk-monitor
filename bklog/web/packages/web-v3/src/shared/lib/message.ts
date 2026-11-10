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

/** 消息提示直接调用 TDesign MessagePlugin。 */
import { MessagePlugin } from 'tdesign-vue-next';

type MessageContent = Parameters<typeof MessagePlugin>[0] extends infer T ? T extends { content?: infer C } ? C : string : string;

const show = (theme: 'error' | 'success' | 'info' | 'warning', message: MessageContent, duration = 3000) =>
  MessagePlugin[theme]({
    content: message,
    duration,
    zIndex: window.__bk_zIndex_manager?.nextMessageZIndex?.(),
  });

export const messageError = (message: MessageContent, delay = 3000, _ellipsisLine = 0) => show('error', message, delay);
export const messageSuccess = (message: MessageContent, delay = 3000, _ellipsisLine = 0) => show('success', message, delay);
export const messageInfo = (message: MessageContent, delay = 3000, _ellipsisLine = 0) => show('info', message, delay);
export const messageWarn = (message: MessageContent, delay = 3000, _ellipsisLine = 0) => show('warning', message, delay);
