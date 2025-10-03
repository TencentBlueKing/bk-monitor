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
import { computed, defineComponent, onMounted, onBeforeUnmount, type Ref, ref } from 'vue';
import './index.scss';

export default defineComponent({
  props: {
    outerWidth: {
      type: Number,
      default: 0,
    },
    innerWidth: {
      type: Number,
      default: 0,
    },
    right: {
      type: Number,
      default: 0,
    },
  },
  emits: ['scroll-change'],
  setup(props, { emit, expose }) {
    const scrollXElementStyle = computed(() => {
      return {
        width: `${props.outerWidth}px`,
        '--right': `${props.right}px`,
      };
    });

    const scrollXInnerElementStyle = computed(() => {
      return {
        width: `${props.innerWidth - 1}px`,
      };
    });
    const refSrollRoot: Ref<HTMLElement> = ref();

    const renderScrollXBar = () => {
      return (
        <div
          ref={refSrollRoot}
          style={scrollXElementStyle.value}
          class='bklog-scroll-x'
        >
          <div style={scrollXInnerElementStyle.value} />
        </div>
      );
    };

    let isAnimating = false;
    const handleScrollEvent = (event: MouseEvent) => {
      event.stopPropagation();
      event.preventDefault();
      event.stopImmediatePropagation();

      if (!isAnimating) {
        isAnimating = true;
        requestAnimationFrame(() => {
          emit('scroll-change', { ...event, target: event.target || refSrollRoot.value });
          isAnimating = false;
        });
      }
    };

    onMounted(() => {
      refSrollRoot.value?.addEventListener('scroll', handleScrollEvent);
    });

    onBeforeUnmount(() => {
      refSrollRoot.value?.removeEventListener('scroll', handleScrollEvent);
    });

    expose({
      scrollLeft: (left: number) => {
        refSrollRoot.value.scrollLeft = left;
      },
      getScrollLeft: () => {
        return refSrollRoot.value.scrollLeft ?? 0;
      },
    });

    return {
      renderScrollXBar,
    };
  },
  render() {
    return this.renderScrollXBar();
  },
});
