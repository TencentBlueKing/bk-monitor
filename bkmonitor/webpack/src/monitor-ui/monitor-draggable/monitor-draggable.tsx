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
import { Component, Emit, Provide } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './monitor-draggable.scss';

export interface IDraggableEvent {
  onDragstart: DragEvent;
  onDrop: IOnDrop;
}

export interface IOnDrop {
  fromIndex: number;
  toIndex: number;
}

@Component
export default class MonitorDraggable extends tsc<object, IDraggableEvent> {
  /** 拖拽索引 */
  fromIndex = 0;
  toIndex = 0;

  /**
   * @description: 记录拖拽元素索引
   * @param {number} index
   */
  @Provide('setFromIndex')
  handleSetFromIndex(index: number) {
    this.fromIndex = index;
  }

  /**
   * @description: 记录拖拽目标索引
   * @param {number} index
   */
  @Provide('setToIndex')
  handleSetToIndex(index: number) {
    this.toIndex = index;
  }

  /**
   * @description: 向上查找拖拽元素
   * @param {HTMLElement} target
   */
  findDragItem(target: HTMLElement): HTMLElement {
    let parent = target;
    while (parent && parent.className.indexOf('drag-item-wrap') === -1) {
      if (parent.className.indexOf('monitor-draggable-wrap') > -1) break;
      parent = parent.parentElement;
    }
    return parent;
  }

  /**
   * @description: 拖拽开始 标记拖拽元素索引
   * @param {DragEvent} evt
   */
  @Emit('dragstart')
  handleDragStart(evt) {
    evt.dataTransfer.effectAllowed = 'move';
    this.fromIndex = +evt.target.dataset.index;
    return evt;
  }
  /**
   * @description: 拖拽经过
   * @param {DragEvent} evt
   */
  handleDragOver(evt: DragEvent) {
    evt.preventDefault();
  }

  /**
   * @description: 拖入目标 标记目标索引并派发拖入事件
   * @param {*} evt
   */
  handleDrop(evt) {
    const dragItemEl = this.findDragItem(evt.target);
    if (dragItemEl.dataset.index) {
      this.toIndex = +dragItemEl.dataset.index;
      this.emitDrop();
    }
  }

  @Emit('drop')
  emitDrop(): IDraggableEvent['onDrop'] {
    return {
      fromIndex: this.fromIndex,
      toIndex: this.toIndex,
    };
  }

  render() {
    return (
      <div
        class='monitor-draggable-wrap'
        onDragover={this.handleDragOver}
        onDragstart={this.handleDragStart}
        onDrop={this.handleDrop}
      >
        {/* <transition-group name="flip-list" tag="div"> */}
        {this.$slots.default}
        {/* </transition-group> */}
      </div>
    );
  }
}
