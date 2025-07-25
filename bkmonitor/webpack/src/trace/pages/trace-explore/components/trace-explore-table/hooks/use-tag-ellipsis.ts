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

import { type Ref, type ShallowRef, nextTick, onBeforeUnmount, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';

interface TagsEllipsisOptions {
  /** 折叠标签实例 */
  collapseTagRef: Ref<HTMLElement | null>;
  debounceDelay?: number;
  /** tag之间的间距 */
  horizontalSpacing: number;
  /** 显示tag的容器 */
  tagContainerRef: Ref<HTMLElement>;
  /** tag元素集合 */
  tagsRef: ShallowRef<HTMLElement[]>;
  /** 需要渲染的tag总数 */
  tagTotal: number;
}

/**
 * @description 处理tag折叠的hooks
 *
 */
export function useTagsEllipsis(options: TagsEllipsisOptions) {
  const { tagContainerRef, tagsRef, collapseTagRef, tagTotal, horizontalSpacing, debounceDelay = 100 } = options;
  /** 可以显示的tag最大索引 */
  const canShowIndex = shallowRef(0);
  /** ResizeObserver实例 */
  let resizeObserver: null | ResizeObserver = null;

  /**
   * @description 类型安全的DOM获取
   *
   **/
  function getValidTags(): HTMLElement[] {
    return tagsRef.value.filter(Boolean);
  }

  /**
   * @description 换行检测算法
   *
   **/
  function detectLineBreak(tags: HTMLElement[]): number {
    if (tagTotal === 0) return 0;

    const firstTop = tags[0].offsetTop;

    return tags.findIndex((tag, index) => {
      if (index === 0) return false;
      const currentTop = tag.offsetTop;
      if (currentTop > firstTop) {
        return true;
      }
      return false;
    });
  }

  /**
   * @description 核心计算逻辑（带防抖）
   *
   **/
  function calculateOverflow() {
    if (!tagsRef.value.length) return;

    const tags = getValidTags();
    const collapseEl = collapseTagRef.value;

    // 重置状态
    canShowIndex.value = tagTotal - 1;

    requestAnimationFrame(() => {
      // 1. 检测自然换行位置
      const firstBreakIndex = detectLineBreak(tags);
      if (firstBreakIndex === -1) return;

      const initialOverflowIndex = firstBreakIndex > 0 ? firstBreakIndex - 1 : 0;

      // 2. 验证折叠标签空间
      let finalIndex = initialOverflowIndex;
      const container = tagContainerRef.value;
      const collapseWidth = collapseEl.offsetWidth;
      const availableWidth = container.offsetWidth;
      // 计算当前行已用宽度
      let currentLineWidth = 0;
      for (let i = 0; i <= finalIndex; i++) {
        const tag = tags[i];
        if (tag.offsetTop > tags[0].offsetTop) break; // 换行了就停止
        currentLineWidth += tag.offsetWidth;
        currentLineWidth += horizontalSpacing;
      }

      // 检查剩余空间是否足够
      const remainingWidth = availableWidth - currentLineWidth - horizontalSpacing;
      if (remainingWidth < collapseWidth) {
        finalIndex = finalIndex - 1;
      }

      // 3. 更新状态
      canShowIndex.value = finalIndex;
    });
  }

  /**
   * @description 设置观察器
   *
   **/
  function setupObserver() {
    if (!resizeObserver) {
      resizeObserver = new ResizeObserver(useDebounceFn(calculateOverflow, debounceDelay));
      if (tagContainerRef?.value) resizeObserver.observe(tagContainerRef?.value);
    }
  }

  /**
   * @description 清理观察器
   *
   */
  function cleanupObserver() {
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
  }

  // 响应式监听
  watch(
    () => tagsRef.value,
    () => {
      cleanupObserver();
      nextTick(setupObserver);
    },
    { immediate: true, deep: true }
  );

  onBeforeUnmount(() => {
    cleanupObserver();
  });

  // 暴露方法
  return {
    canShowIndex,
    refresh: calculateOverflow,
    cleanup: cleanupObserver,
  };
}
