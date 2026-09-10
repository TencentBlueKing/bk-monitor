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

export const createIcon = (iconName: string, className: string) => {
  const iconEl = document.createElement('i');
  iconEl.className = `icon-monitor ${iconName} ${className}`;
  return iconEl;
};

const createMenuItem = (
  icon: string,
  label: string,
  onClick?: () => void,
  options?: {
    disabled?: boolean;
  }
) => {
  const item = document.createElement('li');
  item.className = 'selection-decoder-menu-item';

  const textEl = document.createElement('span');
  textEl.textContent = label;

  item.append(createIcon(icon, 'selection-decoder-menu-icon'), textEl);

  if (options?.disabled) {
    item.classList.add('is-disabled');
    item.setAttribute('aria-disabled', 'true');
    return item;
  }

  item.addEventListener('click', event => {
    event.stopPropagation();
    onClick?.();
  });
  return item;
};

export const createMenuContent = (
  text: string,
  onCopy: (text: string) => void,
  onDecode: (text: string) => void,
  options?: {
    canDecode?: boolean;
  }
) => {
  const canDecode = options?.canDecode !== false;
  const menu = document.createElement('ul');
  menu.className = 'selection-decoder-menu';
  menu.append(
    createMenuItem('icon-mc-copy', t('复制'), () => {
      onCopy(text);
    }),
    createMenuItem(
      'icon-mc-decode',
      canDecode ? t('自动解码') : t('自动解码（未识别到可解码内容）'),
      () => {
        onDecode(text);
      },
      { disabled: !canDecode }
    )
  );
  return menu;
};

const createDecodeButton = (label: string, className: string, onClick: () => void) => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = className;
  button.textContent = label;
  button.addEventListener('click', event => {
    event.stopPropagation();
    onClick();
  });
  return button;
};

export const createDecodeContent = (decoded: string, onCopy: (text: string) => void, onClose: () => void) => {
  const wrap = document.createElement('div');
  wrap.className = 'selection-decoder-decode';

  const closeBtn = createIcon('icon-mc-close', 'selection-decoder-decode-close');
  closeBtn.addEventListener('click', event => {
    event.stopPropagation();
    onClose();
  });

  const header = document.createElement('div');
  header.className = 'selection-decoder-decode-header';

  const title = document.createElement('span');
  title.className = 'selection-decoder-decode-title';
  title.textContent = t('解码');
  header.append(title);

  const body = document.createElement('div');
  body.className = 'selection-decoder-decode-body';
  body.textContent = `${t('解码结果')}：${decoded}`;

  const footer = document.createElement('div');
  footer.className = 'selection-decoder-decode-footer';
  footer.append(
    createDecodeButton(t('复制'), 'selection-decoder-decode-btn is-primary', () => {
      onCopy(decoded);
    }),
    createDecodeButton(t('关闭'), 'selection-decoder-decode-btn', () => {
      onClose();
    })
  );

  wrap.append(closeBtn, header, body, footer);
  return wrap;
};

export const createMessageContent = (message: string, theme: 'error' | 'success', onClose: () => void) => {
  const wrap = document.createElement('div');
  wrap.className = `selection-decoder-message is-${theme}`;

  const content = document.createElement('div');
  content.className = 'selection-decoder-message-content';

  const textEl = document.createElement('span');
  textEl.textContent = message;
  content.append(
    createIcon(theme === 'success' ? 'icon-mc-check-fill' : 'icon-mc-close-fill', 'selection-decoder-message-icon'),
    textEl
  );

  const closeBtn = createIcon('icon-mc-close', 'selection-decoder-message-close');
  closeBtn.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    onClose();
  });

  wrap.append(content, closeBtn);
  return wrap;
};
