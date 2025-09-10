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
/** biome-ignore-all lint/style/useForOf: <explanation> */
import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import './tag-more.scss';

export type TagItem = {
  id?: number | string;
  name: string;
  [key: string]: any;
};

export type TagMoreProps = {
  className?: string; // 自定义class
  gap?: number; // tag之间的间距，默认8px
  maxTagWidth?: number; // 每个tag的最大宽度，默认128px
  showTooltip?: boolean; // 是否显示tooltip，默认true
  tags: TagItem[];
  tooltipPlacement?: 'bottom' | 'left' | 'right' | 'top'; // tooltip位置
};

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
      type: Array as () => TagItem[],
    },
    tooltipPlacement: {
      default: 'bottom',
      type: String as () => 'bottom' | 'left' | 'right' | 'top',
    },
  },

  setup(props: TagMoreProps) {
    const containerRef = ref<HTMLDivElement>();
    const measureRef = ref<HTMLDivElement>();
    const visibleTags = ref<TagItem[]>([]);
    const hiddenCount = ref(0);
    const tipsPanelRef = ref<HTMLDivElement>();
    let tippyInstance: Instance | null = null;

    // 缓存测量用的DOM元素，避免频繁创建和删除
    const measureSpans = {
      tag: ref<HTMLSpanElement | null>(null),
      indicator: ref<HTMLSpanElement | null>(null),
    };

    // 初始化测量用的DOM元素
    const initMeasureElements = () => {
      if (!measureRef.value) {
        return;
      }

      if (!measureSpans.tag.value) {
        const span = document.createElement('span');
        span.className = 'tag-item';
        span.style.display = 'inline-block';
        measureRef.value.appendChild(span);
        measureSpans.tag.value = span;
      }

      if (!measureSpans.indicator.value) {
        const span = document.createElement('span');
        span.className = 'tag-more-indicator';
        span.style.display = 'inline-block';
        measureRef.value.appendChild(span);
        measureSpans.indicator.value = span;
      }
    };

    // 测量标签宽度（使用缓存的DOM元素）
    const measureItemWidth = (text: string) => {
      if (!measureSpans.tag.value) {
        return props.maxTagWidth;
      }

      measureSpans.tag.value.textContent = text;
      const naturalWidth = measureSpans.tag.value.offsetWidth;
      return Math.min(naturalWidth, props.maxTagWidth);
    };

    // 测量指示器宽度（使用缓存的DOM元素）
    const measureIndicatorWidth = (n: number) => {
      if (!measureSpans.indicator.value) {
        return 0;
      }

      measureSpans.indicator.value.textContent = `+${n}`;
      return measureSpans.indicator.value.offsetWidth;
    };

    // 计算可见的标签数量（优化计算逻辑）
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: <explanation>
    const calculateVisibleTags = () => {
      if (!containerRef.value || props.tags.length === 0) {
        visibleTags.value = props.tags;
        hiddenCount.value = 0;
        return;
      }

      const containerWidth = containerRef.value.offsetWidth;
      const gap = props.gap;

      // 先检查是否所有标签都能放下（快速路径）
      const totalMinWidth = props.tags.length * props.maxTagWidth + (props.tags.length - 1) * gap;
      if (totalMinWidth <= containerWidth) {
        visibleTags.value = props.tags;
        hiddenCount.value = 0;
        return;
      }

      // 预先测量每个tag的宽度（受maxTagWidth限制）
      const tagWidths = props.tags.map(tag => measureItemWidth(tag.name));

      // 计算可见标签数量
      let usedWidth = 0;
      let visibleCount = 0;

      // 计算可放标签数量，贪心算法：尽量多放标签
      // eslint-disable-next-line @typescript-eslint/prefer-for-of
      for (let i = 0; i < tagWidths.length; i++) {
        const requiredWidth = usedWidth + (visibleCount > 0 ? gap : 0) + tagWidths[i];
        if (requiredWidth <= containerWidth) {
          usedWidth = requiredWidth;
          visibleCount++;
        } else {
          break;
        }
      }

      // 全部可见
      if (visibleCount >= props.tags.length) {
        visibleTags.value = props.tags;
        hiddenCount.value = 0;
        return;
      }

      // 确保至少显示1个标签
      visibleCount = Math.max(1, visibleCount);
      let remainingCount = props.tags.length - visibleCount;
      let indicatorWidth = measureIndicatorWidth(remainingCount);

      // 检查是否能放下指示器
      let totalRequired = usedWidth + gap + indicatorWidth;

      // 如果放不下，减少可见标签数量
      while (visibleCount > 1 && totalRequired > containerWidth) {
        visibleCount--;
        remainingCount = props.tags.length - visibleCount;
        // 重新计算已使用宽度
        usedWidth = tagWidths
          .slice(0, visibleCount)
          .reduce((sum, width, index) => sum + width + (index > 0 ? gap : 0), 0);
        indicatorWidth = measureIndicatorWidth(remainingCount);
        totalRequired = usedWidth + gap + indicatorWidth;
      }

      // 最终赋值
      visibleTags.value = props.tags.slice(0, visibleCount);
      hiddenCount.value = remainingCount;
    };

    // 监听容器大小变化
    const resizeObserver = ref<ResizeObserver>();
    // 防抖动处理，避免频繁触发计算
    const debouncedCalculate = (() => {
      let timeout: null | number = null;
      return () => {
        if (timeout) {
          window.clearTimeout(timeout);
        }
        timeout = window.setTimeout(() => {
          calculateVisibleTags();
          timeout = null;
        }, 50);
      };
    })();

    onMounted(() => {
      nextTick(() => {
        initMeasureElements();
        initActionPop();
        calculateVisibleTags();

        if (window.ResizeObserver) {
          resizeObserver.value = new ResizeObserver(debouncedCalculate);
          if (containerRef.value) {
            resizeObserver.value.observe(containerRef.value);
          }
        }
      });
    });

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

    // watch监听，添加深度监听但减少触发频率
    watch(
      () => props.tags,
      () => {
        nextTick(debouncedCalculate);
      },
      { deep: true },
    );

    // 监听可能影响布局的属性变化
    watch([() => props.gap, () => props.maxTagWidth], () => {
      nextTick(debouncedCalculate);
    });

    const initActionPop = () => {
      if (!(props.showTooltip && containerRef.value)) {
        return;
      }

      tippyInstance = tippy(containerRef.value as SingleTarget, {
        content: tipsPanelRef.value as any,
        placement: props.tooltipPlacement,
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
      });
    };

    return () => (
      <div
        ref={containerRef}
        class={['tag-more-container', props.className]}
      >
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

        {/* 隐藏测量容器 */}
        <div
          ref={measureRef}
          class='measure-box'
        />

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
