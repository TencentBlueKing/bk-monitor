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
import { type PropType, type VNode, defineComponent, ref } from 'vue';

import { AngleRight } from 'bkui-vue/lib/icon';

import './collapse.scss';

export default defineComponent({
  name: 'PropsCollapsePanel',
  props: {
    defaultCollapsed: {
      type: Boolean,
      default: true,
    },
    title: {
      type: String || (Object as PropType<VNode>),
    },
    suffix: {
      type: String || (Object as PropType<VNode>),
    },
    lightweightTitle: Boolean,
    zIndex: {
      type: Number,
      default: 1000,
    },
  },
  emits: ['update:modelValue', 'change', 'ensure', 'clear'],
  setup(props, { slots }) {
    const collapsed = ref(props.defaultCollapsed);
    return () => (
      <div class={['failure-props-collapse', { 'failure-props-collapse-expand': collapsed.value }]}>
        <div
          style={{ zIndex: props.zIndex }}
          class='failure-props-collapse-header overflow-hidden flex-row align-items-center justify-content-between cursor-pointer'
          onClick={() => (collapsed.value = !collapsed.value)}
        >
          <span class={{ 'text-title font-bold': !props.lightweightTitle }}>{props.title}</span>
          <span />
          <AngleRight class={[{ collapsed: collapsed.value }, 'collapsed-icon']} />
        </div>
        <div class='failure-props-collapse-content-wrap'>
          {collapsed.value ? <div class='failure-props-collapse-content'>{slots?.default?.()}</div> : ''}
        </div>
      </div>
    );
  },
});
