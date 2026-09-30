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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { onBeforeUnmount, shallowRef } from 'vue';

/** 拖拽方向：down 鼠标下移变高（默认），up 鼠标上移变高（底部弹出场景） */
export type VerticalResizeDirection = 'down' | 'up';

interface IUseVerticalResizeOptions {
  /** 当前高度，拖拽中每帧读取；由消费方提供，避免直接读 rect 受 box-sizing 影响 */
  getHeight: () => number;
  /** 高度上限，按下时读取一次；返回 undefined 表示不限制 */
  getMaxHeight?: () => number | undefined;
  /** 高度下限，按下时读取一次；返回 undefined 表示不限制 */
  getMinHeight?: () => number | undefined;
  /** 高度变化回调 */
  onResize: (height: number) => void;
}

/**
 * @description 纵向拖拽调高的公共逻辑：按下拖拽条后跟随鼠标纵向位移改高度。
 *              采用增量模型（每帧用当前高度累加本次位移），撞到上下限后回拖可立即跟随，不产生回程空行程。
 * @param {IUseVerticalResizeOptions} options 高度读写与边界配置
 * @returns {{ isResizing: ShallowRef<boolean>; startResize: Function; stopResize: Function }} 拖拽中与开始 / 结束拖拽
 */
export function useVerticalResize(options: IUseVerticalResizeOptions) {
  /** 当前拖拽的解绑函数，非空表示正在拖拽 */
  let stop: (() => void) | null = null;
  /** 是否处于拖拽中，供拖拽条渲染激活态 */
  const isResizing = shallowRef(false);

  /** 结束拖拽：解绑监听并恢复拖拽前的光标与选中行为 */
  function stopResize() {
    stop?.();
  }

  /**
   * @description 开始拖拽
   * @param {MouseEvent} e 鼠标按下事件
   * @param {VerticalResizeDirection} direction 拖拽方向，缺省为 down
   */
  function startResize(e: MouseEvent, direction: VerticalResizeDirection = 'down') {
    e.preventDefault();
    stopResize();
    isResizing.value = true;
    const sign = direction === 'up' ? -1 : 1;
    const minHeight = options.getMinHeight?.();
    const maxHeight = options.getMaxHeight?.();
    /** 拖拽期间锁定光标并屏蔽文本选中 / 拖拽，结束后原样恢复 */
    const sourceBodyCursor = document.body.style.cursor;
    const sourceSelectStart = document.onselectstart;
    const sourceDragStart = document.ondragstart;
    document.body.style.cursor = 'row-resize';
    document.onselectstart = () => false;
    document.ondragstart = () => false;

    let lastY = e.clientY;
    const handleMove = (event: MouseEvent) => {
      const delta = (event.clientY - lastY) * sign;
      lastY = event.clientY;
      let height = options.getHeight() + delta;
      if (minHeight !== undefined) height = Math.max(minHeight, height);
      if (maxHeight !== undefined) height = Math.min(maxHeight, height);
      options.onResize(height);
    };
    const handleUp = () => stopResize();
    stop = () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
      document.body.style.cursor = sourceBodyCursor;
      document.onselectstart = sourceSelectStart;
      document.ondragstart = sourceDragStart;
      stop = null;
      isResizing.value = false;
    };
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  }

  onBeforeUnmount(stopResize);

  return { isResizing, startResize, stopResize };
}
