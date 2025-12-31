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
/** biome-ignore-all lint/style/useForOf: 需要使用索引进行精确控制 */
import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import './tag-more.scss';

/**
 * 标签项数据结构
 */
export type ITagItem = {
  id?: number | string;
  name: string;
  [key: string]: unknown;
};

/**
 * 标签组件属性定义
 */
export type ITagMoreProps = {
  /** 自定义class */
  className?: string;
  /** tag之间的间距，默认8px */
  gap?: number;
  /** 每个tag的最大宽度，默认128px */
  maxTagWidth?: number;
  /** 是否显示tooltip，默认true */
  showTooltip?: boolean;
  /** 标签列表 */
  tags: ITagItem[];
  /** tooltip标题 */
  title?: string;
  /** tooltip位置 */
  tooltipPlacement?: 'bottom' | 'left' | 'right' | 'top';
};

/**
 * 防抖延迟时间（毫秒）
 */
const DEBOUNCE_DELAY = 50;

export default defineComponent({
  props: {
    className: {
      default: '',
      type: String,
    },
    title: {
      default: '',
      type: String,
    },
    gap: {
      default: 8,
      type: Number,
    },
    maxTagWidth: {
      default: 128,
      type: Number,
    },
    showTooltip: {
      default: true,
      type: Boolean,
    },
    tags: {
      default: () => [],
      type: Array as () => ITagItem[],
    },
    tooltipPlacement: {
      default: 'bottom',
      type: String as () => 'bottom' | 'left' | 'right' | 'top',
    },
  },

  setup(props: ITagMoreProps) {
    // DOM引用
    const containerRef = ref<HTMLDivElement>(); // 主容器引用
    const measureRef = ref<HTMLDivElement>(); // 隐藏的测量容器引用
    const tipsPanelRef = ref<HTMLDivElement>(); // tooltip内容面板引用

    // 状态管理
    const visibleTags = ref<ITagItem[]>([]); // 当前可见的标签列表
    const hiddenCount = ref(0); // 隐藏的标签数量
    const resizeObserver = ref<ResizeObserver>(); // 容器尺寸监听器

    // Tippy实例
    let tippyInstance: Instance | null = null;

    /**
     * 缓存测量用的DOM元素，避免频繁创建和删除
     * 用于准确测量标签和指示器的实际宽度
     */
    const measureSpans = {
      tag: ref<HTMLSpanElement | null>(null), // 用于测量标签宽度的元素
      indicator: ref<HTMLSpanElement | null>(null), // 用于测量指示器宽度的元素
    };

    /**
     * 初始化测量用的DOM元素
     * 在隐藏容器中创建用于测量的span元素，这些元素不会被用户看到
     */
    const initMeasureElements = () => {
      if (!measureRef.value) {
        return;
      }

      // 创建标签测量元素
      if (!measureSpans.tag.value) {
        const span = document.createElement('span');
        span.className = 'tag-item';
        span.style.display = 'inline-block';
        measureRef.value.appendChild(span);
        measureSpans.tag.value = span;
      }

      // 创建指示器测量元素
      if (!measureSpans.indicator.value) {
        const span = document.createElement('span');
        span.className = 'tag-more-indicator';
        span.style.display = 'inline-block';
        measureRef.value.appendChild(span);
        measureSpans.indicator.value = span;
      }
    };

    /**
     * 测量标签的实际宽度
     * @param text - 标签文本内容
     * @returns 标签宽度（不超过maxTagWidth）
     */
    const measureItemWidth = (text: string): number => {
      if (!measureSpans.tag.value) {
        return props.maxTagWidth;
      }

      measureSpans.tag.value.textContent = text;
      const naturalWidth = measureSpans.tag.value.offsetWidth;
      return Math.min(naturalWidth, props.maxTagWidth);
    };

    /**
     * 测量指示器的实际宽度
     * @param count - 隐藏标签的数量
     * @returns 指示器宽度
     */
    const measureIndicatorWidth = (count: number): number => {
      if (!measureSpans.indicator.value) {
        return 0;
      }

      measureSpans.indicator.value.textContent = `+${count}`;
      return measureSpans.indicator.value.offsetWidth;
    };

    /**
     * 计算可见标签数量和隐藏标签数量
     * 使用贪心算法：尽可能多地显示标签，同时确保指示器能够放下
     *
     * 算法流程：
     * 1. 快速路径：如果所有标签的最小宽度总和小于容器宽度，全部显示
     * 2. 测量每个标签的实际宽度
     * 3. 贪心算法：尽可能多地放置标签
     * 4. 调整：如果放不下指示器，减少可见标签数量
     */
    const calculateVisibleTags = () => {
      // 边界情况处理
      if (!containerRef.value || props.tags.length === 0) {
        visibleTags.value = props.tags;
        hiddenCount.value = 0;
        return;
      }

      const containerWidth = containerRef.value.offsetWidth;
      const gap = props.gap;

      // 快速路径：计算所有标签的最小宽度总和（使用maxTagWidth）
      // 如果这个总和小于容器宽度，说明所有标签都能放下
      const totalMinWidth = props.tags.length * props.maxTagWidth + (props.tags.length - 1) * gap;
      if (totalMinWidth <= containerWidth) {
        visibleTags.value = props.tags;
        hiddenCount.value = 0;
        return;
      }

      // 预先测量每个标签的实际宽度（受maxTagWidth限制）
      const tagWidths = props.tags.map(tag => measureItemWidth(tag.name));

      // 贪心算法：尽可能多地放置标签
      let usedWidth = 0; // 已使用的宽度
      let visibleCount = 0; // 可见标签数量

      for (let i = 0; i < tagWidths.length; i++) {
        // 计算放置当前标签所需的总宽度（包括间距）
        const spacing = visibleCount > 0 ? gap : 0; // 第一个标签不需要左边距
        const requiredWidth = usedWidth + spacing + tagWidths[i];

        if (requiredWidth <= containerWidth) {
          usedWidth = requiredWidth;
          visibleCount += 1;
        } else {
          // 当前标签放不下，停止循环
          break;
        }
      }

      // 如果所有标签都能放下，直接返回
      if (visibleCount >= props.tags.length) {
        visibleTags.value = props.tags;
        hiddenCount.value = 0;
        return;
      }

      // 确保至少显示1个标签
      visibleCount = Math.max(1, visibleCount);
      let remainingCount = props.tags.length - visibleCount;
      let indicatorWidth = measureIndicatorWidth(remainingCount);

      // 计算放置指示器所需的总宽度
      let totalRequired = usedWidth + gap + indicatorWidth;

      // 如果放不下指示器，需要减少可见标签数量
      // 循环调整直到能够放下指示器，或只剩下1个可见标签
      while (visibleCount > 1 && totalRequired > containerWidth) {
        visibleCount -= 1;
        remainingCount = props.tags.length - visibleCount;

        // 重新计算已使用宽度（基于实际可见的标签）
        usedWidth = tagWidths
          .slice(0, visibleCount)
          .reduce((sum, width, index) => sum + width + (index > 0 ? gap : 0), 0);

        // 重新测量指示器宽度（因为隐藏数量变化了）
        indicatorWidth = measureIndicatorWidth(remainingCount);
        totalRequired = usedWidth + gap + indicatorWidth;
      }

      // 最终赋值
      visibleTags.value = props.tags.slice(0, visibleCount);
      hiddenCount.value = remainingCount;
    };

    /**
     * 防抖函数：避免频繁触发计算
     * 在短时间内多次调用时，只执行最后一次
     * @returns 防抖后的计算函数
     */
    const debouncedCalculate = (() => {
      let timeout: null | number = null;
      return () => {
        if (timeout) {
          window.clearTimeout(timeout);
        }
        timeout = window.setTimeout(() => {
          calculateVisibleTags();
          timeout = null;
        }, DEBOUNCE_DELAY);
      };
    })();

    /**
     * 初始化Tooltip弹窗
     * 使用tippy.js创建交互式提示框，显示所有标签列表
     */
    const initActionPop = () => {
      if (!(props.showTooltip && containerRef.value)) {
        return;
      }

      tippyInstance = tippy(containerRef.value as SingleTarget, {
        content: tipsPanelRef.value as HTMLElement,
        placement: props.tooltipPlacement,
        interactive: true, // 允许用户与tooltip交互
        hideOnClick: true, // 点击后隐藏
        appendTo: () => document.body, // 挂载到body，避免被父容器裁剪
      });
    };

    /**
     * 组件挂载后的初始化
     * 1. 初始化测量元素
     * 2. 初始化tooltip
     * 3. 计算可见标签
     * 4. 监听容器尺寸变化
     */
    onMounted(() => {
      nextTick(() => {
        initMeasureElements();
        initActionPop();
        calculateVisibleTags();

        // 使用ResizeObserver监听容器尺寸变化，自动重新计算可见标签
        if (window.ResizeObserver) {
          resizeObserver.value = new ResizeObserver(debouncedCalculate);
          if (containerRef.value) {
            resizeObserver.value.observe(containerRef.value);
          }
        }
      });
    });

    /**
     * 组件卸载前的清理工作
     * 释放所有资源，避免内存泄漏
     */
    onBeforeUnmount(() => {
      // 清理ResizeObserver
      if (resizeObserver.value) {
        resizeObserver.value.disconnect();
        resizeObserver.value = undefined;
      }

      // 清理tippy实例
      if (tippyInstance) {
        tippyInstance.destroy();
        tippyInstance = null;
      }

      // 清理测量元素
      if (measureRef.value) {
        measureRef.value.innerHTML = '';
      }
    });

    /**
     * 监听标签列表变化
     * 使用深度监听，当标签内容变化时重新计算可见标签
     */
    watch(
      () => props.tags,
      () => {
        nextTick(debouncedCalculate);
      },
      { deep: true },
    );

    /**
     * 监听影响布局的属性变化
     * gap和maxTagWidth的变化会影响标签布局，需要重新计算
     */
    watch([() => props.gap, () => props.maxTagWidth], () => {
      nextTick(debouncedCalculate);
    });

    /**
     * 渲染函数
     * 返回组件的JSX结构
     */
    return () => (
      <div
        ref={containerRef}
        class={['tag-more-container', props.className]}
      >
        {/* Tooltip内容面板：显示所有标签的完整列表 */}
        <div
          ref={tipsPanelRef}
          class='more-tips-panel'
        >
          {props.title && <div class='title'>{props.title}:</div>}
          <ul>
            {props.tags.map((item, index) => (
              <li key={item.id || index}>{item.name}</li>
            ))}
          </ul>
        </div>

        {/* 隐藏的测量容器：用于准确测量标签和指示器的宽度 */}
        <div
          ref={measureRef}
          class='measure-box'
        />

        {/* 可见的标签列表 */}
        {visibleTags.value.map((tag, index) => (
          <span
            key={tag.id || index}
            style={{
              maxWidth: `${props.maxTagWidth}px`,
              marginRight: index < visibleTags.value.length - 1 ? `${props.gap}px` : '0',
            }}
            class='tag-item'
          >
            {tag.name}
          </span>
        ))}

        {/* 隐藏标签数量指示器：当有标签被隐藏时显示 */}
        {hiddenCount.value > 0 && (
          <span
            style={{
              marginLeft: visibleTags.value.length > 0 ? `${props.gap}px` : '0',
            }}
            class='tag-more-indicator'
          >
            +{hiddenCount.value}
          </span>
        )}
      </div>
    );
  },
});
