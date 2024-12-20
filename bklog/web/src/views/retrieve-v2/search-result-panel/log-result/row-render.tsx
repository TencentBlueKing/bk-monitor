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
import { computed, defineComponent, inject, onBeforeUnmount, onMounted, Ref, ref, watch } from 'vue';
import { RowProxyData } from './log-row-attributes';

export default defineComponent({
  props: {
    rowIndex: {
      type: Number,
      default: 0,
    },
  },
  setup(props, { slots }) {
    const refRowNodeRoot: Ref<HTMLElement> = ref();
    const intersectionObserver: IntersectionObserver = inject('intersectionObserver');
    const resizeObserver: ResizeObserver = inject('resizeObserver');
    const rowProxy: Ref<RowProxyData> = inject('rowProxy');

    const rowStyle = computed(() => {
      return {
        minHeight: `${rowProxy.value[props.rowIndex]?.height ?? 40}px`,
      };
    });

    const visible = computed(() => {
      return (rowProxy.value[props.rowIndex]?.visible ?? true) || !(rowProxy.value[props.rowIndex]?.mounted ?? false);
    });

    const renderRowVNode = () => {
      return (
        <div
          data-row-index={props.rowIndex}
          style={rowStyle.value}
        >
          <div
            ref={refRowNodeRoot}
            class={['bklog-row-observe', { 'is-pending': !visible.value }]}
            data-row-index={props.rowIndex}
            data-is-pending={!visible.value}
          >
            {slots.default?.()}
          </div>
          <div class={['row-pending', { 'is-pending': !visible.value }]}></div>
        </div>
      );
    };

    onMounted(() => {
      intersectionObserver?.observe(refRowNodeRoot.value);
      resizeObserver?.observe(refRowNodeRoot.value);
    });

    onBeforeUnmount(() => {
      intersectionObserver?.unobserve(refRowNodeRoot.value);
      resizeObserver?.unobserve(refRowNodeRoot.value);
    });

    return {
      renderRowVNode,
    };
  },
  render() {
    return this.renderRowVNode();
  },
});
