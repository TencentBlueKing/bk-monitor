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
      type: Array as PropType<string[]>,
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
      type: Function as PropType<(ellipsisList: string[]) => SlotReturnValue>,
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
        const domList = sectionRef.value?.children || [];
        const maxWidth = sectionRef.value?.parentNode?.clientWidth;
        let num = 0;
        let index = -1;

        for (let i = 0; i < domList.length; i++) {
          const clientWidth = domList[i]?.clientWidth;
          num = clientWidth + num + props.tagColGap;

          if (num >= maxWidth) {
            num = num - clientWidth - props.tagColGap;
            break;
          }
          index = i;
        }
        if (domList.length >= index + 1) {
          // +1 是因为兼容实际为浮点数但 clientWidth 获取到的是舍弃小数后的整数的边际场景
          const collectTagWidth = (maxCountCollectTagRef.value?.clientWidth || 0) + 1;
          for (let i = index; i > 0; i--) {
            if (num + collectTagWidth < maxWidth) {
              break;
            }
            const clientWidth = domList[i]?.clientWidth;
            num = num - clientWidth - props.tagColGap;
            index = i - 1;
          }
        }
        calculateTagCount.value = index + 1;
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
          {showList.map((tag, index) => (
            <Tag
              key={index}
              ext-cls={this.styleName}
            >
              {{ default: () => this.$slots?.tagDefault?.(tag) || tag }}
            </Tag>
          ))}
        </span>
        {canShowCollapseTag && (
          <span
            class='top-bar-tag'
            v-tippy={{
              content: this.ellipsisTip?.(ellipsisList) || ellipsisList.join(','),
              theme: 'dark text-wrap max-width-50vw',
              delay: 300,
            }}
          >
            +{collapseCount}
          </span>
        )}
        <span
          ref='maxCountCollectTagRef'
          class='top-bar-tag top-bar-tag-fill'
        >
          +{dataLen}
        </span>
      </span>
    );
  },
});
