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
import {
  defineComponent,
  nextTick,
  onBeforeUnmount,
  ref as deepRef,
  shallowRef,
  watch,
  computed,
  type PropType,
} from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Tag } from 'bkui-vue';

import type { SlotReturnValue } from 'tdesign-vue-next';

import './collapse-tags.scss';

export default defineComponent({
  name: 'TagShow',
  props: {
    data: {
      type: Array as PropType<any[] | string[]>,
      default: () => [],
    },
    filter: {
      type: Array,
      default: () => [],
    },
    styleName: {
      type: String,
      default: '',
    },
    /** tag 之间的水平间距（默认为 4px），不建议另外css单独设置，计算tag宽度溢出时需要使用该值进行计算 */
    tagColGap: {
      type: Number,
      default: 4,
    },
    enableEllipsis: {
      type: Boolean,
      default: true,
    },
    ellipsisTip: {
      type: Function as PropType<(ellipsisList: any[] | string[]) => SlotReturnValue>,
    },
  },
  setup(props) {
    let resizeObserver = null;
    let lastTagContainerWidth = 0;

    const tagContainerRef = deepRef(null);
    const sectionRef = deepRef(null);
    const maxCountCollectTagRef = shallowRef(null);
    const calculateTagCount = shallowRef(props?.data?.length || 0);

    const cssVars = computed(() => ({
      '--tag-col-gap': `${props.tagColGap}px`,
    }));

    /**
     * @description 核心计算逻辑（带防抖）
     *
     **/
    const calculateOverflow = useDebounceFn(() => {
      calculateTagCount.value = props?.data?.length || 0;
      if (!props.enableEllipsis) {
        return;
      }
      requestAnimationFrame(() => {
        //
        const tagsList = sectionRef.value?.children || [];
        // 获取容器宽度
        const containerWidth = sectionRef.value?.parentNode?.getBoundingClientRect?.().width;
        let totalWidth = 0;
        let visibleCount = 0;

        // 第一轮：计算在不显示折叠标签时能容纳的标签数量
        for (let i = 0; i < tagsList.length; i++) {
          const tagWidth = tagsList[i]?.getBoundingClientRect?.().width;
          const newWidth = totalWidth + tagWidth + (i > 0 ? props.tagColGap : 0);
          if (newWidth < containerWidth) {
            totalWidth = newWidth;
            visibleCount = i + 1;
          } else {
            break;
          }
        }

        // 如果所有标签都能显示，则不需要折叠
        if (visibleCount === tagsList.length) {
          calculateTagCount.value = visibleCount;
          return;
        }

        // 如果执行到这里了，那么说明 折叠标签元素 肯定是需要显示的，所以 totalWidth 需要加上 折叠标签的宽度以及间隔宽度
        const collectTagWidth = maxCountCollectTagRef.value?.getBoundingClientRect?.().width || 0;
        totalWidth = totalWidth + collectTagWidth + props.tagColGap;
        if (totalWidth < containerWidth) {
          calculateTagCount.value = visibleCount;
          return;
        }

        // 第二轮：走到这里则说明剩余的空间不足以显示折叠标签，所以需要逐个递减至可以容纳折叠标签
        while (visibleCount > 0) {
          visibleCount--;
          const tagWidth = tagsList[visibleCount]?.getBoundingClientRect?.().width;
          totalWidth = totalWidth - tagWidth - props.tagColGap;
          if (totalWidth < containerWidth) break;
        }
        calculateTagCount.value = Math.max(visibleCount, 0); // 确保visibleCount不为负数
      });
    }, 200);

    /**
     * @description 设置观察器(目前场景只需要监听水平方向)
     *
     **/
    function setupObserver() {
      if (!resizeObserver) {
        resizeObserver = new ResizeObserver(entries => {
          for (const entry of entries) {
            const currentWidth = entry.contentRect.width;
            if (currentWidth === lastTagContainerWidth) {
              return;
            }
            lastTagContainerWidth = currentWidth;
            calculateOverflow();
          }
        });
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

    watch([() => props.data, () => props.enableEllipsis], () => {
      calculateOverflow();
    });

    watch(
      () => tagContainerRef.value,
      nVal => {
        if (!nVal) {
          return;
        }
        cleanupObserver();
        nextTick(setupObserver);
      },
      { immediate: true, deep: true }
    );

    onBeforeUnmount(() => {
      cleanupObserver();
    });

    return { calculateTagCount, tagContainerRef, sectionRef, maxCountCollectTagRef, cssVars };
  },
  render() {
    /** 数据总长度 */
    const dataLen = (this.data || []).length;
    if (dataLen === 0) {
      return;
    }
    /** 折叠个数 */
    const collapseCount = dataLen - this.calculateTagCount;
    /** 是否展示折叠标签 */
    const canShowCollapseTag = collapseCount > 0;
    /** 需要渲染的数据数组 */
    const showList = (this.data || []).slice(0, this.calculateTagCount);
    /** 折叠的数据数组 */
    const ellipsisList = (this.data || []).slice(this.calculateTagCount);
    return (
      <span
        ref='tagContainerRef'
        style={this.cssVars}
        class='bk-common-tag-show'
      >
        <span
          ref='sectionRef'
          class='item-tags'
        >
          {showList.map((tag, index) => {
            return (
              this.$slots?.customTag?.(tag, index) || (
                <Tag key={index}>{{ default: () => this.$slots?.tagDefault?.(tag, index) || tag }}</Tag>
              )
            );
          })}
        </span>
        {canShowCollapseTag && (
          <span
            class='collapse-tag'
            v-tippy={{
              content: this.ellipsisTip ? this.ellipsisTip(ellipsisList) : ellipsisList.join(','),
              theme: 'dark text-wrap max-width-50vw',
              delay: 300,
            }}
          >
            +{collapseCount}
          </span>
        )}
        <span
          ref='maxCountCollectTagRef'
          class='collapse-tag collapse-tag-fill'
        >
          +{dataLen}
        </span>
      </span>
    );
  },
});
