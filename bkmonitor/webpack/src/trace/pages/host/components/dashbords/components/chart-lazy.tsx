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

import { defineComponent, onBeforeUnmount, onMounted, shallowRef, useTemplateRef } from 'vue';

/**
 * 懒渲染容器：仅当自身滚动进入视口（含 100px 预加载边距）后才渲染默认插槽，
 * 用于推迟图表卡片的挂载与取数，避免一次性请求全部图表。
 */
export default defineComponent({
  name: 'ChartLazy',
  props: {
    /** 占位最小高度，避免未渲染时高度塌陷导致 IntersectionObserver 误判 */
    minHeight: {
      type: [Number, String],
      default: 240,
    },
  },
  setup(props, { slots }) {
    const root = useTemplateRef<HTMLElement>('root');
    const visible = shallowRef(false);
    let observer: IntersectionObserver | null = null;

    onMounted(() => {
      observer = new IntersectionObserver(
        entries => {
          if (entries.some(entry => entry.isIntersecting)) {
            visible.value = true;
            observer?.disconnect();
            observer = null;
          }
        },
        { rootMargin: '100px' }
      );
      if (root.value) observer.observe(root.value);
    });

    onBeforeUnmount(() => {
      observer?.disconnect();
      observer = null;
    });

    return () => (
      <div
        ref='root'
        style={{ minHeight: typeof props.minHeight === 'number' ? `${props.minHeight}px` : props.minHeight }}
        class='chart-lazy'
      >
        {visible.value ? slots.default?.() : null}
      </div>
    );
  },
});
