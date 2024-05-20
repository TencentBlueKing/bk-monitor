<!--
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
-->
<template>
  <div
    ref="dragRef"
    class="drag-label"
    @click="e => $emit('click', e)"
    @mousedown="handleMouseDown"
    @mousemove="handleMouseMove"
    @mouseup="handleMouseUp"
    @touchend="handleMouseUp"
    @touchmove.prevent="handleMouseMove"
    @touchstart="handleMouseDown"
  >
    <slot>
      <i class="icon-monitor icon-menu-event" />
    </slot>
    <span
      v-if="alarmNum > 0"
      class="alarm-num"
    >
      {{ alarmNum > 99 ? 99 : alarmNum }}
    </span>
  </div>
</template>
<script lang="ts">
import { Component, Prop, Ref, Vue } from 'vue-property-decorator';
@Component
export default class DragLabel extends Vue {
  // 告警数量
  @Prop({ default: 0 }) readonly alarmNum!: number;

  @Ref() readonly dragRef: HTMLElement;

  isMoving = false;
  position: { x: number; y: number } = { x: 0, y: 0 };
  nx = 0;
  ny = 0;
  dx = 0;
  dy = 0;
  xPum = 0;
  yPum = 0;

  beforeDestroy() {
    this.isMoving = false;
  }

  // 拖拽开始触发
  handleMouseDown(event) {
    this.isMoving = true;
    let touch;
    if (event.touches) {
      const [touchs] = event.touches;
      touch = touchs;
    } else {
      touch = event;
    }
    this.position.x = touch.clientX;
    this.position.y = touch.clientY;
    this.dx = this.dragRef.offsetLeft;
    this.dy = this.dragRef.offsetTop;
  }

  // 移动时触发
  handleMouseMove(event) {
    if (this.isMoving) {
      let touch;
      if (event.touches) {
        const [touchs] = event.touches;
        touch = touchs;
      } else {
        touch = event;
      }
      this.nx = touch.clientX - this.position.x;
      this.ny = touch.clientY - this.position.y;
      this.xPum = this.dx + this.nx;
      this.yPum = this.dy + this.ny;
      // 添加限制：只允许在屏幕内拖动
      const maxWidth = window.innerWidth - 48;
      const maxHeight = window.innerHeight - 48;
      if (this.xPum < 0) {
        // 屏幕x限制
        this.xPum = 0;
      } else if (this.xPum > maxWidth) {
        this.xPum = maxWidth;
      }
      if (this.yPum < 0) {
        // 屏幕y限制
        this.yPum = 0;
      } else if (this.yPum > maxHeight) {
        this.yPum = maxHeight;
      }
      this.dragRef.style.left = `${this.xPum}px`;
      this.dragRef.style.top = `${this.yPum}px`;
      // 阻止页面的滑动默认事件
      document.addEventListener(
        'touchmove',
        () => {
          event.stopPropagation(); // jq 阻止冒泡事件
        },
        false
      );
    }
  }

  // 拖拽释放时触发
  handleMouseUp() {
    this.isMoving = false;
  }
}
</script>
<style lang="scss" scoped>
.drag-label {
  position: fixed;
  right: 24px;
  bottom: 92px;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  font-size: 22px;
  color: #c4c6cc;
  background: #313238;
  border-radius: 24px;
  box-shadow: 0px 3px 6px 0px rgba(79, 85, 96, 0.3);
  opacity: 0.8;

  .alarm-num {
    position: absolute;
    top: 0px;
    right: 0px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    padding: 2px;
    font-size: 10px;
    color: white;
    background-color: #ea3636;
    border-radius: 50%;
  }
}
</style>
