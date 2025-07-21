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
import { defineComponent, onUnmounted, PropType, Ref, ref, watch } from 'vue';
import useResizeObserve from '../../hooks/use-resize-observe';
import './index.scss';
import PopInstanceUtil from '../../global/pop-instance-util';
import { Placement } from 'tippy.js';

export default defineComponent({
  props: {
    list: {
      type: Array,
      required: true,
      default: () => {},
    },
    itemRender: {
      type: Function,
      default: undefined,
    },
    activeEllipsisCount: {
      type: Boolean,
      default: false,
    },
    hiddenClassName: {
      type: String,
      default: 'bklog-v3-ellipsis-hidden',
    },
    tagWidth: {
      type: Number,
      default: 30,
    },
    showFullTooltip: {
      type: String as PropType<'auto' | 'disable' | 'enable'>,
      default: 'auto',
    },
    placement: {
      type: String as PropType<Placement>,
      default: 'auto',
    },
  },
  setup(props, { slots }) {
    const refRootElement: Ref<HTMLElement> = ref(null);
    const refEllipsisNumElement: Ref<HTMLElement> = ref(null);
    const refContainerElement: Ref<HTMLElement> = ref(null);

    const addedMouseHoverEvent = ref(false);

    const showMoreItemNum = ref(false);
    const moreItemNum = ref(0);

    let toolTipInstance: PopInstanceUtil = null;

    const { observeElement, stopObserve, isStoped } = useResizeObserve(
      () => refContainerElement.value,
      () => {
        if (refContainerElement.value) {
          const { scrollWidth, offsetWidth } = refRootElement.value;

          if (scrollWidth > offsetWidth) {
            const childElements = Array.from(refContainerElement.value.children) as HTMLElement[];
            const overflowWidth = scrollWidth - offsetWidth + props.tagWidth;

            let hiddenWidth = 0;
            let index = childElements.length - 1;
            let stop = false;
            let hiddenItemCount = 0;

            childElements.forEach(item => {
              if (item.classList.contains(props.hiddenClassName)) {
                item.classList.remove(props.hiddenClassName);
              }
            });

            while (!stop && index > 0) {
              const node = childElements[index];
              if (node !== refEllipsisNumElement.value) {
                hiddenWidth += node.offsetWidth;
                hiddenItemCount += 1;
                index = index - 1;
                node.classList.add(props.hiddenClassName);

                if (hiddenWidth > overflowWidth) {
                  stop = true;
                }
              }
            }

            if (props.list.length > 1) {
              showMoreItemNum.value = true;
              moreItemNum.value = hiddenItemCount;
            }
          }
        }
      },
      120,
      props.activeEllipsisCount
    );

    const handleMouseenter = (e: MouseEvent) => {
      if (toolTipInstance === null) {
        toolTipInstance = new PopInstanceUtil({
          refContent: () => {
            const div = document.createElement('div');
            div.classList.add('bklog-v3-ellipsis-more-tip');
            div.append(refContainerElement.value?.cloneNode(true));
            return div;
          },
          tippyOptions: {
            placement: props.placement,
            theme: 'log-light',
          },
        });
      }

      toolTipInstance.show(e.target, true);
    };
    const handleMouseleave = () => {
      toolTipInstance?.hide();
    };

    const addMouseHoverEvent = () => {
      if (props.showFullTooltip !== 'disable') {
        if (props.showFullTooltip === 'auto') {
          if (showMoreItemNum.value) {
            if (!addedMouseHoverEvent.value) {
              refRootElement.value?.addEventListener('mouseenter', handleMouseenter);
              refRootElement.value?.addEventListener('mouseleave', handleMouseleave);
              addedMouseHoverEvent.value = true;
            }

            return;
          }
        }

        if (props.showFullTooltip === 'enable') {
          if (!addedMouseHoverEvent.value) {
            refRootElement.value?.addEventListener('mouseenter', handleMouseenter);
            refRootElement.value?.addEventListener('mouseleave', handleMouseleave);
            addedMouseHoverEvent.value = true;
          }

          return;
        }

        if (addedMouseHoverEvent.value) {
          refRootElement.value?.removeEventListener('mouseenter', handleMouseenter);
          refRootElement.value?.removeEventListener('mouseleave', handleMouseleave);
          addedMouseHoverEvent.value = false;
        }
      }
    };

    watch(
      () => [props.activeEllipsisCount],
      () => {
        if (isStoped.value && props.activeEllipsisCount) {
          observeElement();
        }

        if (!props.activeEllipsisCount && !isStoped.value) {
          stopObserve();
        }
      },
      { immediate: true }
    );

    watch(() => showMoreItemNum.value, addMouseHoverEvent);

    onUnmounted(() => {
      if (addedMouseHoverEvent.value) {
        refRootElement.value?.removeEventListener('mouseenter', handleMouseenter);
        refRootElement.value?.removeEventListener('mouseleave', handleMouseleave);
      }

      toolTipInstance?.uninstallInstance();
    });

    return () => (
      <div
        ref={refRootElement}
        class='bklgo-v3-ellipsis-tag-list'
      >
        <div ref={refContainerElement}>
          {props.list.map(item => {
            if (typeof props.itemRender === 'function') {
              return props.itemRender(item);
            }

            return slots.item?.(item) ?? <span>{item}</span>;
          })}
        </div>
        {showMoreItemNum.value && props.list.length > 1 ? (
          <span
            class='bklog-v3-ellipsis-num'
            ref={refEllipsisNumElement}
          >
            +{moreItemNum.value}
          </span>
        ) : null}
      </div>
    );
  },
});
