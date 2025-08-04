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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './monitor-cross-drag.scss';

interface IMonitorDragEvent {
  onMove: (resultHeight: number, cancelFn: () => void) => void;
}
interface IMonitorDragProps {
  /** 可拖动的最大容器高度 */
  maxHeight?: number;
  /** 可拖动的最小容器高度 */
  minHeight?: number;
}
@Component
export default class MonitorCrossDrag extends tsc<IMonitorDragProps, IMonitorDragEvent> {
  /** 可拖动的最小容器高度 */
  @Prop({ type: Number }) minHeight: number;
  /** 可拖动的最大容器高度 */
  @Prop({ type: Number }) maxHeight: number;

  mounted() {
    this.initConfig();
  }
  activated() {
    this.initConfig();
  }

  /**
   * @description: 初始化 resize 操作所需要的配置
   */
  initConfig() {
    setTimeout(() => {
      this.$el.parentElement.style.position = 'relative';
    }, 30);
  }

  /**
   * @description: mousedown触发回调
   * @param {MouseEvent} mouseEventTarget 鼠标事件
   */
  handleMouseDown(mouseDownEvent: MouseEvent) {
    // 需要进行 resize 操作的dom元素
    const target = this.$el.parentElement;
    // 最后一次移动时鼠标所在位置
    let lastPosition = mouseDownEvent.clientY;
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    // 保存 body 原来的 cursor 配置，后续拖拽结束后恢复
    const sourceBodyCursor = document.body.style.cursor;
    // 保存需要进行 resize 操作的dom元素原来的 cursor 配置，后续拖拽结束后恢复
    const sourceTargetCursor = target.style.cursor;
    target.style.cursor = 'row-resize';
    document.body.style.cursor = 'row-resize';
    const handleMouseMove = event => {
      const rect = target.getBoundingClientRect();
      const moveDistance = event.clientY - lastPosition;
      let resultHeight = rect.height + moveDistance;
      let shouldCompare = !!this.minHeight || !!this.maxHeight;

      if (shouldCompare && this.minHeight && resultHeight <= this.minHeight) {
        shouldCompare = false;
        resultHeight = this.minHeight;
      }
      if (shouldCompare && this.maxHeight) {
        resultHeight = Math.max(this.maxHeight, resultHeight);
      }
      this.$emit('move', resultHeight, handleMouseUp);
      lastPosition = event.clientY;
    };
    function handleMouseUp() {
      target.style.cursor = sourceTargetCursor;
      document.body.style.cursor = sourceBodyCursor;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    }
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }

  render() {
    return (
      <div
        class='monitor-cross-drag'
        onMousedown={this.handleMouseDown}
      />
    );
  }
}
