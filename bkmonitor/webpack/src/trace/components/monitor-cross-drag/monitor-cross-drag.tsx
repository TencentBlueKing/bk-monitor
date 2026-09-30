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
import { type PropType, defineComponent, getCurrentInstance, onActivated, onMounted } from 'vue';

import { useVerticalResize } from '../../hooks/use-vertical-resize';

import type { VerticalResizeDirection } from '../../hooks/use-vertical-resize';

import './monitor-cross-drag.scss';

export default defineComponent({
  name: 'MonitorCrossDrag',
  props: {
    /** 可拖动的最小容器高度 */
    minHeight: {
      type: Number,
    },
    /** 可拖动的最大容器高度 */
    maxHeight: {
      type: Number,
    },
    /** 拖拽方向：down 鼠标下移变高（默认），up 鼠标上移变高 */
    direction: {
      type: String as PropType<VerticalResizeDirection>,
      default: 'down',
    },
  },
  emits: {
    move: (resultHeight: number, cancelFn: () => void) =>
      typeof resultHeight === 'number' && typeof cancelFn === 'function',
  },
  setup(props, { emit }) {
    const vmInstance = getCurrentInstance();

    /** 被 resize 的元素：拖拽条的父元素 */
    function getResizeTarget(): HTMLElement | null {
      return (vmInstance?.vnode?.el as Element | null)?.parentElement ?? null;
    }

    const { isResizing, startResize, stopResize } = useVerticalResize({
      getHeight: () => getResizeTarget()?.getBoundingClientRect().height ?? 0,
      getMaxHeight: () => props.maxHeight,
      getMinHeight: () => props.minHeight,
      onResize: height => emit('move', height, stopResize),
    });

    onMounted(() => {
      initConfig();
    });

    onActivated(() => {
      initConfig();
    });

    /**
     * @description: 初始化 resize 操作所需要的配置
     *               父元素未定位时补 position: relative：绝对定位的子元素（折叠态 header、悬浮拖拽条）
     *               需要它作为包含块；父元素已有定位时保持原样，避免覆盖调用方自己的布局。
     */
    function initConfig() {
      setTimeout(() => {
        const parent = getResizeTarget();
        if (parent && getComputedStyle(parent).position === 'static') {
          parent.style.position = 'relative';
        }
      }, 30);
    }

    /**
     * @description: mousedown触发回调
     * @param {MouseEvent} mouseDownEvent 鼠标事件
     */
    function handleMouseDown(mouseDownEvent: MouseEvent) {
      startResize(mouseDownEvent, props.direction);
    }

    return {
      handleMouseDown,
      isResizing,
    };
  },
  render() {
    return (
      <div
        class={['monitor-cross-drag', { 'is-resizing': this.isResizing }]}
        onMousedown={this.handleMouseDown}
      />
    );
  },
});
