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
import { random } from '@/common/util';
import { throttle } from 'lodash-es';

import type { VueConstructor } from 'vue';
import type { DirectiveBinding, DirectiveOptions } from 'vue/types/options';

let insertedEl: IDragHtmlElement = null;

// 缓存拖拽宿主
export type MapType<T extends string> = { [key in T]?: IDragHtmlElement };
const insertedElMap: MapType<string> = {};

interface IBindValue {
  style: object; // 拖拽按钮样式
  maxWidth: number; // 最大宽度
  minWidth: number; // 最小宽度
  defaultWidth: number; // 默认宽度
  isShow: boolean; // 是否展示
  autoHidden: boolean; // 超出最小宽度时是否自动隐藏
  theme: 'normal' | 'simple'; // 拖拽按钮主题
  placement: 'left' | 'right'; // 拖拽侧栏的位置 默认left
  onHidden?: () => void; // 隐藏回调
  onWidthChange?: (width: number) => void; // 宽度更新
}
interface IDragHtmlElement extends HTMLElement {
  _bk_log_drag: {
    el: HTMLDivElement;
    value: IBindValue;
    dragKey: string;
  };
}

/** 处理配置默认值 */
const getBindValue = (data: IBindValue): IBindValue => {
  const { style = {}, theme = 'normal', placement = 'left' } = data;

  return {
    ...data,
    style,
    theme,
    placement,
  };
};

const handleMouseMove = throttle((event: MouseEvent) => {
  if (!insertedEl) {
    return;
  }
  const { maxWidth, minWidth, placement, autoHidden, onHidden, onWidthChange } = getBindValue(
    insertedEl._bk_log_drag.value as IBindValue,
  );
  const rect = insertedEl.getBoundingClientRect();
  let width = placement === 'left' ? event.clientX - rect.left : rect.right - event.clientX;
  // 最大最小值限制
  if (maxWidth && width > maxWidth) {
    width = maxWidth;
  } else if (width < minWidth) {
    width = autoHidden ? 0 : minWidth;
    if (autoHidden) {
      width = 0;
    } else {
      width = minWidth;
    }
    onHidden?.();
  }

  // 超出最小宽度时自动隐藏
  if (width <= 0) {
    insertedEl.style.display = 'none';
    onWidthChange?.(0);
  } else {
    insertedEl.style.width = `${width}px`;
    insertedEl._bk_log_drag.el.style.left = `${width - 10}px`;
    onWidthChange?.(width);
  }
}, 60);

const handleMouseUp = () => {
  document.body.style.cursor = '';
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
  document.onselectstart = null;
  document.ondragstart = null;
};

const dragMouseDown = (evt: MouseEvent) => {
  const key = (evt.target as HTMLElement).dataset.dragKey;
  insertedEl = insertedElMap[key];
  document.onselectstart = () => false;
  document.ondragstart = () => false;

  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};

const logDrag: DirectiveOptions = {
  inserted(el: IDragHtmlElement, bind: DirectiveBinding) {
    const key = random(8);
    // 设置父元素样式
    el.style.cssText = `
        ${el.style.cssText};
        height: 100%;
        position: relative;
    `;
    insertedEl = el;
    insertedElMap[key] = el;

    const { style = {}, theme } = bind.value as IBindValue;

    // 创建拖拽DOM
    const dragEle = document.createElement('div');
    dragEle.dataset.dragKey = key;
    dragEle.className = theme === 'simple' ? 'bk-log-drag-simple' : 'bk-log-drag';
    dragEle.style.cssText = Object.keys(style).reduce((pre, keyParam) => {
      let savePre = pre;
      savePre += `${keyParam}: ${style[keyParam]};`;
      return savePre;
    }, '');
    dragEle.style.left = `${insertedEl.getBoundingClientRect().width - 10}px`;
    el.appendChild(dragEle);

    // 绑定事件
    dragEle.addEventListener('mousedown', dragMouseDown);

    el._bk_log_drag = {
      el: dragEle,
      value: bind.value,
      dragKey: key,
    };
  },

  update(el: IDragHtmlElement, bind: DirectiveBinding) {
    el._bk_log_drag.value = bind.value;
    const { defaultWidth, maxWidth, minWidth, isShow, onWidthChange } = getBindValue(bind.value as IBindValue);
    const curInsertedEl = insertedElMap[el._bk_log_drag.dragKey];
    const isHidden = curInsertedEl.getAttribute('is-hidden');
    // 展开默认宽度
    if (defaultWidth <= maxWidth && defaultWidth >= minWidth && isShow && isHidden === 'true') {
      curInsertedEl.style.width = `${defaultWidth}px`;
      curInsertedEl.setAttribute('is-hidden', 'false');
      el._bk_log_drag.el.style.left = `${insertedEl.getBoundingClientRect().width - 10}px`;
      onWidthChange?.(defaultWidth);
    }
    if (!isShow) {
      curInsertedEl.setAttribute('is-hidden', 'true');
      onWidthChange?.(defaultWidth);
    }
  },

  unbind(el: IDragHtmlElement) {
    const { dragKey } = el._bk_log_drag;
    // 移除事件和删除DOM
    el._bk_log_drag.el.removeEventListener('mousedown', dragMouseDown);
    el.removeChild(el._bk_log_drag.el);
    insertedEl = null;
    delete insertedElMap[dragKey];
    el._bk_log_drag = undefined;
  },
};

export default {
  install: (Vue: VueConstructor) => Vue.directive('log-drag', logDrag),
  directive: logDrag,
};
