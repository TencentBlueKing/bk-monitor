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
import type { VueConstructor } from 'vue';

import { random } from '../utils/utils';

import type { DirectiveBinding, DirectiveOptions } from 'vue/types/options';

let insertedEl: IDragHtmlElement = null;

// 缓存拖拽宿主
export type MapType<T extends string> = { [key in T]?: IDragHtmlElement };
const insertedElMap: MapType<string> = {};

interface IBindValue {
  autoHidden: boolean; // 超出最小宽度时是否自动隐藏
  defaultWidth: number; // 默认宽度
  isShow: boolean; // 是否展示
  maxWidth: number; // 最大宽度
  minWidth: number; // 最小宽度
  placement: 'left' | 'right'; // 拖拽侧栏的位置 默认left
  style: object; // 拖拽按钮样式
  theme: 'dotted' | 'normal' | 'simple'; // 拖拽按钮主题
  onHidden?: () => void; // 隐藏回调
  onWidthChange?: (width: number) => void; // 宽度更新
}
interface IDragHtmlElement extends HTMLElement {
  _bk_monitor_drag: {
    dragKey: string;
    el: HTMLDivElement;
    value: IBindValue;
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

const handleMouseMove = (event: MouseEvent) => {
  if (!insertedEl) return;
  const { maxWidth, minWidth, autoHidden, onHidden, onWidthChange, placement } = getBindValue(
    insertedEl._bk_monitor_drag.value as IBindValue
  );
  const rect = insertedEl.getBoundingClientRect();
  let width = placement === 'left' ? event.clientX - rect.left : rect.right - event.clientX;
  // 最大最小值限制
  if (maxWidth && width > maxWidth) {
    width = maxWidth;
  } else if (width < minWidth) {
    if (autoHidden) {
      width = 0;
      onHidden?.();
    } else {
      width = minWidth;
    }
  }

  // 超出最小宽度时自动隐藏
  if (width <= 0) {
    insertedEl.style.display = 'none';
    onWidthChange?.(0);
  } else {
    insertedEl.style.width = `${width}px`;
    onWidthChange?.(width);
  }
};

const handleMouseUp = () => {
  document.body.style.cursor = '';
  const classList = insertedEl._bk_monitor_drag.el.className.split(' ');
  if (classList.includes('line')) {
    const index = classList.findIndex(item => item === 'darg-ing');
    index >= 0 && classList.splice(index, 1);
    insertedEl._bk_monitor_drag.el.className = classList.join(' ');
  }
  document.removeEventListener('mousemove', handleMouseMove, false);
  document.removeEventListener('mouseup', handleMouseUp, false);
  document.onselectstart = null;
  document.ondragstart = null;
};

const dragMouseDown = evt => {
  const key = evt.target.dataset.dragKey;
  insertedEl = insertedElMap[key];
  document.onselectstart = function () {
    return false;
  };
  document.ondragstart = function () {
    return false;
  };
  const classList = evt.target.className.split(' ');
  if (classList.includes('line')) {
    classList.push('darg-ing');
    evt.target.className = classList.join(' ');
  }
  document.body.style.cursor = 'col-resize';
  document.addEventListener('mousemove', handleMouseMove, false);
  document.addEventListener('mouseup', handleMouseUp, false);
};

export const monitorDrag: DirectiveOptions = {
  inserted(el: IDragHtmlElement, bind: DirectiveBinding) {
    const { defaultWidth, isShow } = getBindValue(bind.value);
    const key = random(8);
    // 设置父元素样式
    el.style.cssText = `
        ${el.style.cssText};
        width: ${isShow ? defaultWidth : 0}px;
        height: 100%;
        position: relative;
    `;
    insertedEl = el;
    insertedElMap[key] = el;

    const { style, theme, placement } = getBindValue(bind.value as IBindValue);

    // 创建拖拽DOM
    const dragEle = document.createElement('div');
    dragEle.dataset.dragKey = key;
    const classes = ['bk-monitor-drag', theme, placement];
    dragEle.className = classes.join(' ');
    dragEle.style.cssText = Object.keys(style).reduce((pre, key) => {
      pre += `${key}: ${style[key]};`;
      return pre;
    }, '');
    el.appendChild(dragEle);

    // 绑定事件
    dragEle.addEventListener('mousedown', dragMouseDown);

    el._bk_monitor_drag = {
      el: dragEle,
      value: bind.value,
      dragKey: key,
    };
  },

  update(el: IDragHtmlElement, bind: DirectiveBinding) {
    el._bk_monitor_drag.value = bind.value;
    const { defaultWidth, maxWidth, minWidth, isShow, onWidthChange } = getBindValue(bind.value as IBindValue);
    const { display } = el.style;
    const curInsertedEl = insertedElMap[el._bk_monitor_drag.dragKey];
    // 展开默认宽度
    if (defaultWidth <= maxWidth && defaultWidth >= minWidth && isShow && display === 'none') {
      curInsertedEl.style.width = `${defaultWidth}px`;
      curInsertedEl.style.display = 'block';
      onWidthChange?.(defaultWidth);
    }
    if (!isShow) {
      curInsertedEl.style.display = 'none';
      onWidthChange?.(defaultWidth);
    }
  },

  unbind(el: IDragHtmlElement) {
    const { dragKey } = el._bk_monitor_drag;
    // 移除事件和删除DOM
    el._bk_monitor_drag.el.removeEventListener('mousedown', dragMouseDown);
    el.removeChild(el._bk_monitor_drag.el);
    insertedEl = null;
    delete insertedElMap[dragKey];

    delete el._bk_monitor_drag;
  },
};

export default {
  install: (Vue: VueConstructor) => Vue.directive('monitor-drag', monitorDrag),
  directive: monitorDrag,
};
