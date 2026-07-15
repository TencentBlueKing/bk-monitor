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
import { isElement, debounce } from 'lodash-es';

import {
  mapGlobalRangesToSegments,
  parseResultMarkedText,
} from '@/views/retrieve-core/page-highlight';

import type { Ref } from 'vue';

function deepQueryShadowSelector(selector) {
  // 搜索当前根下的元素
  const searchInRoot = (root: HTMLElement | ShadowRoot) => {
    // 尝试直接查找
    const el = root.querySelector(selector);
    if (el) {
      return el;
    }
    // 查找当前根下所有可能的 Shadow Host
    const shadowHosts = Array.from(root.querySelectorAll('*')).filter(elItem => elItem.shadowRoot);
    // 递归穿透每个 Shadow Host
    for (const host of shadowHosts) {
      const result = searchInRoot(host.shadowRoot);
      if (result) {
        return result;
      }
    }
    return null;
  };

  // 从 document.body 开始搜索
  return searchInRoot(document.body);
}

export const getTargetElement = (
  target: (() => HTMLElement) | HTMLElement | Ref<HTMLElement> | string,
): HTMLElement => {
  if (typeof target === 'string') {
    if (window.__IS_MONITOR_TRACE__) {
      return deepQueryShadowSelector(target);
    }
    return document.querySelector(target);
  }

  if (isElement(target)) {
    return target as HTMLElement;
  }

  if (typeof target === 'function') {
    return target?.();
  }

  return (target as Ref<HTMLElement>)?.value;
};

/**
 *
 * @param str
 * @param delimiterPattern
 * @param wordsplit 是否分词
 * @returns
 */
export const optimizedSplit = (str: string, delimiterPattern: string, wordsplit = true) => {
  if (!str) {
    return [];
  }

  // 先剥离 <mark> 再分词，避免高亮标签破坏 token 边界；高亮范围再映射回各 token。
  const { plainText, markRanges } = parseResultMarkedText(str);
  if (!plainText) {
    return [];
  }

  const tokens: Record<string, any>[] = [];
  let processedLength = 0;
  const CHUNK_SIZE = 200;

  if (wordsplit) {
    const MAX_TOKENS = 500;
    // 转义特殊字符，并构建用于分割的正则表达式
    const regexPattern = delimiterPattern
      .split('')
      .map(delimiter => `\\${delimiter}`)
      .join('|');

    const DELIMITER_REGEX = new RegExp(`(${regexPattern})`);
    const segmentSplitList = plainText.split(DELIMITER_REGEX).filter(Boolean);
    const normalTokens = segmentSplitList.slice(0, MAX_TOKENS);

    for (const t of normalTokens) {
      processedLength += t.length;
      tokens.push({
        text: t,
        isMark: false,
        isCursorText: !DELIMITER_REGEX.test(t),
      });
    }
  }

  if (processedLength < plainText.length) {
    const remaining = plainText.slice(processedLength);
    const chunkCount = Math.ceil(remaining.length / CHUNK_SIZE);
    for (let i = 0; i < chunkCount; i++) {
      tokens.push({
        text: remaining.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE),
        isMark: false,
        isCursorText: false,
        isBlobWord: false,
      });
    }
  }

  if (!markRanges.length) {
    return tokens.map(token => ({ ...token, resultRanges: [] }));
  }

  const perTokenRanges = mapGlobalRangesToSegments(tokens, markRanges, false);
  return tokens.map((token, index) => {
    const resultRanges = perTokenRanges[index] ?? [];
    return {
      ...token,
      isMark: resultRanges.length > 0,
      resultRanges,
    };
  });
};

/**
 * 设置滚动加载列表
 * @param wordList
 * @param rootElement
 * @param contentElement
 * @param renderFn
 * @returns
 */
export const setScrollLoadCell = (
  wordList: unknown[],
  rootElement: HTMLElement,
  contentElement: HTMLElement,
  renderFn: (_item: unknown, _index?: number) => HTMLElement,
  options: { pageSize?: number; maxAutoRenderItems?: number } = {},
) => {
  let startIndex = 0;
  let scrollEvtAdded = false;
  let scrollHandler: EventListener | null = null;
  const pageSize = options.pageSize ?? 50;
  const maxAutoRenderItems = options.maxAutoRenderItems ?? Number.POSITIVE_INFINITY;

  const defaultRenderFn = (item: any) => {
    const child = document.createElement('span');
    child.classList.add('item-text');
    child.textContent = item?.text?.length ? item.text : "''";
    return child;
  };

  /**
   * 渲染一个占位符，避免正好满一行，点击展开收起遮挡文本
   */
  const appendLastTag = () => {
    if (!contentElement?.lastElementChild?.classList?.contains('last-placeholder')) {
      const { scrollHeight = 0, offsetHeight = 0 } = contentElement ?? {};
      if (scrollHeight > offsetHeight) {
        const child = document.createElement('span');
        child.classList.add('last-placeholder');
        contentElement?.append?.(child);
      }
    }
  };

  const appendPageItems = (size?) => {
    if (startIndex > wordList.length) {
      requestAnimationFrame(appendLastTag);
      startIndex = wordList.length;
      return false;
    }

    const fragment = document.createDocumentFragment();
    const pageItems = wordList.slice(startIndex, startIndex + (size ?? pageSize));
    for (let i = 0; i < pageItems.length; i++) {
      const item = pageItems[i];
      const child = renderFn?.(item, startIndex + i) ?? defaultRenderFn(item);

      fragment.appendChild(child);
    }

    startIndex += size ?? pageSize;
    contentElement?.append?.(fragment);
    return true;
  };

  const createScrollHandler = next =>
    debounce(() => {
      if (rootElement) {
        const { offsetHeight, scrollHeight } = rootElement;
        const { scrollTop } = rootElement;
        if (scrollHeight - offsetHeight - scrollTop < 60) {
          appendPageItems();
          next?.();
        }
      }
    });

  const addScrollEvent = (next?) => {
    if (scrollEvtAdded) {
      return;
    }

    scrollEvtAdded = true;
    scrollHandler = createScrollHandler(next) as EventListener;
    rootElement?.addEventListener('scroll', scrollHandler);
  };

  const removeScrollEvent = () => {
    scrollEvtAdded = false;
    if (scrollHandler) {
      rootElement?.removeEventListener('scroll', scrollHandler);
      scrollHandler = null;
    }
  };

  /**
   * 初始化列表
   * 动态渲染列表，根据内容高度自动判定是否添加滚动监听事件
   */
  const setListItem = (size?, next?) => {
    if (appendPageItems(size)) {
      requestAnimationFrame(() => {
        if (rootElement) {
          const { offsetHeight, scrollHeight } = rootElement;
          if (startIndex < maxAutoRenderItems && offsetHeight * 1.2 > scrollHeight) {
            setListItem(undefined, next);
          } else {
            next?.();
            if (!scrollEvtAdded) {
              addScrollEvent(next);
            }
          }
        }
      });
    }
  };

  const reset = list => {
    // biome-ignore lint/style/noParameterAssign: reason
    wordList = list;
    startIndex = 0;
    contentElement.innerHTML = '';
    removeScrollEvent();
  };

  return {
    reset,
    setListItem,
    addScrollEvent,
    removeScrollEvent,
  };
};

export const getClickTargetElement = (pointer: MouseEvent) => {
  const textNode = pointer.target as HTMLElement;
  if (textNode) {
    return { offsetX: 0, offsetY: 0 };
  }

  const range = document.createRange();
  range.selectNodeContents(textNode);
  const lineRects = Array.from(range.getClientRects());
  const { clientX, clientY } = pointer;

  // 遍历所有行，找到点击位置所在的行
  let targetLineIndex = -1;
  for (let i = 0; i < lineRects.length; i++) {
    const rect = lineRects[i];
    if (clientY >= rect.top && clientY <= rect.bottom && clientX >= rect.left && clientX <= rect.right) {
      targetLineIndex = i;
      break;
    }
  }

  const target = lineRects?.[targetLineIndex];
  return { offsetX: 0, offsetY: (target?.bottom ?? pointer.clientY) - pointer.clientY };
};

export const setPointerCellClickTargetHandler = (e: MouseEvent, { offsetY = 0, offsetX = 0 }) => {
  const x = e.clientX;
  const y = e.clientY;
  let virtualTarget = document.body.querySelector('.bklog-virtual-target') as HTMLElement;
  if (!virtualTarget) {
    virtualTarget = document.createElement('span') as HTMLElement;
    virtualTarget.className = 'bklog-virtual-target';
    virtualTarget.style.setProperty('position', 'fixed');
    virtualTarget.style.setProperty('visibility', 'hidden');
    virtualTarget.style.setProperty('z-index', '-1');
    document.body.appendChild(virtualTarget);
  }

  virtualTarget.style.setProperty('left', `${x + offsetX}px`);
  virtualTarget.style.setProperty('top', `${y + offsetY}px`);

  return virtualTarget;
};
