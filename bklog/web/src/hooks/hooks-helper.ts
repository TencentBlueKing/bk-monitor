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
import { Ref } from 'vue';

import { isElement, debounce } from 'lodash';

function deepQueryShadowSelector(selector) {
  // 搜索当前根下的元素
  const searchInRoot = (root: HTMLElement | ShadowRoot) => {
    // 尝试直接查找
    const el = root.querySelector(selector);
    if (el) return el;
    // 查找当前根下所有可能的 Shadow Host
    const shadowHosts = Array.from(root.querySelectorAll('*')).filter(el => el.shadowRoot);
    // 递归穿透每个 Shadow Host
    for (const host of shadowHosts) {
      const result = searchInRoot(host.shadowRoot);
      if (result) return result;
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
  if (!str) return [];

  let tokens = [];
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
    const MARK_REGEX = /<mark>(.*?)<\/mark>/gis;

    const segments = str.split(/(<mark>.*?<\/mark>)/gi);

    for (const segment of segments) {
      if (tokens.length >= MAX_TOKENS) break;
      const isMark = MARK_REGEX.test(segment);

      const segmengtSplitList = segment.replace(MARK_REGEX, '$1').split(DELIMITER_REGEX).filter(Boolean);
      const normalTokens = segmengtSplitList.slice(0, MAX_TOKENS - tokens.length);

      if (isMark) {
        processedLength += '<mark>'.length;

        if (normalTokens.length === segmengtSplitList.length) {
          processedLength += '</mark>'.length;
        }
      }

      normalTokens.forEach(t => {
        processedLength += t.length;
        tokens.push({
          text: t,
          isMark,
          isCursorText: !DELIMITER_REGEX.test(t),
        });
      });
    }
  }

  if (processedLength < str.length) {
    const remaining = str.slice(processedLength);
    const chunkCount = Math.ceil(remaining.length / CHUNK_SIZE);

    for (let i = 0; i < chunkCount; i++) {
      tokens.push({
        text: remaining.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE),
        isMark: false,
        isCursorText: false,
        isBlobWord: true,
      });
    }
  }

  return tokens;
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
  wordList: Array<unknown>,
  rootElement: HTMLElement,
  contentElement: HTMLElement,
  renderFn: (item: unknown) => HTMLElement,
) => {
  let startIndex = 0;
  let scrollEvtAdded = false;
  const pageSize = 50;

  const defaultRenderFn = (item: any) => {
    const child = document.createElement('span');
    child.classList.add('item-text');
    child.innerText = item?.text ?? 'text';
    return child;
  };

  /**
   * 渲染一个占位符，避免正好满一行，点击展开收起遮挡文本
   */
  const appendLastTag = () => {
    if (!contentElement?.lastElementChild?.classList?.contains('last-placeholder')) {
      const child = document.createElement('span');
      child.classList.add('last-placeholder');
      contentElement?.append?.(child);
    }
  };

  const appendPageItems = (size?) => {
    if (startIndex >= wordList.length) {
      appendLastTag();
      return false;
    }

    const fragment = document.createDocumentFragment();
    const pageItems = wordList.slice(startIndex, startIndex + (size ?? pageSize));
    pageItems.forEach(item => {
      const child = renderFn?.(item) ?? defaultRenderFn(item);

      fragment.appendChild(child);
    });

    contentElement?.append?.(fragment);
    return true;
  };

  const handleScrollEvent = debounce(() => {
    if (rootElement) {
      const { offsetHeight, scrollHeight } = rootElement;
      const { scrollTop } = rootElement;
      if (scrollHeight - offsetHeight - scrollTop < 60) {
        startIndex = startIndex + pageSize;
        appendPageItems();
      }
    }
  });

  const addScrollEvent = () => {
    scrollEvtAdded = true;
    rootElement?.addEventListener('scroll', handleScrollEvent);
  };

  const removeScrollEvent = () => {
    scrollEvtAdded = false;
    rootElement?.removeEventListener('scroll', handleScrollEvent);
  };

  /**
   * 初始化列表
   * 动态渲染列表，根据内容高度自动判定是否添加滚动监听事件
   */
  const setListItem = (size?) => {
    if (appendPageItems(size)) {
      requestAnimationFrame(() => {
        if (rootElement) {
          const { offsetHeight, scrollHeight } = rootElement;
          if (offsetHeight * 1.2 > scrollHeight) {
            startIndex = startIndex + (size ?? pageSize);
            setListItem();
          } else {
            if (!scrollEvtAdded) {
              addScrollEvent();
            }
          }
        }
      });
    }
  };

  return {
    setListItem,
    addScrollEvent,
    removeScrollEvent,
  };
};
