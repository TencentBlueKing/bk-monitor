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
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
import { type PropType, computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { Tag } from 'bkui-vue';

import type { TagCellItem } from '../../typing';
import type { SlotReturnValue } from 'tdesign-vue-next';
import type { TippyOptions } from 'vue-tippy';

import './collapse-tags-multi-rows.scss';

const DEFAULT_TAG_COLOR = {
  tagColor: '#4D4F56',
  tagBgColor: '#F0F1F5',
  tagHoverColor: '#4D4F56',
  tagHoverBgColor: '#DCDEE5',
};

/**
 * @description 多行折叠标签渲染组件
 * 专门为多行 tags 展示设计，独立于单行 CollapseTags 组件
 *
 * 核心设计：双层渲染
 * - 可见层：仅渲染 visibleCount 个 tag + "+N" 折叠标签，有 max-height + overflow:hidden 限制
 * - 测量层：始终渲染全部 tag（visibility:hidden），用于位置计算
 *   这样无论容器如何缩放，所有 tag 都可测量，无需"展开再重算"
 */
export default defineComponent({
  name: 'CollapseTagsMultiRows',
  props: {
    /** 标签数据 */
    data: {
      type: Array as PropType<(string | TagCellItem)[]>,
      default: () => [],
    },
    /** 最大展示行数 */
    maxRows: {
      type: Number,
      default: 4,
    },
    /** 标签之间的水平间距 */
    tagGap: {
      type: Number,
      default: 4,
    },
    /** 标签溢出时 hover 显示的提示内容渲染方法 */
    ellipsisTip: {
      type: Function as PropType<(ellipsisList: (string | TagCellItem)[]) => SlotReturnValue>,
    },
    /** 溢出标签 hover 提示 popover 配置 */
    ellipsisTippyOptions: {
      type: Object as PropType<TippyOptions>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** 根元素 ref */
    const containerRef = ref<HTMLElement | null>(null);
    /** 可见标签容器 ref */
    const tagsWrapRef = ref<HTMLElement | null>(null);
    /** 测量层容器 ref（始终渲染全部 tag） */
    const measureWrapRef = ref<HTMLElement | null>(null);
    /** 折叠标签预计算宽度用 ref */
    const measureTagRef = ref<HTMLElement | null>(null);
    /** 实际可见的标签数量 */
    const visibleCount = ref(props.data.length);
    /** 尺寸监听器 */
    let resizeObserver: null | ResizeObserver = null;
    /** 上一次容器宽度 */
    let lastContainerWidth = 0;

    const cssVars = computed(() => ({
      '--tag-gap': `${props.tagGap}px`,
      '--max-rows': props.maxRows,
    }));

    /**
     * @description 核心溢出计算逻辑（同步，无 debounce）
     * 基于测量层（始终包含全部 tag）来计算可见数量，避免"展开再重算"的闪烁问题
     */
    function doCalculateOverflow() {
      if (!containerRef.value || !measureWrapRef.value) return;

      const tags = props.data;
      if (!tags.length) return;

      // 计算最大内容高度（不含 padding，与测量层对齐）
      const tagHeight = 22; // --multi-rows-tag-height
      const maxContentHeight = tagHeight * props.maxRows + props.tagGap * (props.maxRows - 1);

      const measureWrapRect = measureWrapRef.value.getBoundingClientRect();

      // 获取折叠标签的预计算宽度
      const collectTagWidth = measureTagRef.value?.getBoundingClientRect?.().width || 0;

      // 在测量层中收集所有 tag 元素的位置信息
      const tagElements = measureWrapRef.value.querySelectorAll('.multi-rows-tag-item');
      let lastFullyVisibleIndex = -1;

      for (let i = 0; i < tagElements.length; i++) {
        const el = tagElements[i] as HTMLElement;
        const rect = el.getBoundingClientRect();
        // 相对于测量层顶部的偏移
        const relativeBottom = rect.bottom - measureWrapRect.top;

        // tag 底部超出最大内容高度（行数溢出）
        if (relativeBottom > maxContentHeight + 1) {
          break;
        }

        // tag 右侧超出测量层右侧（宽度溢出，被截断）
        if (rect.left < measureWrapRect.right && rect.right > measureWrapRect.right + 1) {
          break;
        }

        // tag 整个都在测量层右侧之外（换行后宽度溢出）
        if (rect.left >= measureWrapRect.right) {
          break;
        }

        lastFullyVisibleIndex = i;
      }

      // 全部 tag 都可见，无需折叠
      if (lastFullyVisibleIndex === tags.length - 1) {
        visibleCount.value = tags.length;
        return;
      }

      // 极端情况：连一个 tag 都放不下
      if (lastFullyVisibleIndex < 0) {
        visibleCount.value = 0;
        return;
      }

      // 有 tag 不可见，需要折叠并在最后一行为 "+N" 标签腾出空间

      // 找到最后一个可见 tag 所在行的起始索引
      const lastVisibleEl = tagElements[lastFullyVisibleIndex] as HTMLElement;
      const lastVisibleRelativeTop = lastVisibleEl.getBoundingClientRect().top - measureWrapRect.top;
      let rowStartIndex = lastFullyVisibleIndex;
      for (let i = lastFullyVisibleIndex - 1; i >= 0; i--) {
        const el = tagElements[i] as HTMLElement;
        const relativeTop = el.getBoundingClientRect().top - measureWrapRect.top;
        if (relativeTop < lastVisibleRelativeTop - 1) {
          rowStartIndex = i + 1;
          break;
        }
        rowStartIndex = i;
      }

      // 计算最后一行的已用宽度
      let lastRowWidth = 0;
      for (let i = rowStartIndex; i <= lastFullyVisibleIndex; i++) {
        const el = tagElements[i] as HTMLElement;
        if (i > rowStartIndex) {
          lastRowWidth += props.tagGap;
        }
        lastRowWidth += el.getBoundingClientRect().width;
      }

      // 使用测量层的 clientWidth 作为可用宽度（与 flex 布局实际宽度一致）
      const availableWidth = measureWrapRef.value.clientWidth;
      const needCollectSpace = props.tagGap + collectTagWidth;

      if (lastRowWidth + needCollectSpace > availableWidth) {
        // +N 标签放不下，需要从最后一行移除一些 tag 来腾出空间
        let count = lastFullyVisibleIndex + 1;
        let currentWidth = lastRowWidth;
        while (count > rowStartIndex + 1) {
          count--;
          const removedEl = tagElements[count] as HTMLElement;
          currentWidth -= removedEl.getBoundingClientRect().width + props.tagGap;
          // 留 1px 安全余量，避免子像素渲染导致 +N 换行
          if (currentWidth + needCollectSpace <= availableWidth - 1) break;
        }
        visibleCount.value = Math.max(count, 1);
      } else {
        visibleCount.value = lastFullyVisibleIndex + 1;
      }
    }

    /** 设置 ResizeObserver，尺寸变化时直接计算（响应更快） */
    function setupObserver() {
      if (!containerRef.value) return;
      resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          const width = entry.contentRect.width;
          if (width === lastContainerWidth) return;
          lastContainerWidth = width;
          doCalculateOverflow();
        }
      });
      resizeObserver.observe(containerRef.value);
    }

    function cleanupObserver() {
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
    }

    watch(
      () => containerRef.value,
      nVal => {
        cleanupObserver();
        if (nVal) {
          nextTick(setupObserver);
        }
      },
      { immediate: true }
    );

    watch(
      () => props.data,
      () => {
        nextTick(doCalculateOverflow);
      }
    );

    onMounted(() => {
      nextTick(doCalculateOverflow);
    });

    onBeforeUnmount(cleanupObserver);

    return {
      containerRef,
      tagsWrapRef,
      measureWrapRef,
      measureTagRef,
      visibleCount,
      cssVars,
    };
  },
  render() {
    const data = this.data || [];
    if (data.length === 0) return null;

    const collapseCount = data.length - this.visibleCount;
    const canShowCollapseTag = collapseCount > 0;
    const showList = data.slice(0, this.visibleCount);
    const ellipsisList = data.slice(this.visibleCount);

    return (
      <div
        ref='containerRef'
        style={this.cssVars}
        class='collapse-tags-multi-rows'
      >
        {/* 可见标签区域：仅渲染 visibleCount 个 tag + "+N"，有 max-height + overflow:hidden */}
        <div
          ref='tagsWrapRef'
          class='multi-rows-tags-wrap'
        >
          {showList.map((tag, index) => {
            const tagText = (tag as TagCellItem)?.alias || (tag as string);
            return (
              <Tag
                key={index}
                style={{
                  '--tag-color': (tag as TagCellItem)?.tagColor || DEFAULT_TAG_COLOR.tagColor,
                  '--tag-bg-color': (tag as TagCellItem)?.tagBgColor || DEFAULT_TAG_COLOR.tagBgColor,
                  '--tag-hover-color':
                    (tag as TagCellItem)?.tagHoverColor ||
                    (tag as TagCellItem)?.tagColor ||
                    DEFAULT_TAG_COLOR.tagHoverColor,
                  '--tag-hover-bg-color':
                    (tag as TagCellItem)?.tagHoverBgColor ||
                    (tag as TagCellItem)?.tagBgColor ||
                    DEFAULT_TAG_COLOR.tagHoverBgColor,
                }}
                class='multi-rows-tag-item'
                v-tippy={{
                  content: tagText,
                  theme: 'dark',
                  delay: 300,
                  onShow(instance: any) {
                    const el = instance.reference as HTMLElement;
                    // Tag 组件内部有 .bk-tag-text span 做了文本截断，
                    // 需要检查该子元素是否溢出，而非 Tag 根元素
                    const textEl = el.querySelector('.bk-tag-text') as HTMLElement | null;
                    const checkEl = textEl || el;
                    if (checkEl.scrollWidth <= checkEl.clientWidth) {
                      return false;
                    }
                  },
                }}
              >
                {{ default: () => tagText }}
              </Tag>
            );
          })}
          {canShowCollapseTag && (
            <span
              class='multi-rows-collapse-tag'
              v-tippy={{
                content: this.ellipsisTip
                  ? this.ellipsisTip(ellipsisList)
                  : ellipsisList.map(t => (t as TagCellItem)?.alias || t).join('，'),
                theme: 'dark text-wrap max-width-50vw',
                delay: 300,
                ...(this.ellipsisTippyOptions ?? {}),
              }}
            >
              +{collapseCount}
            </span>
          )}
        </div>
        {/* 测量层：始终渲染全部 tag，用于位置计算（visibility:hidden，不影响视觉） */}
        <div
          ref='measureWrapRef'
          class='multi-rows-tags-measure'
        >
          {data.map((tag, index) => (
            <Tag
              key={index}
              style={{
                '--tag-color': (tag as TagCellItem)?.tagColor || DEFAULT_TAG_COLOR.tagColor,
                '--tag-bg-color': (tag as TagCellItem)?.tagBgColor || DEFAULT_TAG_COLOR.tagBgColor,
              }}
              class='multi-rows-tag-item'
            >
              {{ default: () => (tag as TagCellItem)?.alias || tag }}
            </Tag>
          ))}
        </div>
        {/* 隐藏的折叠标签，用于预计算 +N 宽度 */}
        <span
          ref='measureTagRef'
          class='multi-rows-collapse-tag multi-rows-collapse-tag-measure'
        >
          +{data.length}
        </span>
      </div>
    );
  },
});
