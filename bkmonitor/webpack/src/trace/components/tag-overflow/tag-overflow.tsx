/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import {
  type PropType,
  type VNode,
  computed,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  shallowRef,
  watch,
} from 'vue';

import { throttle } from 'lodash';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';

import './tag-overflow.scss';

const BADGE_CLASS = 'tag-overflow__badge';
/** +N 占位预估宽度 */
const TIPS_TAG_PLACEHOLDER_WIDTH = 45;
/** 标签间距（与样式 margin-left 一致） */
const TAG_MARGIN = 6;

export default defineComponent({
  name: 'TagOverflow',
  props: {
    /** 标签数据列表 */
    list: {
      type: Array as PropType<unknown[]>,
      default: () => [],
    },
    /** 从 list item 提取 tip 文案；不传则 String(item) */
    getLabel: {
      type: Function as PropType<(item: unknown, index: number) => string>,
      default: undefined,
    },
    /** 溢出徽标额外 class */
    overflowClass: {
      type: [String, Array] as PropType<string | string[]>,
      default: '',
    },
    /** 外部依赖变化时重新测量（如列宽、visibleColumns） */
    recalcKey: {
      type: [String, Number, Boolean] as PropType<boolean | number | string>,
      default: '',
    },
  },
  emits: {
    overflowClick: (_count: number) => true,
  },
  setup(props, { emit, slots }) {
    const rootRef = shallowRef<HTMLElement>();
    const moreRef = shallowRef<HTMLElement>();
    const tagListRef = shallowRef<HTMLElement>();
    const tipsPanelRef = shallowRef<HTMLElement>();

    /** 可视区域内实际渲染的标签数量 */
    const renderTagNum = shallowRef(1);

    let tippyIns: Instance | undefined;
    let resizeObserver: ResizeObserver | undefined;
    /** 计算版本号：丢弃过期的异步结果 */
    let calcVersion = 0;
    let calcFrameId = 0;

    const moreTagCount = computed(() => Math.max(0, (props.list?.length || 0) - renderTagNum.value));

    const resolveLabel = (item: unknown, index: number) => {
      if (props.getLabel) {
        return props.getLabel(item, index);
      }
      return String(item ?? '');
    };

    /**
     * 按容器宽度计算可展示标签数（TagBlock 算法）：
     * 隐藏测量区取真实宽度 → 预留 +N 占位 → 逐项累加直至超限
     */
    const calcRenderTagNum = () => {
      const version = ++calcVersion;
      if (calcFrameId) {
        cancelAnimationFrame(calcFrameId);
      }
      nextTick(() => {
        if (version !== calcVersion || !rootRef.value) {
          return;
        }
        if (!props.list?.length) {
          renderTagNum.value = 0;
          return;
        }
        calcFrameId = requestAnimationFrame(() => {
          calcFrameId = 0;
          if (version !== calcVersion || !rootRef.value || !tagListRef.value) {
            return;
          }

          const { width: maxWidth } = rootRef.value.getBoundingClientRect();
          const allTagEleList = Array.from(tagListRef.value.children) as HTMLElement[];
          if (!allTagEleList.length) {
            return;
          }

          let nextRenderTagNum = renderTagNum.value;
          if (tagListRef.value.getBoundingClientRect().width <= maxWidth) {
            nextRenderTagNum = props.list.length;
          } else {
            let renderTagCount = 0;
            let totalTagWidth = -TAG_MARGIN;
            for (let i = 0; i < allTagEleList.length; i++) {
              const { width: tagWidth } = allTagEleList[i].getBoundingClientRect();
              const availableWidth = maxWidth - (i < allTagEleList.length - 1 ? TIPS_TAG_PLACEHOLDER_WIDTH : 0);
              if (tagWidth > availableWidth) {
                break;
              }
              totalTagWidth += tagWidth + TAG_MARGIN;
              if (totalTagWidth + TIPS_TAG_PLACEHOLDER_WIDTH <= maxWidth) {
                renderTagCount += 1;
              } else {
                break;
              }
            }
            nextRenderTagNum = renderTagCount;
          }

          if (renderTagNum.value !== nextRenderTagNum) {
            renderTagNum.value = nextRenderTagNum;
          }
        });
      });
    };

    const destroyTippy = () => {
      if (!tippyIns) {
        return;
      }
      tippyIns.hide();
      tippyIns.disable();
      tippyIns.destroy();
      tippyIns = undefined;
    };

    const setupTippy = () => {
      if (moreTagCount.value < 1) {
        destroyTippy();
        return;
      }
      nextTick(() => {
        if (!moreRef.value || !tipsPanelRef.value) {
          return;
        }
        if (tippyIns) {
          tippyIns.enable();
          return;
        }
        tippyIns = tippy(moreRef.value as SingleTarget, {
          allowHTML: true,
          appendTo: () => document.body,
          arrow: true,
          content: tipsPanelRef.value,
          hideOnClick: true,
          interactive: true,
          maxWidth: 400,
          offset: [0, 8],
          placement: 'top',
          theme: 'light',
          trigger: 'mouseenter',
          zIndex: 999999,
        });
      });
    };

    watch(
      () => [props.list, props.recalcKey],
      () => {
        calcRenderTagNum();
      },
      {
        deep: true,
        flush: 'post',
      }
    );

    watch(moreTagCount, setupTippy, { immediate: true });

    const handleOverflowClick = (e: MouseEvent) => {
      e.stopPropagation();
      emit('overflowClick', moreTagCount.value);
    };

    onMounted(() => {
      calcRenderTagNum();
      resizeObserver = new ResizeObserver(
        throttle(() => {
          calcRenderTagNum();
        }, 100)
      );
      if (rootRef.value) {
        resizeObserver.observe(rootRef.value);
      }
    });

    onBeforeUnmount(() => {
      destroyTippy();
      resizeObserver?.disconnect();
      if (calcFrameId) {
        cancelAnimationFrame(calcFrameId);
      }
    });

    return () => {
      const list = props.list || [];
      const visibleList = list.slice(0, renderTagNum.value);
      const overflowList = list.slice(renderTagNum.value);

      return (
        <div
          ref={rootRef}
          class='tag-overflow'
        >
          {list.length ? (
            <>
              {visibleList.map((item, index) => slots.default?.({ item, index }) as VNode)}
              {moreTagCount.value > 0 ? (
                <span
                  ref={moreRef}
                  class={[BADGE_CLASS, props.overflowClass]}
                  onClick={handleOverflowClick}
                >
                  {`+${moreTagCount.value}`}
                </span>
              ) : null}
            </>
          ) : (
            slots.empty?.()
          )}
          {/* 隐藏测量区：预渲染全部标签以获取真实宽度 */}
          <div
            ref={tagListRef}
            class='tag-overflow__measure'
          >
            {list.map((item, index) => slots.default?.({ item, index }) as VNode)}
          </div>
          <div style={{ display: 'none' }}>
            <div
              ref={tipsPanelRef}
              class='tag-overflow__more-panel'
            >
              {overflowList.map((item, index) => {
                const realIndex = renderTagNum.value + index;
                const label = resolveLabel(item, realIndex);
                return (
                  <div
                    key={`${label}__overflow__${realIndex}`}
                    class='tag-overflow__more-panel-item'
                  >
                    {slots.default?.({ item, index: realIndex }) as VNode}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      );
    };
  },
});
