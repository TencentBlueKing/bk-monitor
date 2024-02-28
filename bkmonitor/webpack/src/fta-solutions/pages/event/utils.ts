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
/**
 * @description 在关注人里面但不在通知人则禁用操作
 * @param follower
 * @param assignee
 */
export function getOperatorDisabled(follower: string[], assignee: string[]) {
  const username = window.user_name || window.username;
  const hasFollower = (follower || []).some(u => u === username);
  const hasAssignee = (assignee || []).some(u => u === username);
  return hasAssignee ? false : hasFollower;
}

/**
 * @description 给表格组件增加一个自定义的横向滚动条
 * @param target
 * @returns
 */
export function addHoverScroll(target: HTMLDivElement) {
  // 获取当前容器宽度
  const id = '------add-hover-scroll-class----';
  if (!target) {
    return;
  }
  function setScrollInfo(scrollEl: HTMLDivElement, barEl: HTMLDivElement) {
    // 创建一个 ResizeObserver 实例
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { target } = entry;
        const { scrollWidth, clientWidth } = target;
        scrollEl.style.maxWidth = `${clientWidth}px`;
        barEl.style.width = `${scrollWidth}px`;
      }
    });
    resizeObserver.observe(target);
  }
  const { scrollWidth, clientWidth } = target;
  let customScrollbarWrap: HTMLDivElement = target.querySelector(`#${id}`);
  const style = {
    'max-width': `${clientWidth}px`,
    // height: '8px',
    position: 'sticky',
    left: '0',
    bottom: '1px',
    background: '#fff',
    'overflow-x': 'scroll',
    'overflow-y': 'hidden',
    'z-index': '999'
  };
  if (!customScrollbarWrap) {
    customScrollbarWrap = document.createElement('div');
  }
  Object.keys(style).forEach(key => {
    customScrollbarWrap.style[key] = style[key];
  });
  customScrollbarWrap.id = id;
  customScrollbarWrap.addEventListener('mouseenter', () => {
    customScrollbarWrap.className = 'hover-scroll';
  });
  customScrollbarWrap.addEventListener('mouseleave', () => {
    customScrollbarWrap.className = '';
  });
  customScrollbarWrap.addEventListener('scroll', e => {
    const { scrollLeft } = e.target as HTMLDivElement;
    target.scrollLeft = scrollLeft;
  });
  const customScrollbar = document.createElement('div');
  const barStyle = {
    height: '4px',
    width: `${scrollWidth}px`
  };
  Object.keys(barStyle).forEach(key => {
    customScrollbar.style[key] = barStyle[key];
  });
  customScrollbarWrap.appendChild(customScrollbar);
  target.appendChild(customScrollbarWrap);
  setScrollInfo(customScrollbarWrap, customScrollbar);
}
