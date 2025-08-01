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

import { defineComponent, ref } from 'vue';

import './drag-container.scss';

export default defineComponent({
  name: 'DragContainer',
  props: {
    width: { type: Number, required: true },
    isShow: { type: Boolean, required: true },
    visibleFields: { type: Array, default: () => [] },
    isRefreshCollect: { type: Boolean, default: false },
  },

  emits: ['update:width', 'update:isShow'],
  setup(props, { emit, slots }) {
    // 收藏最小栏宽度
    const collectMinWidth = ref(160);
    // 收藏栏最大宽度
    const collectMaxWidth = ref(400);
    // 当前收藏容器的宽度
    const currentTreeBoxWidth = ref(null);
    const currentScreenX = ref(null);
    // 是否正在拖拽
    const isChangingWidth = ref(false);

    const dragBegin = e => {
      isChangingWidth.value = true;
      currentTreeBoxWidth.value = props.width;
      currentScreenX.value = e.screenX;
      window.addEventListener('mousemove', dragMoving, { passive: true });
      window.addEventListener('mouseup', dragStop, { passive: true });
    };

    const dragMoving = e => {
      const newTreeBoxWidth = currentTreeBoxWidth.value + e.screenX - currentScreenX.value;
      if (newTreeBoxWidth < collectMinWidth.value) {
        emit('update:width', 240);
        emit('update:isShow', false);
        dragStop();
        localStorage.setItem('isAutoShowCollect', 'false');
      } else if (newTreeBoxWidth >= collectMaxWidth.value) {
        emit('update:width', collectMaxWidth.value);
      } else {
        emit('update:width', newTreeBoxWidth);
      }
    };
    const dragStop = () => {
      isChangingWidth.value = false;
      currentTreeBoxWidth.value = null;
      currentScreenX.value = null;
      window.removeEventListener('mousemove', dragMoving);
      window.removeEventListener('mouseup', dragStop);
    };

    return () => {
      return (
        <div
          style={{
            width: props.isShow ? `${props.width}px` : 0,
            display: props.isShow ? 'block' : 'none',
          }}
          class='drag-container-box'
        >
          {slots.default?.()}
          <div
            class={['drag-border', { 'drag-ing': isChangingWidth.value }]}
            onMousedown={dragBegin}
          ></div>
        </div>
      );
    };
  },
});
