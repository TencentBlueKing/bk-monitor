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

import { Component, Vue } from 'vue-property-decorator';

type DragType = 'dragX' | 'dragY';

@Component
export default class ClassDragMixin extends Vue {
  /** 是否正在改变输入框高度 */
  isChanging = false;
  /** 当前容器的高度 */
  currentBoxHeight = null;
  /** 输入框最小高度 */
  collectMinHeight = 160;
  /** 输入框最大高度 */
  collectMaxHeight = 600;
  /** 当前容器的高度 */
  collectHeight = 160;
  /** 当前容器的宽度 */
  currentBoxWidth = null;
  /** 输入框最小宽度 */
  collectMinWidth = 160;
  /** 输入框最大宽度 */
  collectMaxWidth = 600;
  /** 当前容器的宽度 */
  collectWidth = 160;
  /** 当前Y轴的高度 */
  currentScreenY = null;
  /** 当前X轴的宽度 */
  currentScreenX = null;
  /** 默认的拖拽的方式 X轴 */
  currentDragType = 'dragX';

  public dragBegin(e: MouseEvent, type: DragType = 'dragX') {
    e.stopPropagation();
    this.currentDragType = type;
    this.isChanging = true;
    this.currentBoxHeight = this.collectHeight;
    this.currentBoxWidth = this.collectWidth;
    switch (type) {
      case 'dragX':
        this.currentScreenX = e.screenX;
        break;
      case 'dragY':
        this.currentScreenY = e.screenY;
        break;
      default:
        break;
    }
    window.addEventListener('mousemove', this.dragMoving, { passive: true });
    window.addEventListener('mouseup', this.dragStop, { passive: true });
  }

  public dragMoving(e: MouseEvent) {
    switch (this.currentDragType) {
      case 'dragX': {
        const newTreeBoxWidth = this.currentBoxWidth + e.screenX - this.currentScreenX;
        if (newTreeBoxWidth < this.collectMinWidth) {
          this.collectWidth = this.collectMinWidth;
          this.dragStop();
        } else if (newTreeBoxWidth >= this.collectMaxWidth) {
          this.collectWidth = this.collectMaxWidth;
        } else {
          this.collectWidth = newTreeBoxWidth;
        }
        break;
      }
      case 'dragY': {
        const newTreeBoxHeight = this.currentBoxHeight + e.screenY - this.currentScreenY;
        if (newTreeBoxHeight < this.collectMinHeight) {
          this.collectHeight = this.collectMinHeight;
          this.dragStop();
        } else if (newTreeBoxHeight >= this.collectMaxHeight) {
          this.collectHeight = this.collectMaxHeight;
        } else {
          this.collectHeight = newTreeBoxHeight;
        }
        break;
      }
      default:
        break;
    }
  }

  public dragStop() {
    this.isChanging = false;
    this.currentBoxHeight = null;
    this.currentScreenY = null;
    this.currentBoxWidth = null;
    this.currentScreenX = null;
    window.removeEventListener('mousemove', this.dragMoving);
    window.removeEventListener('mouseup', this.dragStop);
  }
}
