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
import { random } from 'monitor-common/utils/utils';

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
  autoHidden: boolean; // 超出最小宽度时是否自动隐藏
  theme: 'normal' | 'simple'; // 拖拽按钮主题
}
interface IDragHtmlElement extends HTMLElement {
  _bk_monitor_drag: {
    el: HTMLDivElement;
    value: IBindValue;
    dragKey: string;
  };
}

const handleMouseMove = (event: MouseEvent) => {
  if (!insertedEl) return;
  const { maxWidth, minWidth, autoHidden } = insertedEl._bk_monitor_drag.value;
  const rect = insertedEl.getBoundingClientRect();
  let width = event.clientX - rect.left;
  // 最大最小值限制
  if (maxWidth && width > maxWidth) {
    width = maxWidth;
  } else if (width < minWidth) {
    width = autoHidden ? 0 : minWidth;
  }

  // 超出最小宽度时自动隐藏
  if (width <= 0) {
    insertedEl.style.display = 'none';
  } else {
    insertedEl.style.width = `${width}px`;
    insertedEl._bk_monitor_drag.el.style.left = `${width - 3}px`;
  }
};

const handleMouseUp = () => {
  document.body.style.cursor = '';
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
  document.onselectstart = null;
  document.ondragstart = null;
};

const dragMouseDown = evt => {
  const key = evt.target.dataset.dragKey;
  insertedEl = insertedElMap[key];
  document.onselectstart = () => false;
  document.ondragstart = () => false;

  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};

const monitorDrag: DirectiveOptions = {
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
    dragEle.className = theme === 'simple' ? 'bk-monitor-drag-simple' : 'bk-monitor-drag';
    dragEle.style.cssText = Object.keys(style).reduce((pre, key) => {
      pre += `${key}: ${style[key]};`;
      return pre;
    }, '');
    dragEle.style.left = `${insertedEl.getBoundingClientRect().width - 3}px`;
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
