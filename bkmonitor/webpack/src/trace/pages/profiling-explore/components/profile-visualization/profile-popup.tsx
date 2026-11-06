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
import { type PropType, defineComponent, nextTick, onMounted, shallowRef, watch } from 'vue';

import { useTippy } from 'vue-tippy';

export default defineComponent({
  name: 'ProfilePopup',
  props: {
    point: { type: Object as PropType<null | { x: number; y: number }>, default: null },
    interactive: Boolean,
  },
  emits: ['close'],
  setup(props, { emit }) {
    const anchor = shallowRef<HTMLElement>();
    const content = shallowRef<HTMLElement>();
    const popup = useTippy(anchor, {
      content: () => content.value,
      trigger: 'manual',
      arrow: false,
      duration: 0,
      maxWidth: 430,
      placement: 'right-start',
      offset: [0, 16],
      theme: props.interactive ? 'profiling-menu' : 'profiling-detail',
      interactive: props.interactive,
      hideOnClick: false,
      appendTo: element => {
        // 浮层留在微应用 ShadowRoot 内才能继承图标和主题样式，挂到 body 会丢失样式。
        const root = element.getRootNode();
        return root instanceof ShadowRoot ? root.querySelector('#app') || element.parentElement : document.body;
      },
      onClickOutside: () => {
        if (props.interactive) emit('close');
      },
    });
    function update() {
      if (!props.point) {
        popup.hide();
        return;
      }
      const { x, y } = props.point;
      popup.setProps({ getReferenceClientRect: () => new DOMRect(x, y, 0, 0) });
      popup.show();
    }
    onMounted(() => nextTick(update));
    watch(
      () => props.point,
      () => nextTick(update)
    );
    return { anchor, content };
  },
  render() {
    return (
      <div
        ref='anchor'
        class='profile-popup-anchor'
      >
        <div style={{ display: 'none' }}>
          <div
            ref='content'
            class={this.interactive ? 'profile-context-menu' : 'profile-detail-tip'}
          >
            {this.$slots.default?.()}
          </div>
        </div>
      </div>
    );
  },
});
