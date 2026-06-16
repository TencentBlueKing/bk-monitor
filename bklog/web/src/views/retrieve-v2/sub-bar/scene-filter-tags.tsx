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

import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import useStore from '@/hooks/use-store';
import { isEmptyFilterValue } from '@/store/helper';
import { getOperatorDisplay, getDefaultOp } from '@/views/retrieve-v3/search-bar/scene-filter/scene-config';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import './scene-filter-tags.scss';

interface TagItem {
  key: string;
  name: string;
  value: string;
  opDisplay: string;
}

const DEBOUNCE_DELAY = 50;
const TAG_GAP = 8;

export default defineComponent({
  name: 'SceneFilterTags',
  props: {
    filterLabels: {
      type: Object as () => Record<string, Record<string, string>>,
      default: () => ({}),
    },
  },
  setup(props) {
    const store = useStore();

    const containerRef = ref<HTMLDivElement>();
    const measureRef = ref<HTMLDivElement>();
    const tipsPanelRef = ref<HTMLDivElement>();
    const indicatorRef = ref<HTMLSpanElement>();

    const visibleTags = ref<TagItem[]>([]);
    const hiddenCount = ref(0);
    const resizeObserver = ref<ResizeObserver>();

    let tippyInstance: Instance | null = null;

    const measureSpans = {
      tag: ref<HTMLSpanElement | null>(null),
      indicator: ref<HTMLSpanElement | null>(null),
    };


    const sceneConfigs = computed(() => store.getters['retrieve/sceneConfigList']);

    const tags = computed<TagItem[]>(() => {
      const sceneActive = store.state.indexItem.scene_active;
      const filterValues = store.state.indexItem.scene_filter_values;

      if (!sceneActive || !filterValues) return [];

      const sceneConfig = sceneConfigs.value.find(s => s.type === sceneActive);
      if (!sceneConfig) return [];

      const result: TagItem[] = [];

      for (const field of sceneConfig.fields) {
        const val = filterValues[field.key];
        if (isEmptyFilterValue(val)) continue;

        const rawValue = val?.value ?? val;
        const op = val?.op ?? getDefaultOp(field.ops);
        const opDisplay = getOperatorDisplay(op, field.choicesType, field.fieldType);

        const fieldLabels = props.filterLabels[field.key] ?? {};
        const rawValues = Array.isArray(rawValue) ? rawValue : [rawValue];
        const displayNames = rawValues.map(id => fieldLabels[id] ?? String(id));
        const displayValue = displayNames.join(', ');

        result.push({
          key: field.key,
          name: field.name,
          value: `${field.name}${opDisplay}${displayValue}`,
          opDisplay,
        });
      }

      return result;
    });

    const initMeasureElements = () => {
      if (!measureRef.value) return;

      if (!measureSpans.tag.value) {
        const span = document.createElement('span');
        span.className = 'tag-item';
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

    const measureItemWidth = (tag: TagItem): number => {
      if (!measureSpans.tag.value) return 0;
      const displayValue = tag.value.slice(tag.name.length + tag.opDisplay.length);
      measureSpans.tag.value.innerHTML = `<span class="tag-key">${tag.name}</span>`
        + `<span class="tag-separator">${tag.opDisplay}</span>`
        + `<span class="tag-value">${displayValue}</span>`;
      return measureSpans.tag.value.offsetWidth;
    };

    const measureIndicatorWidth = (count: number): number => {
      if (!measureSpans.indicator.value) return 0;
      measureSpans.indicator.value.textContent = `+${count}`;
      return measureSpans.indicator.value.offsetWidth;
    };

    const calculateVisibleTags = () => {
      if (!containerRef.value || tags.value.length === 0) {
        visibleTags.value = tags.value;
        hiddenCount.value = 0;
        return;
      }

      // 容器不可见时（祖先 display:none），跳过计算，保留当前值
      // 等待可见后由 ResizeObserver 重新触发计算
      if (containerRef.value.offsetWidth === 0 && containerRef.value.offsetHeight === 0) {
        return;
      }

      // 可用宽度 = 容器 offsetWidth - 额外间距
      const availableWidth = containerRef.value.offsetWidth - 8 * 2;
      if (availableWidth <= 0) {
        visibleTags.value = [];
        hiddenCount.value = tags.value.length;
        return;
      }

      const tagWidths = tags.value.map(tag => measureItemWidth(tag));

      let usedWidth = 0;
      let visibleCount = 0;

      for (let i = 0; i < tagWidths.length; i++) {
        const spacing = visibleCount > 0 ? TAG_GAP : 0;
        const requiredWidth = usedWidth + spacing + tagWidths[i];

        if (requiredWidth <= availableWidth) {
          usedWidth = requiredWidth;
          visibleCount += 1;
        } else {
          break;
        }
      }

      if (visibleCount >= tags.value.length) {
        visibleTags.value = tags.value;
        hiddenCount.value = 0;
        return;
      }

      visibleCount = Math.max(1, visibleCount);
      let remainingCount = tags.value.length - visibleCount;
      let indicatorWidth = measureIndicatorWidth(remainingCount);

      let totalRequired = usedWidth + TAG_GAP + indicatorWidth;

      while (visibleCount > 1 && totalRequired > availableWidth) {
        visibleCount -= 1;
        remainingCount = tags.value.length - visibleCount;

        usedWidth = tagWidths
          .slice(0, visibleCount)
          .reduce((sum, width, index) => sum + width + (index > 0 ? TAG_GAP : 0), 0);

        indicatorWidth = measureIndicatorWidth(remainingCount);
        totalRequired = usedWidth + TAG_GAP + indicatorWidth;
      }

      visibleTags.value = tags.value.slice(0, visibleCount);
      hiddenCount.value = remainingCount;
    };

    const debouncedCalculate = (() => {
      let timeout: null | number = null;
      return () => {
        if (timeout) window.clearTimeout(timeout);
        timeout = window.setTimeout(() => {
          calculateVisibleTags();
          timeout = null;
        }, DEBOUNCE_DELAY);
      };
    })();

    const initActionPop = () => {
      if (tippyInstance) {
        tippyInstance.destroy();
        tippyInstance = null;
      }

      if (!indicatorRef.value || !tipsPanelRef.value) return;

      tippyInstance = tippy(indicatorRef.value as SingleTarget, {
        content: tipsPanelRef.value as HTMLElement,
        arrow: false,
        theme: 'light',
        placement: 'bottom-end',
        interactive: true,
        maxWidth: 'none',
        appendTo: () => document.body,
      });
    };

    let rightOptionObserver: ResizeObserver | undefined;

    onMounted(() => {
      nextTick(() => {
        initMeasureElements();
        calculateVisibleTags();

        if (window.ResizeObserver) {
          resizeObserver.value = new ResizeObserver(debouncedCalculate);
          if (containerRef.value) {
            resizeObserver.value.observe(containerRef.value);
          }

          const rightOptionEl = document.querySelector('.subbar-container .box-right-option') as HTMLElement;
          if (rightOptionEl) {
            rightOptionObserver = new ResizeObserver(debouncedCalculate);
            rightOptionObserver.observe(rightOptionEl);
          }
        }
      });
    });

    onBeforeUnmount(() => {
      if (resizeObserver.value) {
        resizeObserver.value.disconnect();
        resizeObserver.value = undefined;
      }
      if (rightOptionObserver) {
        rightOptionObserver.disconnect();
        rightOptionObserver = undefined;
      }
      if (tippyInstance) {
        tippyInstance.destroy();
        tippyInstance = null;
      }
      if (measureRef.value) {
        measureRef.value.innerHTML = '';
      }
    });

    watch(
      () => tags.value,
      (newTags, oldTags) => {
        const wasEmpty = !oldTags || oldTags.length === 0;
        const isNowNonEmpty = newTags && newTags.length > 0;

        nextTick(() => {
          // 在 tags 从空变为非空时，DOM 由 null 新建，需要重新绑定 ResizeObserver 和初始化测量元素
          if (wasEmpty && isNowNonEmpty) {
            if (containerRef.value && resizeObserver.value) {
              resizeObserver.value.disconnect();
              resizeObserver.value.observe(containerRef.value);
            }
            initMeasureElements();
          }
          debouncedCalculate();
        });
      },
      { deep: true },
    );

    watch(
      () => hiddenCount.value,
      (val) => {
        if (val > 0) {
          nextTick(initActionPop);
        } else if (tippyInstance) {
          tippyInstance.destroy();
          tippyInstance = null;
        }
      },
    );

    return () => {
      if (tags.value.length === 0) return null;

      return (
        <div
          ref={containerRef}
          class='scene-filter-tags'
        >
          <div
            ref={tipsPanelRef}
            class='scene-filter-tags-tips-panel'
          >
            {tags.value.map((tag, index) => (
              <span
                key={index}
                class='tag-item'
              >
                <span class='tag-key'>{tag.name}</span>
                <span class='tag-separator'>{tag.opDisplay}</span>
                <span class='tag-value'>{tag.value.slice(tag.name.length + tag.opDisplay.length)}</span>
              </span>
            ))}
          </div>

          <div
            ref={measureRef}
            class='measure-box'
          />

          {visibleTags.value.map((tag, index) => (
            <span
              key={tag.key}
              style={{
                marginRight: index < visibleTags.value.length - 1 ? `${TAG_GAP}px` : '0',
              }}
              class='tag-item'
            >
              <span class='tag-key'>{tag.name}</span>
              <span class='tag-separator'>{tag.opDisplay}</span>
              <span class='tag-value'>{tag.value.slice(tag.name.length + tag.opDisplay.length)}</span>
            </span>
          ))}

          {hiddenCount.value > 0 && (
            <span
              ref={indicatorRef}
              style={{
                marginLeft: visibleTags.value.length > 0 ? `${TAG_GAP}px` : '0',
              }}
              class='tag-more-indicator'
            >
              +{hiddenCount.value}
            </span>
          )}
        </div>
      );
    };
  },
});
