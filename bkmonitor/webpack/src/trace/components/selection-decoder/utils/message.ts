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

import tippy, { type Instance } from 'tippy.js';

import { copyText } from './clipboard';
import { createMessageContent } from './dom';
import { createDOMRect } from './geometry';
import { hideSelectionDecoder } from './popover';

const t = (key: string) => window.i18n.t(key) as string;

/** 对齐 bkui-vue Message：默认 3s 关闭、距顶 30px、宽度 560 */
const MESSAGE_DELAY = 3000;
const MESSAGE_OFFSET_Y = 30;
const MESSAGE_WIDTH = 560;
/** 高于 Sideslider / 解码弹层（9999），避免顶部提示被遮挡 */
const MESSAGE_Z_INDEX = 10000;
const MESSAGE_FADE_DURATION = 200;

let messageInstance: Instance | null = null;
let messageTimer: null | ReturnType<typeof setTimeout> = null;

const clearMessageTimer = () => {
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
};

const startMessageTimer = () => {
  clearMessageTimer();
  messageTimer = setTimeout(() => {
    hideMessageTip();
  }, MESSAGE_DELAY);
};

const destroyMessageTip = () => {
  clearMessageTimer();
  const instance = messageInstance;
  messageInstance = null;
  instance?.destroy();
};

const hideMessageTip = () => {
  clearMessageTimer();
  messageInstance?.hide();
};

/** 强制按 bk-message 的方式钉在视口顶部居中，避免 Popper 算到侧栏/页面外 */
const pinMessageToViewport = (instance: Instance) => {
  const root = instance.popper;
  root.classList.add('selection-decoder-message-root');
  root.style.position = 'fixed';
  root.style.top = `${MESSAGE_OFFSET_Y}px`;
  root.style.left = '50%';
  root.style.transform = 'translateX(-50%)';
  root.style.zIndex = String(MESSAGE_Z_INDEX);
};

/**
 * 用 tippy 在页面顶部提示复制结果，样式与交互对齐 bkui-vue Message
 */
const showMessageTip = (message: string, theme: 'error' | 'success') => {
  hideSelectionDecoder();
  destroyMessageTip();

  if (typeof document === 'undefined') {
    return;
  }

  const handleResize = () => {
    if (messageInstance) {
      pinMessageToViewport(messageInstance);
    }
  };

  /**
   * 不要挂到 document.body：popper 会成为 reference 的子节点，
   * 视口坐标会被算到页面外，看起来像被侧栏挡住。
   */
  const messageReference = document.createElement('div');
  messageInstance = tippy(messageReference, {
    content: createMessageContent(message, theme, hideMessageTip),
    trigger: 'manual',
    placement: 'bottom',
    offset: [0, 0],
    arrow: false,
    interactive: true,
    hideOnClick: false,
    animation: 'message-fade',
    duration: MESSAGE_FADE_DURATION,
    theme: 'selection-decoder-message',
    appendTo: () => document.body,
    zIndex: MESSAGE_Z_INDEX,
    maxWidth: MESSAGE_WIDTH,
    getReferenceClientRect: () => {
      const cx = window.innerWidth / 2;
      return createDOMRect(cx, MESSAGE_OFFSET_Y, cx, MESSAGE_OFFSET_Y);
    },
    popperOptions: {
      strategy: 'fixed',
      modifiers: [
        { name: 'flip', enabled: false },
        { name: 'preventOverflow', enabled: false },
      ],
    },
    onMount(instance) {
      pinMessageToViewport(instance);
    },
    onShown(instance) {
      pinMessageToViewport(instance);
    },
    onShow(instance) {
      pinMessageToViewport(instance);
      instance.popper.addEventListener('mouseenter', clearMessageTimer);
      instance.popper.addEventListener('mouseleave', startMessageTimer);
      window.addEventListener('resize', handleResize);
      startMessageTimer();
    },
    onHidden(instance) {
      instance.popper.removeEventListener('mouseenter', clearMessageTimer);
      instance.popper.removeEventListener('mouseleave', startMessageTimer);
      window.removeEventListener('resize', handleResize);
      if (messageInstance === instance) {
        destroyMessageTip();
      }
    },
  });
  messageInstance.show();
  pinMessageToViewport(messageInstance);
};

/**
 * 复制文本到剪切板，并用 tippy Message 提示结果
 */
export const copyToClipboard = async (text: string) => {
  try {
    await copyText(text);
    showMessageTip(t('复制成功'), 'success');
  } catch (error) {
    const message = error instanceof Error && error.message ? error.message : t('复制失败，请手动复制');
    showMessageTip(message, 'error');
  }
};
